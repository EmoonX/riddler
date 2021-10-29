import json
from copy import deepcopy

from quart import Blueprint, render_template
from quart_discord import requires_authorization

import admin.admin as admin
from auth import discord
from util.db import database

# Create app blueprint
levels = Blueprint('levels', __name__)


@levels.route('/<alias>/levels')
@requires_authorization
async def level_list(alias: str):
    '''Fetch list of levels, showing only desired public info.'''
    
    user = await discord.get_user()
    base_values = {'riddle': alias,
            'username': user.name, 'disc': user.discriminator}

    # Get level dict (and mark them as unlocked and/or beaten appropriately)
    query = 'SELECT * FROM levels WHERE riddle = :riddle ' \
            'ORDER BY is_secret, `index`'
    result = await database.fetch_all(query, {'riddle': alias})
    levels = {}
    for level in result:
        level = dict(level)
        if user:
            # Retrieve level unlocking and completion data
            query = 'SELECT username, rating_given, completion_time ' \
                        'FROM user_levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :username AND discriminator = :disc ' \
                        'AND level_name = :level_name'
            values = {**base_values, 'level_name': level['name']}
            result = await database.fetch_one(query, values)
            
            # _, status = await admin.auth(alias)
            # if status == 200:
            if False:
                # If admin of riddle, everything is unlocked :)
                level['beaten'] = True
                level['unlocked'] = True
                if result:
                    level['rating_given'] = result['rating_given']
            else:
                level['beaten'] = (result and result['completion_time'])
                level['unlocked'] = level['beaten']

                if not level['beaten']:
                    # Level appears on list iff user reached its front page(s)
                    query = 'SELECT * FROM levels ' \
                                'WHERE riddle = :riddle AND name = :level_name'
                    values = {'riddle': alias, 'level_name': level['name']}
                    result = await database.fetch_one(query, values)
                    path = result['path']
                    query = 'SELECT * FROM user_pages ' \
                            'WHERE riddle = :riddle ' \
                                'AND username = :username ' \
                                'AND discriminator = :disc ' \
                                'AND (:path = `path` ' \
                                    'OR :path LIKE CONCAT(\'%"\', `path`, \'"%\'))'
                    values = {**base_values, 'path': path}
                    result = await database.fetch_one(query, values)
                    level['unlocked'] = (result is not None)
                else:
                    # Get level rating:
                    level['rating_given'] = result['rating_given']
                    
                    # Get total file count for level
                    query = 'SELECT COUNT(*) AS count FROM level_pages ' \
                            'WHERE riddle = :riddle AND level_name = :level ' \
                            'GROUP BY riddle, level_name'
                    values = {'riddle': alias, 'level': level['name']}
                    result = await database.fetch_one(query, values)
                    level['pages_total'] = result['count']
                
                if level['unlocked']:
                    if level['path'][0] == '[':
                        # If a multi-front level, pick up the first found
                        # front path for player purposes (like the image link)
                        query = 'SELECT * FROM user_pages ' \
                                'WHERE riddle = :riddle ' \
                                    'AND username = :username ' \
                                    'AND discriminator = :disc ' \
                                    'AND level_name = :level_name'
                        values = {**base_values, 'level_name': level['name']}
                        result = await database.fetch_all(query, values)
                        found_paths = set([row['path'] for row in result])
                        paths = level['path'].split('"')[1::2]
                        for path in paths:
                            if path in found_paths:
                                level['path'] = path
                                break
                        if level['path'][0] == '[':
                            level['path'] = ''  # safeguard

                    # Get playe's current found pages count for level
                    query = 'SELECT `path` FROM user_pages ' \
                            'WHERE riddle = :riddle ' \
                                'AND username = :username ' \
                                'AND discriminator = :disc ' \
                                'AND level_name = :level '
                    values = {**base_values, 'level': level['name']}
                    result = await database.fetch_all(query, values)
                    if result:
                        found_pages = [row['path'] for row in result]
                        level['pages_found'] = len(found_pages)

                        # Get topmost folder by longest
                        # common prefix of all found level pages
                        longest_prefix = '%s/' % \
                                found_pages[0].rsplit('/', 1)[0]
                        for path in found_pages[1:]:
                            k = min(len(path), len(longest_prefix))
                            for i in range(k):
                                if path[i] != longest_prefix[i]:
                                    longest_prefix = longest_prefix[:i]
                                    break
                        level['topmost_folder'] = longest_prefix
                    
        else:
            level['beaten'] = False
            level['unlocked'] = False

        # Register list of users currently working on level
        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle and level_name = :name ' \
                    'AND completion_time IS NULL'
        values = {'riddle': alias, 'name': level['name']}
        result = await database.fetch_all(query, values)
        level['users'] = [dict(level) for level in result]

        # Append level to its set subdict
        if not level['level_set'] in levels:
            levels[level['level_set']] = []
        levels[level['level_set']].append(level)

    return await render_template('levels.htm', **locals())


