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

    async def _handle_wildcards(glob_change: dict):
        '''Handle paths with wildcards (`*` and/or `?`).'''

        query = '''
            SELECT * FROM level_pages
            WHERE riddle = :riddle
                AND path LIKE :wildcard_path
                AND path NOT LIKE :wildcard_new_path
        '''
        values = {
            'riddle': alias,
            'wildcard_path':
                glob_change['path'].replace('*', '%').replace('?', '_'),
            'wildcard_new_path':
                glob_change['new_path'].replace('*', '%').replace('?', '_'),
        }
        if glob_change['level_name']:
            # Restrict changes just to the specified level's pages
            query += 'AND (level_name = :level_name OR level_name IS NULL)'
            values |= {'level_name': glob_change['level_name']}
        pages = await database.fetch_all(query, values)

        for path in [page['path'] for page in pages]:
            single_change = copy(glob_change)
            single_change['path'] = path
            pattern = glob_change['path'] \
                .replace('?', '(.)').replace('*', '(.*)')
            t1 = re.split('[*|?]', glob_change['new_path'])
            t2 = list(map(lambda k: f"\{k}", range(1, len(t1))))
            repl = ''.join(chain(*zip(t1, t2), t1[-1]))
            single_change['new_path'] = re.sub(pattern, repl, path)

            await _apply_change(single_change, expanded=True)

    async def _handle_tokens(glob_change: dict):
        '''Handle paths with tokens (`{a,b,c,...}`).'''

        base_path, new_base_path = \
            glob_change['path'], glob_change['new_path']
        tokens, new_tokens = [], []
        if base_path:
            tokens_str = re.search('{(.+)}', base_path).group(1)
            tokens = list(filter(None, tokens_str.split(',')))
        if new_base_path:
            new_tokens_str = re.search('{(.+)}', new_base_path).group(1)
            new_tokens = list(filter(None, new_tokens_str.split(',')))

        for i in range(max(len(tokens), len(new_tokens))):
            single_change = copy(glob_change)
            single_change['path'] = (
                base_path.replace(f"{{{tokens_str}}}", tokens[i])
                if tokens[i:] else ''
            )
            single_change['new_path'] = (
                new_base_path.replace(f"{{{new_tokens_str}}}", new_tokens[i])
                if new_tokens[i:] else ''
            )

            await _apply_change(single_change, expanded=True)

    def _log_glob_change(glob_type: str, glob_change: str):
        '''Log glob change, highlighting pattern(s).'''
        path, new_path = glob_change['path'], glob_change['new_path']
        pattern = {'wildcard': '([*|?])', 'tokenized': '({.+})'}[glob_type]
        repl = r'\033[1m\1\033[0m\033[4m'
        formatted_path = f"\033[4m{re.sub(pattern, repl, path)}\033[0m"
        formatted_new_path = f"\033[4m{re.sub(pattern, repl, new_path)}\033[0m"
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Expanding {glob_type} "
            + (
                f"paths {formatted_path} ➜ {formatted_new_path}"
                    if path and new_path else
                f"path {formatted_path if path else formatted_new_path}"
            ),
            flush=True
        )

    # Fetch page changes; partition those between single and glob ones
    query = '''
        SELECT * FROM _page_changes
        WHERE riddle = :riddle
    '''
    all_changes = await database.fetch_all(query, {'riddle': alias})
    single_changes, glob_changes = [], []
    for page_change in map(dict, all_changes):
        is_glob = bool(set('*?{}') & set(page_change['path']))
        (single_changes, glob_changes)[is_glob].append(page_change)

    # Apply single changes
    for single_change in single_changes:
        await _apply_change(single_change)

    # Apply glob changes, iterating in `most specific -> most general` order
    for glob_change in reversed(glob_changes):
        if {'*', '?'} & set(glob_change['path']):
            _log_glob_change('wildcard', glob_change)
            await _handle_wildcards(glob_change)
        elif {'{', '}'} & set(glob_change['path'] or glob_change['new_path']):
            _log_glob_change('tokenized', glob_change)
            await _handle_tokens(glob_change)

    return 'SUCCESS :)', 200


