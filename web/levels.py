import json
from copy import deepcopy

from quart import Blueprint, render_template
from quart_discord import requires_authorization

import admin.admin as admin
from auth import User, discord
from ipc import web_ipc
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
    query = 'SELECT * FROM levels WHERE riddle = :riddle'
    result = await database.fetch_all(query, {'riddle': alias})
    levels = {}
    for level in result:
        level = dict(level)
        if user:
            # Retrieve level unlocking and completion data
            table = 'user_levelcompletion' if not level['is_secret'] \
                    else 'user_secrets'
            query = ('SELECT username, rating_given FROM %s ' % table) + \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND level_name = :level_name'
            values = {**base_values, 'level_name': level['name']}
            result = await database.fetch_one(query, values)
            
            _, status = await admin.auth(alias)
            if status == 200:
                # If admin of riddle, everything is unlocked :)
                level['beaten'] = True
                level['unlocked'] = True
                if result:
                    level['rating_given'] = result['rating_given']
            else:
                level['beaten'] = (result is not None)
                level['unlocked'] = level['beaten']

                if not level['beaten']:
                    # Level appears on list iff user reached its front page
                    query = 'SELECT username FROM user_pageaccess ' \
                            'WHERE riddle = :riddle ' \
                            'AND username = :name AND discriminator = :disc ' \
                            'AND path = :path'
                    values = {**base_values, 'path': level['path']}
                    result = await database.fetch_one(query, values)
                    level['unlocked'] = (result is not None)
                else:
                    level['rating_given'] = result['rating_given']

        else:
            level['beaten'] = False
            level['unlocked'] = False

        # Register list of users currently on level
        query = 'SELECT * FROM riddle_accounts ' \
                'WHERE riddle = :riddle and current_level = :id'
        values = {'riddle': alias, 'id': level['name']}
        result = await database.fetch_all(query, values)
        level['users'] = [dict(level) for level in result]

        # Append level to its set subdict
        if not level['level_set'] in levels:
            levels[level['level_set']] = []
        levels[level['level_set']].append(level)

    # return render_and_count('levels.htm', locals())
    # return render_and_count('levels.htm', locals())
    s = 'cipher'
    if alias == 'rns':
        s = 'riddle'
    url = 'http://gamemastertips.com/cipher'
    if alias == 'rns':
        url = 'https://rnsriddle.com/riddle'
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    riddle = dict(await database.fetch_one(query, {'alias': alias}))
    url = await web_ipc.request('get_riddle_icon_url',
            name=riddle['full_name'])
    riddle['icon_url'] = url
    return await render_template('levels.htm', **locals())


@levels.route('/<alias>/levels/get-pages', methods=['GET'])
@requires_authorization
async def get_pages(alias: str) -> str:
    '''Return a recursive JSON of all riddle folders and pages.'''
    
    # Build dict of (level -> paths) from user database data
    user = await discord.fetch_user()
    query = 'SELECT level_name, path FROM user_pageaccess ' \
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
    base = {'children': {}, 'folder': 1}
    pages = {}
    for level, level_paths in paths.items():
        query = 'SELECT riddle, level_name, COUNT(*) as total ' \
                    'FROM level_pages ' \
                'WHERE riddle = :riddle AND level_name = :level ' \
                'GROUP BY riddle, level_name'
        values = {'riddle': alias, 'level': level}
        result = await database.fetch_one(query, values)
        print(result)
        pages[level] = {'/': deepcopy(base),
                'files_found': len(level_paths),
                'files_total': result['total']}
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
                parent = children[seg]
    
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


@levels.route('/<alias>/levels/rate/<level_name>/<rating>', methods=['GET'])
async def rate(alias: str, level_name: str, rating: float):
    '''Update level rating upon user giving new one.'''

    # Must not have logged out meanwhile
    user = await discord.fetch_user()
    if not user:
        return 'Unauthorized', 401

    # Get user's previous rating
    query = 'SELECT * FROM user_levelcompletion ' \
            'WHERE riddle = :riddle ' \
                'AND username = :name AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'riddle': alias, 'name': user.name,
            'disc': user.discriminator, 'level_name': level_name}
    result = await database.fetch_one(query, values)
    if not result:
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

    # Update both user_levelcompletion and levels tables
    query = 'UPDATE user_levelcompletion SET rating_given = :rating ' \
            'WHERE riddle = :riddle ' \
                'AND username = :name AND discriminator = :disc ' \
                'AND level_name = :level_name'
    values = {'rating': rating, 'riddle': alias, 'name': user.name,
            'disc': user.discriminator, 'level_name': level_name}
    await database.execute(query, values)
    query = 'UPDATE levels SET rating_avg = :average, rating_count = :count ' \
            'WHERE riddle = :riddle AND name = :name'
    values = {'average': average, 'count': count,
            'riddle': alias, 'name': level_name}
    await database.execute(query, values)

    # Return new rating data
    text = '%s %s %s' % (average, count, rating)
    return text, 200
