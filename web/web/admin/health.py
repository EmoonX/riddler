from datetime import datetime
import re
from urllib.parse import urljoin
import warnings

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from quart import Blueprint, render_template, request
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth
from admin.archive import ArchivedPage
from credentials import get_path_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages
from process import process_url
from util.db import database

admin_health = Blueprint('admin_health', __name__)

status_symbols = {
    200: '✔️',
    401: '⛔',
    403: '🔴',
    404: '🔴',
    412: '❓',
}

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


@admin_health.get('/admin/<alias>/health-diagnostics')
@requires_authorization
async def health_diagnostics(alias: str):
    '''Run level/page health diagnostics for a given riddle.'''

    await admin_auth(alias)

    args = request.args
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

        # Build URL (with possibly embedded credentials)
        url = f"{riddle['root_path']}{path}"
        credentials = await get_path_credentials(alias, path)
        username = credentials['username']
        password = credentials['password']
        if username or password:
            url = url.replace('://', f"://{username or ''}:{password or ''}@")
        page_data |= {'url': url}

        if show_new_in_days:
            # Mark page as *new* if existing and newer than the X days given
            archived_page = await ArchivedPage.get_latest_snapshot(alias, path)
            if archived_page:
                page_data['content_hash'] = archived_page.content_hash
                page_data['retrieval_time'] = archived_page.retrieval_time
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
                return page_data

        headers = {
            # Impersonate real browser so certain hosts don't throw 412
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:128.0) '
                'Gecko/20100101 Firefox/128.0'
            )
        }
        res = requests.get(url, headers=headers, timeout=10)
        page_data |= {
            'status_code': res.status_code,
            'status_symbol': status_symbols.get(res.status_code),
        }
        if res.ok:
            # Valid page, so archive it if new/changed
            archived_page = ArchivedPage(alias, path, res.content)
            if await archived_page.record_hash():
                archived_page.save()
                page_data['new'] = True
            page_data['content_hash'] = archived_page.content_hash
            page_data['retrieval_time'] = archived_page.retrieval_time

            page_extension = path.partition('.')[-1].lower()
            if page_extension in ['htm', 'html', 'php', '']:
                # Check for redirects inside HTML pages
                page_data['redirects_to'] = \
                    await _check_and_record_redirect(path, res.text)

        return page_data

    async def _check_and_record_redirect(path: str, html: str) -> str | None:
        '''
        Search for and record redirect path when page contains the meta
        refresh tag (i.e `<meta http-equiv="refresh" "content=...; URL=...">).
        '''

        # Parse HTML content in search for specific tag
        soup = BeautifulSoup(html, features='html.parser')
        meta_refresh_tag = soup.find(
            'meta', {'http-equiv': re.compile('refresh', re.I)}
        )
        if not meta_refresh_tag:
            return None

        # Build absolute URL from tag's content and extract
        # processed path from it (either an actual path or external link)
        content = meta_refresh_tag.attrs['content']
        redirect_url = urljoin(
            f"{riddle['root_path']}{path}",
            re.sub(r';|=|\'|"', ' ', content).split()[-1],
        )
        redirect_path = await process_url(None, redirect_url, admin=True)

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
        if front_page := pages.get(level.get('frontPage')):
            level['pages'] |= {
                level['frontPage']: front_page | {'flag': 'front-page'}
            }
            del pages[level['frontPage']]
        image_path = urljoin(level.get('frontPage'), level.get('image'))
        if image_page := pages.get(image_path):
            level['pages'] |= {
                image_path: image_page | {'flag': 'front-image'}
            }
            del pages[image_path]

        # Show remaining paths, with answer path at the bottom
        answer_page = pages.pop(level.get('answer'), None)
        level['pages'] |= pages
        if answer_page:
            level['pages'] |= {
                level['answer']: answer_page | {'flag': 'answer'}
            }

        if include_level:
            # Include levels only within the [start, end] range (when given)
            levels[name] = level

        include_level &= not name == end_level

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels, all_pages_by_path=all_pages_by_path,
    )
