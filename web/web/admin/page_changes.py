from copy import copy
from itertools import chain
import re

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

    query = '''
        SELECT * FROM _page_changes
        WHERE riddle = :riddle
    '''
    page_changes = await database.fetch_all(query, {'riddle': alias})
    for page_change in map(dict, page_changes):

        if {'*', '?'} & set(page_change['path']):
            query = '''
                SELECT * FROM level_pages
                WHERE riddle = :riddle
                    AND path LIKE :wildcard_path
                    AND path NOT LIKE :wildcard_new_path
            '''
            values = {
                'riddle': alias,
                'wildcard_path':
                    page_change['path'].replace('*', '%').replace('?', '_'),
                'wildcard_new_path':
                    page_change['new_path'].replace('*', '%').replace('?', '_'),
            }
            if page_change['level_name']:
                # Restrict changes just to the specified level's pages
                query += 'AND level_name = :level_name'
                values |= {'level_name': page_change['level_name']}
            pages = await database.fetch_all(query, values)
            for path in [page['path'] for page in pages]:
                single_change = copy(page_change)
                single_change['path'] = path
                pattern = page_change['path'] \
                    .replace('?', '(.)').replace('*', '(.*)')
                t1 = re.split('[*]|[?]', page_change['new_path'])
                t2 = list(map(lambda k: f"\{k}", range(1, len(t1))))
                repl = ''.join(chain(*zip(t1, t2), t1[-1]))
                single_change['new_path'] = re.sub(pattern, repl, path)

                await _apply_change(single_change)

        elif '{' in page_change['path']:
            base_path, new_base_path = \
                page_change['path'], page_change['new_path']
            tokens_str = re.search('{(.+)}', base_path).group(1)
            new_tokens_str = re.search('{(.+)}', new_base_path).group(1)
            tokens = list(filter(None, tokens_str.split(',')))
            new_tokens = list(filter(None, new_tokens_str.split(',')))
            for i in range(max(len(tokens), len(new_tokens))):
                single_change = copy(page_change)
                single_change['path'] = (
                    f"{base_path.replace(tokens_str, tokens[i])}"
                    if tokens[i:] else ''
                )
                single_change['new_path'] = (
                    f"{base_path.replace(new_tokens_str, new_tokens[i])}"
                    if new_tokens[i:] else ''
                )

                await _apply_change(single_change)

        else:
            await _apply_change(page_change)

    return 'SUCCESS :)', 200


async def _apply_change(page_change: dict, dry_run: bool = False):

    alias = page_change['riddle']
    path, new_path = page_change['path'], page_change['new_path']
    level_name = page_change['level_name']

    async def _update_page_level(path: str, level_name: str | None) -> bool:
        '''Update level for page with given path.'''
        if dry_run:
            return False
        query = '''
            UPDATE level_pages
            SET level_name = :level_name
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias, 'path': path, 'level_name': level_name}
        return await database.execute(query, values)

    def _log(msg: str):
        '''Log message with riddle alias.'''
        if level_name:
            msg += f" ({level_name})"
        nonlocal success
        print(
            f"> \033[1m[{alias}]\033[0m {msg}... " +
            (
                '\033[1mOK\033[0m' if not dry_run and success else
                '\033[3mskipped\033[0m'
            ),
            flush=True
        )

    if page_change['trivial_move']:
        # "Trivial move" means the path change was essentially
        # due to logistics and not actually new/different content;
        # therefore, just rename the old page and let players keep it
        query = '''
            UPDATE IGNORE level_pages
            SET path = :new_path
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias,'path': path, 'new_path': new_path}
        if not dry_run:
            success = await database.execute(query, values)
        _log(
            f"Moving page "
            f"\033[3m{path}\033[0m -> \033[1;3m{new_path}\033[0m "
            f"(trivial)"
        )
    else:
        if path:
            # Erase level from the old page
            success = await _update_page_level(path, None)
            if not new_path:
                _log(f"Removing page \033[3m{path}\033[0m")
        if new_path:
            # Write level to the new page
            success = await _update_page_level(new_path, level_name)
            if not path:
                _log(f"Adding page \033[1;3m{new_path}\033[0m")
        if path and new_path:
            _log(
                f"Moving page "
                f"\033[3m{path}\033[0m -> \033[1;3m{new_path}\033[0m"
            )

    if path and new_path and not dry_run:
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
