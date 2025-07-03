from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from itertools import islice
import json
import os

from quart import Blueprint, jsonify, render_template, request
from quartcord import requires_authorization

from admin.admin_auth import is_admin_of
from auth import discord
from credentials import get_all_unlocked_credentials
from util.db import database
from util.levels import get_ordered_levels

# Create app blueprint
levels = Blueprint('levels', __name__)


@levels.get('/<alias>/levels')
@requires_authorization
async def level_list(alias: str):
    '''Fetch list of levels, showing only applicable public info.'''

    async def _populate_level_data(level: dict):
        '''Retrieve level data and add to dict.'''

        # Add level unlocking and completion info
        user_level = user_level_data.get(level['name'])
        level['unlocked'] = user_level is not None
        if not level['unlocked']:
            level['unlocked'] = (
                not level['has_requirements']
                and not level['is_secret']
            )
        level['beaten'] = bool(user_level and user_level['completion_time'])

        # _, status = await admin.auth(alias)
        # if status == 200:
        # if False:
        #     # If admin of riddle, everything is unlocked :)
        #     level['beaten'] = True
        #     level['unlocked'] = True
        #     if result:
        #         level['rating_given'] = result['rating_given']
        # else:

        if level['unlocked']:
            if level['path'] and level['path'].startswith('['):
                # If a multi-front level, pick up the first found
                # front path for player purposes (e.g image link)
                query = '''
                    SELECT * FROM user_pages
                    WHERE riddle = :riddle
                        AND username = :username
                        AND level_name = :level_name
                '''
                values = base_values | {'level_name': level['name']}
                result = await database.fetch_all(query, values)
                found_paths = set([row['path'] for row in result])
                paths = json.loads(level['path'])
                for path in paths:
                    if path in found_paths:
                        level['path'] = path
                        break
                if level['path'][0] == '[':
                    level['path'] = ''  # safeguard

        if level['beaten']:
            # Get level rating
            user_level = user_level_data[level['name']]
            level['rating_given'] = user_level['rating_given']

            # Get total file count for level
            query = '''
                SELECT COUNT(*) FROM level_pages
                WHERE riddle = :riddle
                    AND level_name = :level
                    AND hidden IS NOT TRUE
                GROUP BY riddle, level_name
            '''
            values = {'riddle': alias, 'level': level['name']}
            level['pages_total'] = await database.fetch_val(query, values)

        # Get player's current found pages count for level
        query = '''
            SELECT *
            FROM user_pages up INNER JOIN level_pages lp
                ON up.riddle = lp.riddle AND up.path = lp.path
            WHERE up.riddle = :riddle
                AND up.username = :username
                AND up.level_name = :level
                AND lp.hidden IS NOT TRUE
        '''
        values = base_values | {'level': level['name']}
        pages_data = await database.fetch_all(query, values)
        if pages_data:
            found_pages = [row['path'] for row in pages_data]
            level['pages_found'] = len(found_pages)

            # Get topmost folder by the
            # longest common prefix of all found level pages
            parsed_prefix = found_pages[0].split('/')
            for path in islice(found_pages, 1, None):
                parsed_path = path.split('/')
                k = min(len(parsed_path), len(parsed_prefix))
                for i in range(k):
                    if parsed_path[i] != parsed_prefix[i]:
                        parsed_prefix = parsed_prefix[:i]
                        break
            level['topmost_folder'] = f"{'/'.join(parsed_prefix)}/"

            if level['path'] not in found_pages:
                # Fallback for when front path has changed
                # but user hasn't accessed it yet
                level['path'] = ''

        # Register list of users currently working on level
        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle
                AND level_name = :name
                AND completion_time IS NULL
            ORDER BY find_time DESC
        '''
        values = {'riddle': alias, 'name': level['name']}
        result = await database.fetch_all(query, values)
        level['users'] = [dict(level) for level in result]

    # async def _add_credentials(level: dict):
    #     '''Add credentials (if any) for level's front path.'''
    #     for path in reversed(credentials):
    #         # Iterate in reverse to pick the innermost dir
    #         if level['path'].startswith(path):
    #             level |= credentials[path]
    #             return

    # Get riddle level data
    query = '''
        SELECT *, EXISTS(
            SELECT level_name FROM level_requirements lr
            WHERE riddle = :riddle AND lv.name = lr.level_name
        ) AS has_requirements
        FROM levels lv
        WHERE riddle = :riddle
        ORDER BY `index`
    '''
    values = {'riddle': alias}
    levels_list = [
        {**row, 'image': os.path.basename(row['image'] or '')}
        for row in await database.fetch_all(query, values)
    ]

    # Get riddle level sets
    query = '''
        SELECT name FROM level_sets
        WHERE riddle = :riddle
    '''
    level_sets = await database.fetch_all(query, values)

    # Retrieve user-specific level data
    user = await discord.get_user()
    query = '''
        SELECT level_name, completion_time, rating_given FROM user_levels
        WHERE riddle = :riddle AND username = :username
    '''
    base_values = values | {'username': user.name}
    result = await database.fetch_all(query, base_values)
    user_level_data = {row['level_name']: row for row in result}

    # Build sets & levels dict
    levels_dict = {set_['name']: [] for set_ in level_sets}
    for level in levels_list:
        await _populate_level_data(level)
        # await _add_credentials(level)
        levels_dict[level['level_set']].append(level)

    # Pass better named dict to template
    context = locals() | {'levels': levels_dict}
    context.pop('levels_dict')
    return await render_template('levels.htm', **context)


