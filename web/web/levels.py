from collections.abc import Iterator
from copy import deepcopy

from quart import Blueprint, jsonify, render_template
from quartcord import requires_authorization

from admin.admin_auth import is_admin_of
from auth import discord
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
            if level['path'][0] == '[':
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
                paths = level['path'].split('"')[1::2]
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
                WHERE riddle = :riddle AND level_name = :level
                GROUP BY riddle, level_name
            '''
            values = {'riddle': alias, 'level': level['name']}
            level['pages_total'] = await database.fetch_val(query, values)

        # Get player's current found pages count for level
        query = '''
            SELECT `path` FROM user_pages
            WHERE riddle = :riddle
                AND username = :username
                AND level_name = :level
        '''
        values = base_values | {'level': level['name']}
        pages_data = await database.fetch_all(query, values)
        if pages_data:
            found_pages = [row['path'] for row in pages_data]
            level['pages_found'] = len(found_pages)

            # Get topmost folder by longest
            # common prefix of all found level pages
            longest_prefix = found_pages[0].rsplit('/', 1)[0] + '/'
            for path in found_pages[1:]:
                k = min(len(path), len(longest_prefix))
                for i in range(k):
                    if path[i] != longest_prefix[i]:
                        longest_prefix = longest_prefix[:i]
                        break
            level['topmost_folder'] = longest_prefix

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
    
    async def _add_credentials(level: dict):
        '''Add credentials (if any) for level's front path.'''
        for folder_path in reversed(credentials):
            # Iterate in reverse to pick the innermost dir
            if level['path'].startswith(folder_path):
                level |= credentials[folder_path]
                return
    
    # Get riddle level data
    query = '''
        SELECT *, EXISTS(
            SELECT level_name FROM level_requirements lr
            WHERE riddle = :riddle AND lv.name = lr.level_name
        ) AS has_requirements
        FROM levels lv
        WHERE riddle = :riddle
        ORDER BY is_secret, `index`
    '''
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    levels_list = [dict(row) for row in result]
    credentials = await _get_credentials(alias)    

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
        await _add_credentials(level)
        levels_dict[level['level_set']].append(level)

    # Pass better named dict to template
    context = locals() | {'levels': levels_dict}
    context.pop('levels_dict')
    return await render_template('levels.htm', **context)


@levels.get('/<alias>/levels/get-pages')
@levels.get('/<alias>/levels/get-pages/<requested_level>')
@requires_authorization
async def get_pages(
    alias: str, requested_level: str = '%',
    admin: bool = False, as_json: bool = True
) -> str:
    '''Return a recursive JSON of all user level folders and pages.
    If a level is specified, return only pages from that level instead.'''

    admin &= await is_admin_of(alias)

    # Fetch and build general unlocked level data
    unlocked_levels = {}
    values = {
        'riddle': alias,
        'level_name': requested_level,
    }
    if admin:
        query = '''
            SELECT *, current_timestamp() AS completion_time FROM levels
            WHERE riddle = :riddle AND name LIKE :level_name
        '''
    else:
        user = await discord.get_user()
        query = '''
            SELECT lv.name, lv.path, lv.image, lv.answer, ul.completion_time
            FROM levels lv INNER JOIN user_levels ul
                ON lv.riddle = ul.riddle AND lv.name = ul.level_name
            WHERE lv.riddle = :riddle
                AND username = :username
                AND lv.name LIKE :level_name
        '''
        values |= {'username': user.name}
    result = await database.fetch_all(query, values)
    for row in result:
        level_name = row['name']
        unlocked_levels[level_name] = {
            'frontPage': row['path'],
            'image': row['image'],
        }
        if row['completion_time']:
            unlocked_levels[level_name] |= {'answer': row['answer']}

    # Fetch user page data
    if admin:
        query = '''
            SELECT *, current_timestamp() AS access_time FROM level_pages
            WHERE riddle = :riddle AND level_name LIKE :level_name
        '''
    else:
        query = '''
            SELECT level_name, path, access_time FROM user_pages
            WHERE riddle = :riddle
                AND username = :username
                AND level_name LIKE :level_name
            ORDER BY SUBSTRING_INDEX(`path`, ".", -1)
        '''
    result = await database.fetch_all(query, values)
    user_page_data = [dict(row) for row in result]

     # Build dict of (level -> paths)
    ordered_levels = await get_ordered_levels(alias)
    paths = {level_name: [] for level_name in ordered_levels}
    for data in user_page_data:
        data['page'] = data['path'].rsplit('/', 1)[-1]
        data['folder'] = 0
        data['access_time'] = \
            data['access_time'].strftime('%Y/%b/%d at %H:%M (UTC)')
        paths[data['level_name']].append(data)

    # Build recursive dict of folders and files
    base = {
        'children': {}, 'folder': 1, 'path': '',
        'filesFound': 0, 'filesTotal': 0
    }
    pages = {}
    for level_name, level_paths in paths.items():
        if not level_paths:
            continue
        pages[level_name] = {'/': deepcopy(base)}
        pages[level_name] |= unlocked_levels.get(level_name, {})
        for data in level_paths:
            parent = pages[level_name]['/']
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
                parent = children[seg]
    
    # Recursively calculate total file count for each folder
    # and record credentials based on innermost protected directory
    query = '''
        SELECT level_name, `path` FROM level_pages
        WHERE riddle = :riddle AND level_name LIKE :level_name
    '''
    values = {'riddle': alias, 'level_name': requested_level}
    pages_data = await database.fetch_all(query, values)
    credentials = await _get_credentials(alias)
    for data in pages_data:
        level = data['level_name']
        if not level or level not in pages:
            continue
        path = ''
        parent = pages[level]['/']
        segments = data['path'].split('/')[1:]
        for seg in segments:
            parent['filesTotal'] += 1
            if not seg in parent['children']:
                # Avoid registering locked folders/pages
                break
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


