from pymysql.err import IntegrityError
from quart import Blueprint
from quartcord import requires_authorization

from admin.admin_auth import admin_auth
from util.db import database

admin_page_changes = Blueprint('admin_page_changes', __name__)


@admin_page_changes.get('/admin/<alias>/apply-page-changes')
@requires_authorization
async def apply_page_changes(alias: str):
    '''Apply riddle-wise page changes.'''

    # Check for admin permissions
    await admin_auth(alias)

    async def _update_page_level(path: str, level_name: str | None):
        '''Update level for page with given path.'''
        query = '''
            UPDATE level_pages
            SET level_name = :level_name
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias, 'path': path, 'level_name': level_name}
        await database.execute(query, values)

    def _log(msg: str):
        '''Log message with riddle alias.'''
        if level_name:
            msg += f" ({level_name})"
        print(f"> \033[1m[{alias}]\033[0m {msg}")

    query = '''
        SELECT * FROM _page_changes
        WHERE riddle = :riddle
    '''
    page_changes = await database.fetch_all(query, {'riddle': alias})
    for page_change in page_changes:
        path, new_path = page_change['path'], page_change['new_path']
        level_name = page_change['level']

        if page_change['trivial_move']:
            # "Trivial move" means the path change was essentially
            # due to logistics and not actually new/different content;
            # therefore, just rename the old page and let players keep it
            query = '''
                UPDATE level_pages (
                SET path = :new_path
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': alias,'path': path, 'new_path': new_path}
            _log(
                f"Moving page "
                f"\033[3m{path}\033[0m -> \033[1;3m{new_path}\033[0m "
                f"(trivial)"
            )
        else:
            if path:
                # Erase level from the old page
                await _update_page_level(path, None)
                if not new_path:
                    _log(f"Removing page \033[3m{path}\033[0m")
            if new_path:
                # Write level to the new page
                await _update_page_level(new_path, level_name)
                if not path:
                    _log(f"Adding page \033[1;3m{new_path}\033[0m")
            if path and new_path:
                _log(
                    f"Moving page "
                    f"\033[3m{path}\033[0m -> \033[1;3m{new_path}\033[0m"
                )

        if path and new_path:
            # Update level data in case the old path was a front/answer one
            query = '''
                UPDATE levels
                SET path = :new_path
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': alias, 'path': path, 'new_path': new_path}
            await database.execute(query, values)
            query = '''
                UPDATE levels
                SET answer = :new_path
                WHERE riddle = :riddle AND answer = :path
            '''
            await database.execute(query, values)
    
    return 'SUCCESS :)', 200