@levels.route('/<alias>/levels/get-pages', methods=['GET'])
@requires_authorization
async def get_pages(alias: str) -> str:
    '''Return a recursive JSON of all riddle folders and pages.'''
    
    # Build dict of (level -> paths) from user database data
    user = await discord.get_user()
    query = 'SELECT level_name, path, access_time FROM user_pages ' \
            'WHERE riddle = :riddle ' \
                'AND username = :username AND discriminator = :disc ' \
            'ORDER BY SUBSTRING_INDEX(`path`, ".", -1)'
    values = {'riddle': alias,
            'username': user.name, 'disc': user.discriminator}
    result = await database.fetch_all(query, values)
    paths = {}
    for row in result:
        row = dict(row)
        row['page'] = row['path'].rsplit('/', 1)[-1]
        row['folder'] = 0
        row['access_time'] = row['access_time'] \
                .strftime('%Y/%b/%d at %H:%M (UTC)')
        level = row['level_name']
        if not level in paths:
            paths[level] = []
        paths[level].append(row)

    # Build recursive dict of folders and files
    base = {'children': {}, 'folder': 1,
            'files_found': 0, 'files_total': 0}
    pages = {}
    for level, level_paths in paths.items():
        pages[level] = {'/': deepcopy(base)}
        for row in level_paths:
            parent = pages[level]['/']
            segments = row['path'].split('/')[1:]
            for seg in segments:
                children = parent['children']
                if seg not in children:
                    if seg != row['page']:
                        children[seg] = deepcopy(base)
                    else:
                        children[seg] = row
                parent['files_found'] += 1
                parent = children[seg]
    
    # Get recursively total file count for each folder
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = :riddle '
    result = await database.fetch_all(query, {'riddle': alias})
    for row in result:
        level = row['level_name']
        if not level or level not in pages:
            continue
        path = ''
        parent = pages[level]['/']
        segments = row['path'].split('/')[1:]
        for seg in segments:
            parent['files_total'] += 1
            if not seg in parent['children']:
                # Avoid registering locked folders/pages
                break
            parent = parent['children'][seg]
            path = '%s/%s' % (path, seg)
            parent['path'] = path
    
    # Return JSON dump
    return json.dumps(pages)


@levels.route('/<alias>/levels/get-root-path', methods=['GET'])
async def get_root_path(alias: str):
    '''Get riddles' root URL path from DB.'''
    query = 'SELECT * FROM riddles ' \
            'WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    return result['root_path']


@levels.route('/<alias>/levels/rate/<level_name>/<int:rating>', methods=['GET'])
async def rate(alias: str, level_name: str, rating: int):
    '''Update level rating upon user giving new one.'''

    # Must not have logged out meanwhile
    user = await discord.get_user()
    if not user:
        return 'Unauthorized', 401
    
    # Disallow phony ratings :)
    if not (1 <= rating <= 5):
        return 'Funny guy, eh? :)', 403

    # Get user's previous rating
    query = 'SELECT * FROM user_levels ' \
            'WHERE riddle = :riddle ' \
                'AND username = :username AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'riddle': alias,
            'username': user.name, 'disc': user.discriminator,
            'level_name': level_name}
    result = await database.fetch_one(query, values)
    if not result or not result['completion_time']:
        return 'Unauthorized', 401
    rating_prev = result['rating_given']

    # Get level's overall rating info
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle and name = :level_name'
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
    query = 'UPDATE user_levels ' \
            'SET rating_given = :rating ' \
            'WHERE riddle = :riddle ' \
                'AND username = :username AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'rating': rating, 'riddle': alias,
            'username': user.name, 'disc': user.discriminator,
            'level_name': level_name}
    await database.execute(query, values)
    query = 'UPDATE levels ' \
            'SET rating_avg = :average, rating_count = :count ' \
            'WHERE riddle = :riddle AND name = :level_name'
    values = {'average': average, 'count': count,
            'riddle': alias, 'level_name': level_name}
    await database.execute(query, values)

    # Return new rating data
    text = '%s %s %s' % (average, count, rating)
    return text, 200