@levels.get('/<alias>/levels/get-pages')
@levels.get('/<alias>/levels/get-pages/<requested_level>')
@requires_authorization
async def get_pages(
    alias: str,
    requested_level: str = '%',
    include_hidden: bool = False,
    include_unlisted: bool = False,
    include_removed: bool = False,
    index_by_levels: bool = True,
    as_json: bool = True,
    admin: bool = False,
) -> dict | str:
    '''Return a recursive JSON of all user level folders and pages.
    If a level is specified, return only pages from that level instead.'''

    def _stringify_datetime(time: datetime) -> str:
        return time.strftime('%Y/%b/%d at %H:%M (UTC)')

    admin &= await is_admin_of(alias)

    # Fetch user page data
    level_condition = 'level_name LIKE :level_name'
    if include_unlisted:
        level_condition = f"({level_condition} OR level_name IS NULL)"
    values = {
        'riddle': alias,
        'level_name': requested_level,
    }
    if admin:
        user = None
        query = f"""
            SELECT *, current_timestamp() AS access_time FROM level_pages
            WHERE riddle = :riddle
                AND {level_condition}
                {'AND hidden  IS NOT TRUE' if not include_hidden  else ''}
                {'AND removed IS NOT TRUE' if not include_removed else ''}
        """
    else:
        user = await discord.get_user()
        # TODO
        query = f"""
            SELECT up.level_name, up.path, up.access_time, lp.*
            FROM user_pages up INNER JOIN level_pages lp
                ON up.riddle = lp.riddle AND up.path = lp.path
            WHERE up.riddle = :riddle
                AND username = :username
                AND {
                    level_condition
                        .replace('level_name LIKE', 'up.level_name LIKE')
                        .replace('level_name IS  ', 'up.level_name IS  ')
                }
                {'AND hidden  IS NOT TRUE' if not include_hidden  else ''}
                {'AND removed IS NOT TRUE' if not include_removed else ''}
            ORDER BY SUBSTRING_INDEX(up.path, ".", -1)
        """
        values |= {'username': user.name}
    result = await database.fetch_all(query, values)
    page_data = {}
    for row in result:
        page_data[row['path']] = dict(row)
        if not row['level_name']:
            page_data[row['path']]['level_name'] = 'Unlisted'

    # Fetch and build general unlocked level data
    unlocked_levels = {}
    if admin:
        query = '''
            SELECT 
                *,
                current_timestamp() AS find_time,
                current_timestamp() AS completion_time
            FROM levels
            WHERE riddle = :riddle AND name LIKE :level_name
        '''
    else:
        query = '''
            SELECT lv.*, ul.*
            FROM levels lv INNER JOIN user_levels ul
                ON lv.riddle = ul.riddle AND lv.name = ul.level_name
            WHERE lv.riddle = :riddle
                AND username = :username
                AND lv.name LIKE :level_name
        '''
    result = await database.fetch_all(query, values)
    for row in result:
        level_name = row['name']
        unlocked_levels[level_name] = {
            'levelSet': row['level_set'],
            'latinName': row['latin_name'],
            'image': row['image'],
            'unlockTime': _stringify_datetime(row['find_time']),
        }
        if page_data.get(row['path']) or admin:
            unlocked_levels[level_name] |= {'frontPage': row['path']}
        if row['completion_time']:
            if page_data.get(row['answer']) or admin:
                unlocked_levels[level_name] |= {'answer': row['answer']}
            unlocked_levels[level_name] |= {
                'solveTime': _stringify_datetime(row['completion_time']),
            }

    # Scan extensions dir for available extension icon names
    available_extensions = set()
    extensions_dir = '../static/icons/extensions'
    for icon in os.scandir(extensions_dir):
        name = icon.name.rpartition('.')[0]
        available_extensions.add(name)

    # Build dict of (level -> paths)
    ordered_levels = await get_ordered_levels(alias)
    paths = {level_name: [] for level_name in ordered_levels}
    if include_unlisted:
        paths |= {'Unlisted': []}
    for data in page_data.values():
        extension = data['path'].rpartition('.')[-1].lower()
        data['page'] = data['path'].rpartition('/')[-1]
        data['folder'] = 0
        data['unknownExtension'] = extension not in available_extensions
        data['access_time'] = data['accessTime'] = \
            _stringify_datetime(data['access_time'])
        paths[data['level_name']].append(data)

    # Build recursive dict of folders and files
    base = {
        'children': {}, 'folder': 1, 'path': '/',
        'filesFound': 0, 'pagesFound': 0,
    }
    if not index_by_levels:
        base |= {'levels': {}}
    pages = {} if index_by_levels else {'/': deepcopy(base)}
    for level_name, level_paths in paths.items():
        if not admin and not unlocked_levels.get(level_name):
            continue
        if index_by_levels:
            level_pages = pages[level_name] = {'/': deepcopy(base)}
        else:
            level_pages = pages
        level_pages |= unlocked_levels.get(level_name, {})
        for data in level_paths:
            parent = level_pages['/']
            path = data['path']
            segments = path.split('/')[1:]
            for seg in segments:
                children = parent['children']
                if seg not in children:
                    if seg != data['page']:
                        children[seg] = deepcopy(base)
                    else:
                        children[seg] = data
                parent['filesFound'] += 1
                parent['pagesFound'] += 1
                parent = children[seg]

    # Recursively calculate total file count for each folder
    # and record credentials based on innermost protected directory
    query = f"""
        SELECT level_name, `path` FROM level_pages
        WHERE riddle = :riddle
            AND {level_condition}
            {'AND hidden  IS NOT TRUE' if not include_hidden  else ''}
            {'AND removed IS NOT TRUE' if not include_removed else ''}
    """
    values = {'riddle': alias, 'level_name': requested_level}
    pages_data = await database.fetch_all(query, values)
    credentials = await get_all_unlocked_credentials(alias, user)
    for data in pages_data:
        level_name = data['level_name']
        if (
            (not include_unlisted and not level_name) or
            (index_by_levels and (level_name not in pages))
        ):
            continue
        path = ''
        parent = pages[level_name]['/'] if index_by_levels else pages['/']
        segments = data['path'].split('/')[1:]
        for seg in segments:
            if unlocked_levels.get(level_name, {}).get('solveTime'):
                if not parent.get('pagesTotal'):
                    parent |= {'filesTotal': 0, 'pagesTotal': 0}
                parent['filesTotal'] += 1
                parent['pagesTotal'] += 1
            if not seg in parent['children']:
                # Avoid registering locked folders/pages
                break
            if not index_by_levels:
                parent['levels'][level_name] = True
            greatparent = parent
            parent = parent['children'][seg]
            path = path + '/' + seg
            parent['path'] = path
            if path in credentials:
                parent['username'] = credentials[path]['username']
                parent['password'] = credentials[path]['password']
            elif 'username' in greatparent:
                parent['username'] = greatparent['username']
                parent['password'] = greatparent['password']

    return jsonify(pages) if as_json else pages


