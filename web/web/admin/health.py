from itertools import dropwhile

from quart import Blueprint, render_template, request
from quartcord import requires_authorization
import requests
from requests.auth import HTTPBasicAuth

from admin.admin_auth import admin_auth
from admin.archive import ArchivePage
from credentials import get_path_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages
from util.db import database

admin_health = Blueprint('admin_health', __name__)


@admin_health.get('/admin/<alias>/health-diagnostics')
@requires_authorization
async def health_diagnostics(alias: str | None = None):

    await admin_auth(alias)
    
    def _get_status_symbol(status_code: int) -> str:
        symbols = {
            200: '✔️',
            401: '⛔',
            403: '🔴',
            404: '🔴',
            412: '❓',
        }
        return symbols.get(status_code, '')

    pages = await get_pages(
        alias,
        include_unlisted=request.args.get('includeUnlisted'),
        admin=True,
        as_json=False,
    )
    archive_requested = bool(request.args.get('archive'))
    skip_existing = bool(request.args.get('skipExisting'))
    start_level = request.args.get('start', list(pages.keys())[0])
    end_level = request.args.get('end')

    levels = {}
    riddle = await get_riddle(alias)
    for level_name in dropwhile(lambda k: k != start_level, pages):
        # Start iterating at user-informed level (if any)
        for path, page_data in absolute_paths(pages[level_name]['/']):
            if skip_existing:
                query = '''
                    SELECT 1 FROM _page_hashes
                    WHERE riddle = :riddle AND path = :path
                '''
                values = {'riddle': alias, 'path': path}
                if await database.fetch_val(query, values):
                    continue

            url = f"{riddle['root_path']}{path}"
            credentials = await get_path_credentials(alias, path)
            if credentials:
                username = credentials['username']
                password = credentials['password']
                url = url.replace('://', f"://{username}:{password}@")
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
                'status_symbol': _get_status_symbol(res.status_code),
            }
            if not level_name in levels:
                levels[level_name] = {}
            levels[level_name][path] = page_data | {'url': url}

            if res.ok and archive_requested:
                # Valid page, so archive it if new/changed
                archive_page = ArchivePage(alias, path, res.content)
                if await archive_page.record_hash():
                    archive_page.save()
            
        # Stop when reaching user-informed level (if any)
        if level_name == end_level:
            break

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels
    )