async def _apply_change(page_change: dict, expanded: bool = False):
    '''Apply individual page change.'''

    alias = page_change['riddle']
    path, new_path = page_change['path'], page_change['new_path']

    query = '''
        SELECT level_name FROM level_pages
        WHERE riddle = :riddle AND path = :path
    '''
    values = {'riddle': alias, 'path': path}
    if level_name := await database.fetch_val(query, values):
        if not page_change['level_name']:
            page_change['level_name'] = level_name
        elif level_name != page_change['level_name']:
            raise ValueError(
                f"mismatching levels for page {path}: "
                f"'{level_name}' (level_pages) and "
                f"'{page_change['level_name']}' (_page_changes)"
            )

    async def _update_page_data(
        path: str, level_name: str | None, removed: bool
    ) -> bool:
        '''Update level and/or removed status for page.'''

        values = {'riddle': alias, 'path': path}
        success = False
        if removed:
            query = '''
                UPDATE level_pages
                SET hidden = TRUE, removed = TRUE
                WHERE riddle = :riddle AND path = :path
            '''
            success |= await database.execute(query, values)
        if level_name:
            query = '''
                UPDATE level_pages
                SET level_name = :level_name
                WHERE riddle = :riddle AND path = :path
            '''
            values |= {'level_name': level_name}
            success |= await database.execute(query, values)
            query = '''
                UPDATE user_pages
                SET level_name = :level_name
                WHERE riddle = :riddle AND path = :path
            '''
            success |= await database.execute(query, values)

        return success

    async def _apply_trivial_move(path: str, new_path: str, level_name: str):
        '''
        Apply a "trivial move", meaning the path change was essentially
        due to logistics and not actual new/different name/content.
        '''

        # Mark old path as (removed) alias
        # query = '''
        #     UPDATE IGNORE level_pages
        #     SET alias_for = :new_path
        #     WHERE riddle = :riddle AND path = :path
        # '''
        # values = {'riddle': alias, 'path': path, 'new_path': new_path}
        # await database.execute(query, values)

        # Remove level from the old page (to not pollute the catalog)
        query = '''
            UPDATE level_pages
            SET level_name = NULL
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias, 'path': path}
        await database.execute(query, values)

        # Duplicate user records from old path to new one
        query = '''
            INSERT IGNORE INTO user_pages
                (riddle, username, level_name, path, access_time)
            SELECT :riddle, username, :level_name, :new_path, access_time
            FROM user_pages up
            WHERE riddle = :riddle AND path = :path
        '''
        values |= {'level_name': level_name, 'new_path': new_path}
        await database.execute(query, values)

    def _log(msg: str):
        '''Log message with riddle alias.'''
        if level_name:
            msg += f" ({level_name})"
        nonlocal success
        print(
            f"> \033[1m[{alias}]\033[0m"
            f"{' ·· ' if expanded else ' '}{msg}… "
            f"\033{'[1mOK' if success else '[3mskipped'}\033[0m",
            flush=True
        )

    success = False
    if path:
        # Mark old page as removed
        success |= await _update_page_data(path, level_name, removed=True)
        if not new_path:
            _log(f"Marking page \033[3m{path}\033[0m as removed")
            return
    if new_path:
        # Write level to the new page
        success |= await _update_page_data(new_path, level_name, removed=False)
        if not path:
            _log(f"Adding page \033[1;3m{new_path}\033[0m")
            return

    # Both `path`` and `new_path`` given, so handle page move
    _log(
        f"Moving page "
        f"\033[3m{path}\033[0m to \033[1;3m{new_path}\033[0m"
        f"{' (trivial)' if page_change['trivial_move'] else ''}"
    )
    if page_change['trivial_move']:
        await _apply_trivial_move(path, new_path, level_name)

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

    # Update achievement data
    query = '''
        SELECT * FROM achievements
        WHERE riddle = :riddle
    '''
    values = {'riddle': alias}
    achievements = await database.fetch_all(query, values)
    for achievement in achievements:
        if f'"{path}"' in (paths_json := achievement['paths_json']):
            query = '''
                UPDATE achievements
                SET paths_json = :paths_json
                WHERE riddle = :riddle AND title = :title
            '''
            values |= {
                'title': achievement['title'],
                'paths_json': re.sub(f'"{path}"', f'"{new_path}"', paths_json),
            }
            await database.execute(query, values)
