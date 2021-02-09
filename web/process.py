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
    "D": (10, "cornflowerblue"),
    "C": (15, "lawngreen"),
    "B": (25, "gold"),
    "A": (40, "crimson"),
    "S": (60, "lightcyan")
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
        url = (await request.data).decode('utf-8')
        parsed = urlparse(url)
        path = parsed.path

        if request.method =='POST':
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
            
            print('[%s] Received path "%s" from %s#%s'
                    % (riddle, path, user.name, user.discriminator))
        
        # Successful response
        response = jsonify({'path': path})
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
    Return total points gotten.'''

    async def _search_and_add_to_db(table: str, id: int, points: int):
        '''Search if level was yet not completed or secret yet not found.
        If true, add user and datetime of completion to respective table.'''

        # Check if level has been completed
        username = session['user']['username']
        disc = session['user']['discriminator']
        query = ('SELECT * FROM %s ' % table) + \
                'WHERE riddle = :riddle AND username = :name ' \
                'AND discriminator = :disc AND level_id = :id'
        values = {'riddle': riddle, 'name': username, 'disc': disc, 'id': id}
        found = await database.fetch_one(query, values)
        if found:
            return
        
        # Register level completion in designated table
        time = datetime.utcnow()
        count = session[riddle]['cur_hit_counter']
        query = ('INSERT INTO %s ' % table) + \
                '(riddle, username, discriminator, ' \
                    'level_id, completion_time, page_count) ' \
                'VALUES (:riddle, :name, :disc, :id, :time, :count)'
        values = {**values, 'time': time, 'count': count}
        await database.execute(query, values)

        if table == 'user_levelcompletion':
            # Update global user completion count
            query = 'UPDATE levels ' \
                    'SET completion_count = completion_count + 1 ' \
                    'WHERE riddle = :riddle AND id = :id'
            values = {'riddle': riddle, 'id': id}
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

            if not 'Status' in id:
                # Update current_level count and reset user's page count
                id_next = ''
                if riddle == 'cipher':
                    id_next = '%02d' % (int(id) + 1)
                if riddle == 'rns':
                    id_next = 'level-%d' % (int(id[-1:]) + 1)
                query = 'UPDATE riddle_accounts ' \
                        'SET current_level = :id_next, cur_hit_counter = 0 ' \
                        'WHERE riddle = :riddle AND ' \
                            'username = :name AND discriminator = :disc'
                values = {'id_next': id_next,
                        'riddle': riddle, 'name': username, 'disc': disc}
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

    def _has_access():
        """Check if user can access level_id,
                having reached current_level so far."""
        return True
        # # Admins can access everything!
        # if session['user']['rank'] == 'Site Administrator':
        #     return True

        # if "Status" in level_id:
        #     # Secret level, check previous id in respective table
        #     cursor = get_cursor()
        #     cursor.execute("SELECT * FROM user_secretsfound "
        #             "WHERE level_id = %s", (level_id,))
        #     secret_found = cursor.fetchone()
        #     return secret_found

        # # Return if level is *at most* the current_level
        # return int(level_id) <= int(current_level)
    
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
    current_level = session[riddle]['current_level']
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = :riddle AND path = :path'
    values = {'riddle': riddle, 'path': path}
    page = await database.fetch_one(query, values)
    if not page:
        # Page not found!
        return
    level_id = page['level_id']

    # if is_htm:
    # Get user's current level info from DB
    query = 'SELECT * FROM levels WHERE riddle = :riddle AND id = :id'
    values = {'riddle': riddle, 'id': current_level}
    level = await database.fetch_one(query, values)

    # If user entered a correct and new answer, register time on DB
    #if int(current_level) <= total and path == level["answer"]:
    points = 0
    if current_level == '00' or path == level['answer']:
        rank = level['rank'] if level else 'D'
        points = level_ranks[rank]['points']
        await _search_and_add_to_db('user_levelcompletion',
                current_level, points)
    else:
        pass
        # Check if a secret level has been found
        # cursor.execute("SELECT * FROM levels "
        #         "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
        #         "path = %s", (path,))
        # secret = cursor.fetchone()
        # if secret:
        #     search_and_add_to_db('user_secretsfound', secret['id'])
        # else:
        #     # Otherwise, check if a secret level has been beaten
        #     cursor.execute("SELECT * FROM levels "
        #             "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
        #             "answer = %s", (path,))
        #     secret = cursor.fetchone()
        #     if secret:
        #         search_and_add_to_db('user_levelcompletion',
        #                 secret['id'], secret['rank'])

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
            'id': level_id, 'path': path, 'time': tnow}
    await database.execute(query, values)

    # If it's an achievement page, add it to user's collection
    # cursor.execute("SELECT * FROM achievements "
    #         "WHERE path = %s", (path,))
    # cheevo = cursor.fetchone()
    # if cheevo:
    #     cursor.execute("SELECT username from user_achievements "
    #             "WHERE username = %s and title = %s",
    #             (session['user']['username'], cheevo['title']))
    #     has_cheevo = (cursor.fetchone() is not None)
    #     if not has_cheevo:
    #         cursor.execute("INSERT INTO user_achievements VALUES (%s, %s)",
    #                 (session['user']['username'], cheevo['title']))
    #         # Update user and country score
    #         points = cheevo['points']
    #         cursor.execute("UPDATE accounts "
    #                 "SET score = score + %s WHERE username = %s",
    #                 (points, session['user']['username']))
    #         cursor.execute("UPDATE countries "
    #                 "SET total_score = total_score + %s "
    #                 "WHERE alpha_2 = %s",
    #                 (points, session['user']['country']))

    return points