@levels.get('/<alias>/levels/get-root-path')
async def get_root_path(alias: str):
    '''Get riddles' root URL path from DB.'''
    query = '''
        SELECT root_path FROM riddles
        WHERE alias = :alias
    '''
    values = {'alias': alias}
    root_path = await database.fetch_val(query, values)
    try:
        root_path = json.loads(root_path)[0]
    except json.decoder.JSONDecodeError:
        pass
    return root_path


@levels.route(
    '/<alias>/levels/rate/<level_name>/<int:rating>',
    methods=['DELETE', 'PUT'],
)
@requires_authorization
async def rate(alias: str, level_name: str, rating: int):
    '''Update level rating upon user giving new one.'''

    # Disallow phony ratings
    if not 1 <= rating <= 5:
        return 'Funny guy, eh? :)', 422

    # Get level's overall rating info
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle and name = :level_name
    '''
    values = {'riddle': alias, 'level_name': level_name}
    level = await database.fetch_one(query, values)
    if not level:
        return f"[{alias}] Level {level_name} not found.", 404

    # Get user's previous rating
    user = await discord.get_user()
    query = '''
        SELECT * FROM user_levels
        WHERE riddle = :riddle
            AND username = :username
            AND level_name = :level_name
    '''
    values = {
        'riddle': alias, 'username': user.name, 'level_name': level_name
    }
    user_level = await database.fetch_one(query, values)
    if not user_level or not user_level['completion_time']:
        return f"[{alias}] Level {level_name} not completed yet.", 403
    rating_prev = user_level['rating_given']

    # Calculate new average and count
    count = level['rating_count']
    total = 0
    if level['rating_avg']:
        total = count * level['rating_avg']
    if request.method == 'PUT':
        if not rating_prev:
            # User is adding a new vote
            total += rating
            count += 1
            status_code = 201
        else:
            # User is changing previous vote
            total = total - rating_prev + rating
            status_code = 200
        rating_time = datetime.utcnow()
    elif request.method == 'DELETE':
        if not rating_prev:
            # User is trying to remove nonexistent vote
            # (shouldn't happen under normal circumstances)
            status_code = 404
        else:
            # User is removing vote
            total -= rating
            count -= 1
            status_code = 200
        rating = rating_time = None
    average = total/count if count > 0 else 0

    # Update needed tables
    query = '''
        UPDATE user_levels
        SET rating_given = :rating_given, rating_time = :rating_time
        WHERE riddle = :riddle
            AND username = :username
            AND level_name = :level_name
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'level_name': level_name,
        'rating_given': rating,
        'rating_time': rating_time,
    }
    await database.execute(query, values)
    query = '''
        UPDATE levels
        SET rating_avg = :average, rating_count = :count
        WHERE riddle = :riddle AND name = :level_name
    '''
    values = {
        'riddle': alias,
        'level_name': level_name,
        'average': average,
        'count': count,       
    }
    await database.execute(query, values)

    # Return new rating data
    return f"{average} {count} {rating}", status_code


def absolute_paths(page_node: dict) -> Iterator[tuple[str, dict]]:
    '''Iterator for `levels.get_pages` resulting page tree.'''
    if not page_node['folder']:
        yield (page_node['path'], page_node)
        return
    for child in page_node['children'].values():
        yield from absolute_paths(child)
