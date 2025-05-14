from collections import defaultdict
from itertools import dropwhile
import re
from urllib.parse import urljoin
import warnings

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from quart import Blueprint, render_template, request
from quartcord import requires_authorization
import requests
from requests.auth import HTTPBasicAuth

from admin.admin_auth import admin_auth
from admin.archive import ArchivePage
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
    '''Run page-health diagnostics for a given riddle.'''

    await admin_auth(alias)

    riddle = await get_riddle(alias)
    pages = await get_pages(
        alias,
        include_unlisted=request.args.get('includeUnlisted'),
        include_removed=request.args.get('includeRemoved'),
        as_json=False,
        admin=True,
    )
    archive_requested = bool(request.args.get('archive'))
    skip_existing = bool(request.args.get('skipExisting'))
    show_skipped = bool(request.args.get('showSkipped'))
    skip_hidden = bool(request.args.get('skipHidden'))
    start_level = request.args.get('start', list(pages.keys())[0])
    end_level = request.args.get('end')

    async def _retrieve_page(path: str, page_data: dict) -> dict | None:
        '''
        Retrieve page directly from riddle's host through web request
        (unless `skipExisting` is passed), optionally archiving its content.
        '''

        # Build URL (with possibly embedded credentials)
        url = f"{riddle['root_path']}{path}"
        credentials = await get_path_credentials(alias, path)
        if credentials['username']:
            username = credentials['username']
            password = credentials['password']
            url = url.replace('://', f"://{username}:{password}@")
        page_data |= {'url': url}

        if skip_existing:
            query = '''
                SELECT 1 FROM _page_hashes
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': alias, 'path': path}
            if await database.fetch_val(query, values):
                # Path has already been recorded, so skip it as instructed
                if show_skipped:
                    return page_data
                return None

        headers = {
            # Impersonate real browser so certain hosts don't throw 412
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:128.0) '
                'Gecko/20100101 Firefox/128.0'
            )
        }
        res = requests.get(url, headers=headers)
        page_data |= {
            'status_code': res.status_code,
            'status_symbol': status_symbols.get(res.status_code),
        }
        if res.ok:
            if archive_requested:
                # Valid page, so archive it if new/changed
                archive_page = ArchivePage(alias, path, res.content)
                if await archive_page.record_hash():
                    archive_page.save()
                    page_data['content_hash'] = archive_page.content_hash

            page_extension = path.partition('.')[-1].lower()
            if page_extension in ['htm', 'html', 'php', '']:
                # Check for redirects in HTML pages
                await _check_and_record_redirect(path, res.text)

        return page_data

    async def _check_and_record_redirect(path: str, html: str):
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
            return

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

    levels = defaultdict(dict)
    for level_name in dropwhile(lambda k: k != start_level, pages):
        # Start iterating at user-informed level (if any)
        if level_name:
            print(
                f"> \033[1m[{alias}]\033[0m "
                f"Fetching page data for {level_name}…",
                flush=True
            )
        else:
            print(
                f"> \033[1m[{alias}]\033[0m "
                f"Fetching unlisted page data…",
                flush=True
            )
        for path, page_data in absolute_paths(pages[level_name]['/']):
            if page_data := await _retrieve_page(path, page_data):
                levels[level_name][path] = page_data

        # Stop when reaching user-informed level (if any)
        if level_name == end_level:
            break

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels
    )
