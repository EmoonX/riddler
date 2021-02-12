from urllib.parse import urlparse
from datetime import datetime

from quart import Blueprint, request, session, jsonify
from quart_discord.models import User

from players.auth import discord
from ipc import web_ipc
from util.db import database

# Create app blueprint
process = Blueprint('process', __name__)

# Dict of pairs (level rank -> (points, color))
level_ranks = {
    'D': (50, 'cornflowerblue'),
    'C': (100, 'lawngreen'),
    'B': (200, 'gold'),
    'A': (400, 'crimson'),
    'S': (1000, 'lightcyan')
}
for rank, pair in level_ranks.items():
    level_ranks[rank] = {'points': pair[0], 'color': pair[1]}


@process.route('/process/', methods=['POST', 'OPTIONS'])
async def process_url():
    '''Process an URL sent by browser extension.'''

    response = None
    status = None
    if not await discord.authorized:
        # Unauthorized, return status 401
        response = jsonify({'message': 'Unauthorized'})
        status = 401 if request.method == 'POST' else 200
    else:
        # Receive URL from request and parse it
        url_list = (await request.data).decode('utf-8')
        url_list = url_list.split('\n')

        if request.method =='POST':
            for url in url_list:
                # Parse path from url
                parsed = urlparse(url)
                path = parsed.path
                if not path:
                    continue

                # If no explicit file, add 'index.htm' to end of path
                dot_index = path.rfind('.')
                if dot_index == -1:
                    if path[-1] != '/':
                        path += '/'
                    path += 'index.htm'
                
                # Store session riddle user data
                riddle = 'cipher'
                if 'rnsriddle.com' in url:
                    riddle = 'rns'
                user = await discord.fetch_user()

                print('[%s] Received path "%s" from %s#%s'
                        % (riddle, path, user.name, user.discriminator))

                query = 'SELECT * FROM riddle_accounts ' \
                        'WHERE riddle = :riddle AND ' \
                            'username = :name AND discriminator = :disc'
                values = {'riddle': riddle,
                        'name': user.name, 'disc': user.discriminator}
                result = await database.fetch_one(query, values)
                if not result:
                    # If user don't have a riddle account yet, create it
                    await _create_riddle_account(riddle, user)
                # Register player's riddle session data
                await _get_player_riddle_data(riddle, user)
                
                # Process page and register player info on database
                if riddle == 'cipher':
                    path = path.replace('/cipher/', '')
                else:
                    path = path.replace('/riddle/', '')
                points = await _process_page(riddle, path)

                # Send unlocking request to bot's IPC server (if everything's good)
                await web_ipc.request('unlock',
                        alias=riddle, player_id=user.id,
                        path=path, points=points)
        
        # Successful response
        response = jsonify({'message': 'Success!'})
        status = 200
    
    # (Chrome security issues) Allow CORS to be requested from other domains
    if request.referrer:
        ref = request.referrer[:-1]
        response.headers.add('Access-Control-Allow-Origin', ref)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Headers', 'Cookie')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    
    # Return response
    return response, status


async def _create_riddle_account(riddle: str, user: User):
    '''Insert new user riddle account on riddle_accounts table.'''
    query = 'INSERT INTO riddle_accounts ' \
            '(riddle, username, discriminator) ' \
            'VALUES (:riddle, :name, :disc)'
    values = {'riddle': riddle,
            'name': user.name, 'disc': user.discriminator}
    await database.execute(query, values)


async def _get_player_riddle_data(riddle: str, user: User):
    '''Save player's riddle data to session.'''
    query = 'SELECT * FROM riddle_accounts ' \
            'WHERE riddle = :riddle ' \
            'AND username = :name AND discriminator = :disc'
    values = {'riddle': riddle,
            'name': user.name, 'disc': user.discriminator}
    result = await database.fetch_one(query, values)
    session[riddle] = dict(result)