@levels.get('/<alias>/levels/rate/<level_name>/<int:rating>')
async def rate(alias: str, level_name: str, rating: int):
    '''Update level rating upon user giving new one.'''

    # Must not have logged out meanwhile
    user = await discord.get_user()
    if not user:
        return 'Unauthorized', 401

    # Disallow phony ratings :)
    if not 1 <= rating <= 5:
        return 'Funny guy, eh? :)', 403

    # Get user's previous rating
    query = '''
        SELECT * FROM user_levels
        WHERE riddle = :riddle
            AND username = :username
            AND level_name = :level_name
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'level_name': level_name,
    }
    played_level = await database.fetch_one(query, values)
    if not played_level or not played_level['completion_time']:
        return 'Unauthorized', 401
    rating_prev = played_level['rating_given']

    # Get level's overall rating info
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle and name = :level_name
    '''
    values = {'riddle': alias, 'level_name': level_name}
    level = await database.fetch_one(query, values)

    # Calculate new average and count
    total = 0
    if level['rating_avg']:
        total = level['rating_avg'] * level['rating_count']
    count = level['rating_count']
    rating = int(rating)
    if not rating_prev:
        # User is adding a new vote
        total += rating
        count += 1
    elif rating != rating_prev:
        # User is changing previous vote
        total = total - rating_prev + rating
    else:
        # User is removing vote
        total -= rating
        count -= 1
        rating = None
    average = (total / count) if (count > 0) else 0

    # Update needed tables
    query = '''
        UPDATE user_levels SET rating_given = :rating
        WHERE riddle = :riddle
            AND username = :username
            AND level_name = :level_name
    '''
    values = {
        'rating': rating,
        'riddle': alias,
        'username': user.name,
        'level_name': level_name,
    }
    await database.execute(query, values)
    query = '''
        UPDATE levels
        SET rating_avg = :average, rating_count = :count
        WHERE riddle = :riddle AND name = :level_name
    '''
    values = {
        'average': average, 'count': count,
        'riddle': alias, 'level_name': level_name
    }
    await database.execute(query, values)

    # Return new rating data
    text = ' '.join(map(str, (average, count, rating)))
    return text, 200


def absolute_paths(page_node: dict) -> Iterator[tuple[str, dict]]:
    '''Iterator for `levels.get_pages` resulting page tree.'''
    if not page_node['folder']:
        yield (page_node['path'], page_node)
        return
    for child in page_node['children'].values():
        yield from absolute_paths(child)


async def _get_credentials(alias: str) -> dict:
    '''Fetch dict of level credentials (folder_path -> un/pw).'''
    
    query = '''
        SELECT * FROM riddle_credentials
        WHERE riddle = :riddle
    '''
    result = await database.fetch_all(query, {'riddle': alias})
    credentials = {
        row['folder_path']: {
            'username': row['username'],
            'password': row['password'],
        }
        for row in result
    }
    
    return credentials
