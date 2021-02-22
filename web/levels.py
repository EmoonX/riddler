from quart import Blueprint, session, render_template
from quart_discord import requires_authorization

import admin.admin as admin
from auth import discord, User
from util.db import database

# Create app blueprint
levels = Blueprint('levels', __name__)


@levels.route('/<alias>/levels/')
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
            _, status = await admin.auth(alias)
            if status == 200:
                # If admin of riddle, everything is unlocked :)
                level['beaten'] = True
                level['unlocked'] = True
            
            else:
                # Retrieve level unlocking and completion data
                table = 'user_levelcompletion' if not level['is_secret'] \
                        else 'user_secrets'
                query = ('SELECT username, rating_given FROM %s ' % table) + \
                        'WHERE riddle = :riddle ' \
                        'AND username = :name AND level_name = :id ' \
                        'AND discriminator = :disc'
                values = {**base_values, 'id': level['name']}
                result = await database.fetch_one(query, values)
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
        
    if not user:
        # First level is always visible
        levels[0]['unlocked'] = True
        levels[0]['image'] = 'enter.jpg'
        levels[0]['folders'] = None
        levels[0]['files_count'] = 0
        levels[0]['files_total'] = 0
    else:
        # Get dict of pages to explorers
        await _get_user_unlocked_pages(alias, user, levels)

    # return render_and_count('levels.htm', locals())
    # return render_and_count('levels.htm', locals())
    s = 'cipher'
    if alias == 'rns':
        s = 'riddle'
    url = 'http://gamemastertips.com/cipher'
    if alias == 'rns':
        url = 'https://rnsriddle.com/riddle'
    return await render_template('levels.htm', **locals())


async def _get_user_unlocked_pages(alias: str, user: User, levels: dict):
    '''Build dict of pairs (folder -> list of pages),
    containing all user accessed pages ordered by extension.'''

    s = 'cipher'
    if alias == 'rns':
        s = 'riddle'
    for level_set in levels.values():
        for level in level_set:
            _, status = await admin.auth(alias)
            if status == 200:
                query = 'SELECT path FROM level_pages ' \
                        'WHERE riddle = :riddle AND level_name = :name'
                values = {'riddle': alias, 'name': level['name']}
            else:
                # Get all pages (paths) user accessed in respective level
                query = 'SELECT path FROM user_pageaccess ' \
                        'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND level_name = :level_name'
                values = {'riddle': alias, 
                        'name': user.name, 'disc': user.discriminator,
                        'level_name': level['name']}
            result = await database.fetch_all(query, values)
            paths = [(s + '/' + row['path']) for row in result]

            # Build dict of pairs (folder -> list of paths)
            level['folders'] = {}
            folders = level['folders']
            for path in paths:
                folder, page = path.rsplit('/', 1)
                if not folder in folders:
                    folders[folder] = []
                folders[folder].append(page)

            # Save number of pages/files in folder
            level['files_count'] = {}
            for folder in folders:
                level['files_count'][folder] = len(folders[folder])

            def extension_cmp(page: str):
                '''Compare pages based firstly on their extension.
                Order is: folders first, then .htm, then the rest.'''
                if len(page) < 4 or page[-4] != '.':
                    return 'aaa'
                if page[-3:] == 'htm':
                    return 'aab'
                return page[-3:]

            # Add folders to directories
            aux = {}
            for folder in folders:
                f = folder
                while f.count('/'):
                    parent, name = f.rsplit('/', 1)
                    if not parent in aux:
                        aux[parent] = set()
                    aux[parent].add(name)
                    f = parent
            for folder, names in aux.items():
                if not folder in folders:
                    folders[folder] = []
                folders[folder].extend(names)

            # Sort pages from each folder
            for _, pages in folders.items():
                pages.sort(key=extension_cmp)

            # Count total number of pages (unlocked or not) in each folder
            level['files_total'] = {}
            query = 'SELECT path FROM level_pages WHERE ' \
                    'riddle = :riddle AND level_name = :id'
            values = {'riddle': alias, 'id': level['name']}
            result = await database.fetch_all(query, values)
            paths = [row['path'] for row in result]
            for path in paths:
                folder = s + '/' + path.rsplit('/', 1)[0]
                if not folder in folders:
                    # Avoid spoiling things in HTML!
                    continue
                if not folder in level['files_total']:
                    level['files_total'][folder] = 0
                level['files_total'][folder] += 1



@levels.route('/<alias>/levels/rate/<level_name>/<rating>')
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
