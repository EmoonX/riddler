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
    
    user = await discord.fetch_user()
    base_values = {'riddle': alias,
            'name': user.name, 'disc': user.discriminator}

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
                        'AND username = :name AND discriminator = :disc ' \
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
                    # Level appears on list iff user reached its front page
                    query = 'SELECT username FROM user_pages ' \
                            'WHERE riddle = :riddle AND username = :name ' \
                                'AND discriminator = :disc AND path = :path'
                    values = {**base_values, 'path': level['path']}
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
                    # Get playe's current found files count for level
                    query = 'SELECT COUNT(*) AS count FROM user_pages ' \
                            'WHERE riddle = :riddle AND username = :name ' \
                                'AND discriminator = :disc ' \
                                'AND level_name = :level ' \
                            'GROUP BY riddle, username, ' \
                                'discriminator, level_name'
                    values = {**base_values, 'level': level['name']}
                    result = await database.fetch_one(query, values)
                    level['pages_found'] = result['count'] if result else 0
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
    user = await discord.fetch_user()
    query = 'SELECT level_name, path FROM user_pages ' \
            'WHERE riddle = :riddle ' \
                'AND username = :name AND discriminator = :disc'
    values = {'riddle': alias,
            'name': user.name, 'disc': user.discriminator}
    result = await database.fetch_all(query, values)
    paths = {}
    for row in result:
        row = dict(row)
        row['page'] = row['path'].rsplit('/', 1)[-1]
        row['folder'] = 0
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
        parent = pages[level]['/']
        segments = row['path'].split('/')[1:]
        for seg in segments:
            parent['files_total'] += 1
            if not seg in parent['children']:
                # Avoid registering locked folders/pages
                break                
            parent = parent['children'][seg]
    
    # def _extension_cmp(row: dict):
    #     '''Compare pages based firstly on their extension.
    #     Order is: folders first, then .htm, then the rest.'''
    #     page = row['page']
    #     index = page.rfind('.')
    #     if index == -1:
    #         return 'aaa' + page
    #     if page[index:] in ('.htm', '.html'):
    #         return 'aab' + page
    #     return 'zzz' + page[-3:]

    # # Sort pages from each folder
    # for folder in folders.values():
    #     folder['files'].sort(key=_extension_cmp)
    
    # # Save number of pages/files in folder
    # for folder in folders.values():
    #     folder['files_total'] = len(folder['files'])
    
    # Return JSON dump
    return json.dumps(pages)


@levels.route('/<alias>/levels/get-root-path', methods=['GET'])
async def get_root_path(alias: str):
    '''Get riddles's root URL path from DB.'''
    query = 'SELECT * FROM riddles ' \
            'WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    return result['root_path']


@levels.route('/<alias>/levels/rate/<level_name>/<int:rating>', methods=['GET'])
async def rate(alias: str, level_name: str, rating: int):
    '''Update level rating upon user giving new one.'''

    # Must not have logged out meanwhile
    user = await discord.fetch_user()
    if not user:
        return 'Unauthorized', 401
    
    # Disallow phony ratings :)
    if not (1 <= rating <= 5):
        return 'Funny guy, eh? :)', 403

    # Get user's previous rating
    query = 'SELECT * FROM user_levels ' \
            'WHERE riddle = :riddle ' \
                'AND username = :name AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'riddle': alias, 'name': user.name,
            'disc': user.discriminator, 'level_name': level_name}
    result = await database.fetch_one(query, values)
    if not result or not result['completion_time']:
        return 'Unauthorized', 401
    rating_prev = result['rating_given']

    # Get level's overall rating info
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle and name = :name'
    values = {'riddle': alias, 'name': level_name}
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
                'AND username = :name AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'rating': rating, 'riddle': alias,
            'name': user.name, 'disc': user.discriminator,
            'level_name': level_name}
    await database.execute(query, values)
    query = 'UPDATE levels SET rating_avg = :average, rating_count = :count ' \
            'WHERE riddle = :riddle AND name = :name'
    values = {'average': average, 'count': count,
            'riddle': alias, 'name': level_name}
    await database.execute(query, values)

    # Return new rating data
    text = '%s %s %s' % (average, count, rating)
    return text, 200
