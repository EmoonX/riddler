from quart import Blueprint, render_template
from quartcord import requires_authorization
import requests
from requests.auth import HTTPBasicAuth

from admin.admin_auth import admin_auth
from admin.backup import Backup
from credentials import get_correct_credentials
from inject import get_riddle
from levels import absolute_paths, get_pages

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

    pages = await get_pages(alias, json=False)

    levels = {}
    riddle = await get_riddle(alias)
    for level_name in pages:
        levels[level_name] = {}
        for path, page_data in absolute_paths(pages[level_name]['/']):
            url = f"{riddle['root_path']}{path}"
            credentials = await get_correct_credentials(alias, path)
            if credentials:
                username = credentials['username']
                password = credentials['password']
                url = url.replace('://', f"://{username}:{password}@")
            headers = {
                # Mask as real browser so certain hosts don't throw 412
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
            levels[level_name][path] = page_data

            if res.ok:
                backup = Backup(alias, path, res.content)
                await backup.record_page_hash()

    return await render_template(
        'admin/health.htm',
        riddle=riddle, levels=levels
    )
