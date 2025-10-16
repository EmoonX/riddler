from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
import posixpath
import re
from urllib.parse import urljoin, urlsplit
import warnings

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from quart import Blueprint, current_app, render_template, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from admin.archive import ArchivedPage
from credentials import get_path_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages, listify
from process import process_url
from util.db import database

admin_health = Blueprint('admin_health', __name__)

status_symbols = {
    200: '✔️',
    302: '🧭',
    401: '⛔',
    403: '🔴',
    404: '🔴',
    412: '❓',
}

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


@admin_health.get('/admin/<alias>/health-diagnostics')
@requires_authorization
async def health_diagnostics(alias: str, background: bool = False):
    '''Run level/page health diagnostics for a given riddle.'''

    await admin_auth(alias)

    args = request.args
    if bool(args.get('background')) and not background:
        # Run background diagnostics to avoid worker timeout restarts
        current_app.add_background_task(
            health_diagnostics, alias, background=True
        )
        return f"[{alias}] Running Health Diagnostics in the background.", 202
    
    riddle = await get_riddle(alias)
    all_pages_by_level = await get_pages(
        alias,
        include_hidden=True,
        include_unlisted=True,
        include_removed=args.get('includeRemoved'),
        index_by_levels=True,
        as_json=False,
        admin=True,
    )
    redo_existing = bool(args.get('redoExisting'))
    show_new_in_days = int(args.get('showNewInDays', 0))
    start_level = args.get('start')
    end_level = args.get('end')

    async def _retrieve_page(
        path: str, page_data: dict, include_level: bool,
    ) -> dict:
        '''
        Retrieve page directly from riddle's host through web request,
        unless `include_level` or `redo_existing` conditions are(n't) met.
        '''
        
        url =  await _build_url(path)
        page_data |= {'url': url}

        if show_new_in_days:
            # Mark page as *new* if existing and newer than the X days given
            archived_page = await ArchivedPage.get_latest_snapshot(alias, path)
            if archived_page:
                page_data |= {
                    'content_hash': archived_page.content_hash,
                    'retrieval_time': archived_page.retrieval_time,
                }
                tdiff = datetime.utcnow() - archived_page.retrieval_time
                if tdiff.days < show_new_in_days:
                    page_data['new'] = True

        if not include_level:
            return page_data
        if not redo_existing:
            query = '''
                SELECT 1 FROM _page_hashes
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': alias, 'path': path}
            if await database.fetch_val(query, values):
                # Path has already been recorded, so skip it as instructed
                page_data |= {
                    'status_symbol': status_symbols.get(page_data['status_code'])
                }
                return page_data

        headers = {
            # Impersonate real browser so certain hosts don't throw 412
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:128.0) '
                'Gecko/20100101 Firefox/128.0'
            )
        }
        res = requests.get(
            _build_request_url(url),
            headers=headers,
            allow_redirects=False,  # don't follow 30x redirects
            timeout=10,
        )
        page_data |= {
            'status_code': res.status_code,
            'status_symbol': status_symbols.get(res.status_code),
        }
        if res.ok:
            # Valid page, so archive it if new/changed
            if last_modified := res.headers.get('Last-Modified'):
                last_modified = parsedate_to_datetime(last_modified)
            archived_page = ArchivedPage(
                alias, path, content=res.content, last_modified=last_modified
            )
            if await archived_page.record_hash():
                archived_page.save()
                page_data['new'] = True
            page_data['content_hash'] = archived_page.content_hash
            page_data['retrieval_time'] = archived_page.retrieval_time

            if Path(path).suffix in ['.htm', '.html', '.php', '']:
                # Look for redirects (30x and <meta> ones)
                page_data['redirects_to'] = \
                    await _search_and_record_redirect(path, res)

        await _update_status_code(path, res.status_code)

        return page_data

    async def _build_url(path: str) -> str:
        '''Build full external URL, embedding credentials if needed.'''

        url = f"{riddle['root_path']}{page_data['path']}"

        credentials = await get_path_credentials(alias, path)
        username = credentials['username']
        password = credentials['password']
        if username and password:
            url = url.replace('://', f"://{username or ''}:{password or ''}@")

        return url
 
    def _build_request_url(url: str) -> str:
        '''Build request-safe URL, accounting for quirks of certain hosts.'''

        parsed_url = urlsplit(url)
        if parsed_url.netloc.endswith('.neocities.org'):
            if parsed_url.path.endswith(('.htm', '.html')) and '?' not in url:
                # Add empty query to trick neocities.org's `.htm[l]` stripping
                url += '?'

        if url.endswith('?'):
            # Append dummy key/value so `requests` doesn't ignore the '?'
            url += '_='
        
        return url

    async def _search_and_record_redirect(
        path: str, response: requests.models.Response
    ) -> str | None:
        '''
        Search for, parse and record redirect path when page either:
            - comes from a `30x` response (`Location` header); or
            - contains `<script> [window.]location[.href] = '...'; </script>`; or
            - contains `<meta http-equiv="refresh" content="...">`.
        '''

        def _extract_redirect_href(res: requests.models.Response) -> str | None:
            '''Extract redirect href from response (header/content), if any.'''

            if location := res.headers.get('Location'):
                # 30x response, direct `Location` header
                return location
            
            # Parse HTML content in search of specific tags and patterns
            soup = BeautifulSoup(res.text, features='html.parser')

            # <script> window.location.href = '...'; </script>
            if script_tag := soup.script:
                if match := re.fullmatch(
                    r'''(window[.])?location([.]href)?\s*=\s*['"](.+)['"];?''',
                    script_tag.text.strip()
                ):
                    return match[3]

            # <meta http-equiv="refresh" content="X; URL='...'">
            meta_refresh_tag = soup.find(
                'meta', {'http-equiv': re.compile('refresh', re.I)}
            )
            if meta_refresh_tag:
                content = meta_refresh_tag.attrs['content']
                return re.sub(r';|=|\'|"', ' ', content).split()[-1]

            return None

        href = _extract_redirect_href(response)
        if not href:
            return None

        # Build processed path from href
        # (either an actual riddle page or full external link)
        redirect_url = urljoin(f"{riddle['root_path']}{path}", href)
        redirect_alias, redirect_path = \
            await process_url(None, redirect_url, admin=True)
        if redirect_alias != alias:
            redirect_path = href

        # Record redirect in DB
        query = '''
            UPDATE level_pages
            SET redirects_to = :redirect_path
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias, 'path': path, 'redirect_path': redirect_path}
        if await database.execute(query, values):
            print(
                f"> \033[1m[{alias}]\033[0m "
                f"Added redirect \033[3m{path} ➜ \033[1m{redirect_path}\033[0m",
                flush=True
            )

        return redirect_path

    async def _update_status_code(path: str, status_code: int):
        '''Mark response status code of page's last request (NULL if 200/OK).'''
        query = '''
            UPDATE level_pages
            SET status_code = :status_code
            WHERE riddle = :riddle AND path = :path
        '''
        values = {
            'riddle': alias,
            'path': path,
            'status_code': status_code if status_code != 200 else None,
        }
        await database.execute(query, values)

    # Start iterating at user-informed level (if any)
    levels = {}
    all_pages_by_path = {}
    include_level = not bool(start_level)
    for name, level in all_pages_by_level.items():
        include_level |= name == start_level
        if include_level:
            if name != 'Unlisted':
                print(
                    f"> \033[1m[{alias}]\033[0m Fetching page data for {name}…",
                    flush=True
                )
            else:
                print(
                    f"> \033[1m[{alias}]\033[0m Fetching unlisted page data…",
                    flush=True
                )

        pages = {}
        for path, page_data in absolute_paths(level['/']):
            page_data = await _retrieve_page(path, page_data, include_level)
            pages[path] = all_pages_by_path[path] = page_data

        # Show front page/image paths at the top
        level |= {'pages': {}}
        level['frontPages'] = listify(level.get('frontPage'))
        for path in level['frontPages']:
            if front_page := pages.get(path):
                level['pages'] |= {path: front_page | {'flag': 'front-page'}}
                del pages[path]
        if level['frontPages']:
            image_path = posixpath.join(
                # Use `posixpath` to avoid `urljoin`'s '..' resolution
                f"{level['frontPages'][0].rpartition('/')[0]}/",
                level.get('image') or '',
            )
            if image_page := pages.get(image_path):
                level['pages'] |= {
                    image_path: image_page | {'flag': 'front-image'}
                }
                del pages[image_path]

        if args.get('orderBy') == 'time':
            # Order displayed pages by harvest time
            pages = dict(sorted(
                pages.items(),
                key=lambda page: page[1].get('find_time_raw') or datetime.min,
            ))

        # Show remaining paths, with answer(s) at the bottom
        level['answers'] = listify(level.get('answer'))
        answer_pages = []
        for path in level['answers']:
            if page := pages.pop(path, None):
                answer_pages.append(page)
        level['pages'] |= pages            
        level['pages'] |= {
            page['path']: page | {'flag': 'answer'}
            for page in answer_pages
        }

        if include_level:
            # Include levels only within the [start, end] range (when given)
            levels[name] = level

        include_level &= not name == end_level

    # TODO
    # Retroactively grant user records for non-demo riddles; temp-fix for now
    query = '''
        UPDATE user_pages up
        SET level_name = (
            SELECT level_name FROM level_pages lp
            WHERE up.riddle = lp.riddle AND up.path = lp.path
        )
        WHERE level_name IS NULL AND up.riddle IN (
            SELECT alias FROM riddles
            WHERE demo IS NOT TRUE
        )
    '''
    await database.execute(query)

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels, all_pages_by_path=all_pages_by_path,
    )