async def _process_page(riddle: str, path: str):
    '''Process level pages (one or more folders deep).
    Return points gotten (if level completed, else 0).'''

    # Basic player info
    username = session['user']['username']
    disc = session['user']['discriminator']

    async def _get_user_level_row(level: dict, table: str):
        '''Return row corresponding to user and level register on table.'''

        query = ('SELECT * FROM %s ' % table) + \
                'WHERE riddle = :riddle AND username = :name ' \
                'AND discriminator = :disc AND level_name = :level_name'
        values = {'riddle': riddle, 'name':
                username, 'disc': disc, 'level_name': level['name']}
        row = await database.fetch_one(query, values)
        return row
    
    async def _update_info(level: dict):
        '''Update level-related tables.'''

        # Update global user completion count
        query = 'UPDATE levels ' \
                'SET completion_count = completion_count + 1 ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': riddle, 'name': level['name']}
        await database.execute(query, values)

        # Update user, country and global scores
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle AND username = :name'
        values = {'points': points, 
                'riddle': riddle, 'name': username}
        await database.execute(query, values)
        # cursor.execute("UPDATE countries "
        #         "SET total_score = total_score + %s "
        #         "WHERE alpha_2 = %s",
        #         (points, session['user']['country']))
        query = 'UPDATE accounts ' \
                'SET global_score = global_score + :points ' \
                'WHERE username = :name'
        values = {'points': points, 'name': username}
        await database.execute(query, values)

    async def _register_completion(level: dict, points: int):
        '''Register level completion and update all needed tables.'''

        # Check if level has been completed
        row = await _get_user_level_row(level, 'user_levelcompletion')
        if row:
            return
        
        # Register level completion in designated table
        time = datetime.utcnow()
        count = session[riddle]['cur_hit_counter']
        query = 'INSERT INTO user_levelcompletion ' \
                '(riddle, username, discriminator, ' \
                    'level_name, completion_time, page_count) ' \
                'VALUES (:riddle, :name, :disc, :level_name, :time, :count)'
        values = {'riddle': riddle, 'name': username, 'disc': disc,
                'level_name': level['name'], 'time': time, 'count': count}
        await database.execute(query, values)

        # Update level-related tables
        await _update_info(level)    
        
        # Update current_level count and reset user's page count
        name_next = '%02d' % (int(level['name']) + 1)
        query = 'UPDATE riddle_accounts ' \
                'SET current_level = :name_next, cur_hit_counter = 0 ' \
                'WHERE riddle = :riddle AND ' \
                    'username = :name AND discriminator = :disc'
        values = {'name_next': name_next, 'riddle': riddle,
                'name': username, 'disc': disc}
        await database.execute(query, values)

        # Also Update session info
        session[riddle]['current_level'] = current_level
        session[riddle]['cur_hit_counter'] = 0

        # Update countries table too
        # cursor.execute("UPDATE countries "
        #         "SET highest_level = GREATEST(highest_level, %s) "
        #         "WHERE alpha_2 = %s",
        #         (current_level, session['user']['country']))
        # if int(current_level) > get_level_count()[0]:
        #     cursor.execute("UPDATE countries "
        #             "SET winners_count = winners_count + 1 "
        #             "WHERE alpha_2 = %s",
        #             (session['user']['country'],))
    
    async def _register_secret_found(level: dict, points: int):
        '''Register secret finding on the respective table.'''

        # Register new secret if not yet been found
        row = await _get_user_level_row(level, 'user_secrets')
        if not row:
            time = datetime.utcnow()
            query = 'INSERT INTO user_secrets ' \
                    '(riddle, username, discriminator, ' \
                        'level_name, find_time) ' \
                    'VALUES (:riddle, :name, :disc, ' \
                        ':level_name, :time)'
            values = {'riddle': riddle, 'name': username, 'disc': disc,
                    'level_name': level['name'], 'time': time}
            await database.execute(query, values)
            return
        
    async def _register_secret_completion(level: dict, points: int):
        '''Register secret completion and update all needed tables.'''

        # Check if secret has been already completed
        row = await _get_user_level_row(level, 'user_secrets')
        if row and row['completion_time']:
            return
        
        # Register level completion in designated table
        time = datetime.utcnow()
        query = 'UPDATE user_secrets ' \
                'SET completion_time = :time ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :level_name'
        values = {'time': time, 'riddle': riddle,
                'name': username, 'disc': disc, 'level_name': level['name']}
        await database.execute(query, values)

        # Update level-related tables
        await _update_info(level)

        # Update countries table too
        # cursor.execute("UPDATE countries "
        #         "SET highest_level = GREATEST(highest_level, %s) "
        #         "WHERE alpha_2 = %s",
        #         (current_level, session['user']['country']))
        # if int(current_level) > get_level_count()[0]:
        #     cursor.execute("UPDATE countries "
        #             "SET winners_count = winners_count + 1 "
        #             "WHERE alpha_2 = %s",
        #             (session['user']['country'],))            

    def _has_access():
        """Check if user can access level_name,
                having reached current_level so far."""
        return True
        # # Admins can access everything!
        # if session['user']['rank'] == 'Site Administrator':
        #     return True

        # if "Status" in level_name:
        #     # Secret level, check previous id in respective table
        #     cursor = get_cursor()
        #     cursor.execute("SELECT * FROM user_secretsfound "
        #             "WHERE level_name = %s", (level_name,))
        #     secret_found = cursor.fetchone()
        #     return secret_found

        # # Return if level is *at most* the current_level
        # return int(level_name) <= int(current_level)
    
    # Check if it's not an txt/image/video/etc
    dot_index = path.rfind('.')
    extension = path[(dot_index + 1):]
    is_page = 'htm' in extension or 'php' in extension

    if is_page:
        # If a normal page, increment user current hit counter
        query = 'UPDATE riddle_accounts ' \
                'SET cur_hit_counter = cur_hit_counter + 1 ' \
                'WHERE riddle = :riddle ' \
                'AND username = :name AND discriminator = :disc'
        values = {'riddle': riddle,
                'name': session['user']['username'],
                'disc': session['user']['discriminator']}
        await database.execute(query, values)
        session[riddle]['cur_hit_counter'] += 1

        # Also update riddle hit counter
        query = 'UPDATE general_info ' \
                'SET hit_counter = hit_counter + 1 ' \
                'WHERE riddle = :riddle '
        await database.execute(query, {'riddle': riddle})

    # Get user's current reached level and requested level number
    current_name = session[riddle]['current_level']
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = :riddle AND path = :path'
    values = {'riddle': riddle, 'path': path}
    page = await database.fetch_one(query, values)
    if not page:
        # Page not found!
        return
    level_name = page['level_name']

    # if is_htm:
    # Get user's current level info from DB
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND name = :name'
    values = {'riddle': riddle, 'name': current_name}
    current_level = await database.fetch_one(query, values)

    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND name = :name'
    values = {'riddle': riddle, 'name': level_name}
    level = await database.fetch_one(query, values)

    # If user entered a correct and new answer, register time on DB
    #if int(current_level) <= total and path == level["answer"]:
    points = 0
    if current_name == '00' or path == current_level['answer']:
        rank = current_level['rank']
        points = level_ranks[rank]['points']
        await _register_completion(current_level, points)
    else:
        # Check if a secret level has been found
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                'AND path = :path'
        values = {'riddle': riddle, 'path': path}
        level = await database.fetch_one(query, values)
        if level:
            await _register_secret_found(level, points)
        else:
            # Otherwise, check if a secret level was beaten
            query = 'SELECT * FROM levels ' \
                    'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                    'AND answer = :answer'
            values = {'riddle': riddle, 'answer': path}
            level = await database.fetch_one(query, values)
            if level:
                rank = level['rank']
                points = level_ranks[rank]['points']
                await _register_secret_completion(level, points)

    # if not has_access():
    #     # Forbid user from accessing any level further than permitted
    #     abort(403)

    # Register into database new page access (if applicable)
    tnow = datetime.utcnow()
    query = 'INSERT IGNORE INTO user_pageaccess ' \
            'VALUES (:riddle, :name, :disc, :id, :path, :time)'
    values = {'riddle': riddle,
            'name': session['user']['username'],
            'disc': session['user']['discriminator'],
            'id': level_name, 'path': path, 'time': tnow}
    await database.execute(query, values)

    # Check if it's an achievement page
    query = 'SELECT * FROM achievements ' \
            'WHERE riddle = :riddle AND path = :path'
    values = {'riddle': riddle, 'path': path}
    cheevo = await database.fetch_one(query, values)
    if cheevo:
        # If positive, add it to user's collection
        time = datetime.utcnow()
        query = 'INSERT INTO user_achievements ' \
                'VALUES (:riddle, :name, :disc, :title, :time)'
        values = {'riddle': riddle,
                'name': username, 'disc': disc,
                'title': cheevo['title'], 'time': time}
        await database.execute(query, values)
        print('> [%s] %s got cheevo %s!' %
                (riddle, username, cheevo['title']))

        # Also Update user, country and global scores
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'points': cheevo['points'], 'riddle': riddle,
                'name': username, 'disc': disc}
        await database.execute(query, values)
        # cursor.execute("UPDATE countries "
        #         "SET total_score = total_score + %s "
        #         "WHERE alpha_2 = %s",
        #         (points, session['user']['country']))
        query = 'UPDATE accounts ' \
                'SET global_score = global_score + :points ' \
                'WHERE username = :name AND discriminator = :disc'
        values.pop('riddle')
        await database.execute(query, values)

        # Send request for bot to congratulate member
        await web_ipc.request('cheevo_found',
                alias=riddle, name=username, disc=disc, cheevo=dict(cheevo))

    return points
