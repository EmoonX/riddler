from itertools import dropwhile

from quart import Blueprint, render_template, request
from quartcord import requires_authorization
import requests
from requests.auth import HTTPBasicAuth

from admin.admin_auth import admin_auth
from admin.backup import PageBackup
from credentials import get_correct_credentials
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

    pages = await get_pages(alias, admin=True, json=False)
    backup_requested = bool(request.args.get('backup'))
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
            credentials = await get_correct_credentials(alias, path)
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
            levels[level_name][path] = page_data

            if res.ok and backup_requested:
                # Valid page, so employ backup if new/changed
                page_backup = PageBackup(alias, path, res.content)
                if await page_backup.record_hash():
                    page_backup.save()
            
        # Stop when reaching user-informed level (if any)
        if level_name == end_level:
            break

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels
    )
