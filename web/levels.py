from quart import Blueprint, session, render_template
from quart_discord import requires_authorization

from auth import discord
from util.db import database

# Create app blueprint
levels = Blueprint('levels', __name__)


@levels.route('/<riddle>/levels/')
@requires_authorization
async def level_list(riddle: str):
    '''Fetch list of levels, showing only desired public info.'''
    
    pages = None
    user = await discord.fetch_user()
    base_values = {'riddle': riddle,
            'name': user.name, 'disc': user.disc}
    if 'user' in session:
        # Get user's current level
        query = 'SELECT current_level FROM riddle_accounts WHERE ' \
                'riddle = :riddle AND ' \
                'username = :name AND discriminator = :disc'
        result = await database.fetch_one(query, base_values)
        current_level = result['current_level']

    # Get level dict (and mark them as unlocked and/or beaten appropriately)
    query = 'SELECT * FROM levels WHERE riddle = :riddle'
    result = await database.fetch_all(query, {'riddle': riddle})
    levels = {}
    for level in result:
        level = dict(level)
        if 'user' in session:
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
                # Level appears on level list iff user reached its front page
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
        values = {'riddle': riddle, 'id': level['name']}
        result = await database.fetch_all(query, values)
        level['users'] = [dict(level) for level in result]

        # Append level to its set subdict
        if not level['level_set'] in levels:
            levels[level['level_set']] = []
        levels[level['level_set']].append(level)
        

    if 'user' not in session:
        # First level is always visible
        levels[0]['unlocked'] = True
        levels[0]['image'] = 'enter.jpg'
        levels[0]['folders'] = None
        levels[0]['files_count'] = 0
        levels[0]['files_total'] = 0
    else:
        # Get dict of unlocked pages to file explorers
        await _get_user_unlocked_pages(riddle, user, levels)

    # return render_and_count('levels.htm', locals())
    # return render_and_count('levels.htm', locals())
    s = 'cipher'
    if riddle == 'rns':
        s = 'riddle'
    url = 'http://gamemastertips.com/cipher'
    if riddle == 'rns':
        url = 'https://rnsriddle.com/riddle'
    return await render_template('levels.htm', **locals())


async def _get_user_unlocked_pages(riddle: str, user, levels: dict):
    '''Build dict of pairs (folder -> list of pages),
    containing all user accessed pages ordered by extension.'''

    s = 'cipher'
    if riddle == 'rns':
        s = 'riddle'
    for level_set in levels.values():
        for level in level_set:
            # Get all pages (paths) user accessed in respective level
            query = 'SELECT path FROM user_pageaccess ' \
                    'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :id'
            values = {'riddle': riddle, 
                    'name': user.name, 'disc': user.discriminator,
                    'id': level['name']}
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
            values = {'riddle': riddle, 'id': level['name']}
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



@levels.route('/cipher/levels/rate/<level_name>/<rating>')
def rate(level_name, rating):
    '''Update level rating upon user giving new one.'''

    # Must not have logged out meanwhile
    if not 'user' in session:
        return '403'

    # Get user's previous rating
    cursor = get_cursor()
    cursor.execute('SELECT rating_given FROM user_levelcompletion '
            'WHERE username = %s AND level_name = %s',
            (session['user']['username'], level_name))
    aux = cursor.fetchone()
    if not aux:
        return 'FORBIDDEN OPERATION'
    rating_prev = aux['rating_given']

    # Get level's overall rating info
    cursor.execute('SELECT rating_avg, rating_count FROM levels '
            'WHERE id = %s', (level_name,))
    level = cursor.fetchone()

    # Calculate new average and count
    total = (level['rating_avg'] * level['rating_count'])
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
    average = (total / count) if count > 0 else 0

    # Update both user_levelcompletion and levels tables
    cursor.execute('UPDATE user_levelcompletion SET rating_given = %s '
            'WHERE username = %s AND level_name = %s',
            (rating, session['user']['username'], level_name))
    cursor.execute('UPDATE levels SET rating_avg = %s, rating_count = %s '
            'WHERE id = %s', (average, count, level_name))
    mysql.connection.commit()

    return str(average) + ' ' + str(count) + ' ' + str(rating)
