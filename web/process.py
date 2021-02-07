from urllib.parse import urlparse

from quart import Blueprint, request, session, jsonify

from user.auth import discord
from ipc import web_ipc
from util.db import database

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/', methods=['POST', 'OPTIONS'])
async def process_url():
    '''Process an URL sent by the browser extension.'''
    # Receive URL from request and parse it
    url = (await request.data).decode('utf-8')
    parsed = urlparse(url)
    path = parsed.path

    response = None
    status = None
    if not await discord.authorized:
        # Unauthorized, return status 401
        response = jsonify({'message': 'Unauthorized'})
        status = 401 if request.method == 'POST' else 200
    else:
        # Send Unlocking request to bot's IPC server
        user = await discord.fetch_user()
        path = path.replace('/cipher/', '')
        await process_page(user.id, path)
        response = jsonify({'path': path})
        status = 200
    
    # (Chrome fix) Allow CORS to be requested from other domains
    response.headers.add('Access-Control-Allow-Origin',
            'http://gamemastertips.com')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Headers', 'Cookie')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    
    # Return response
    return response, status


async def process_page(player_id: int, path:str):
    """Process level pages (one or more folders deep)."""

    def search_and_add_to_db(table, level, rank=''):
        """Search if level was yet not completed or secret yet not found.
        If true, add user and datetime of completion to respective table."""
        cursor.execute("SELECT username FROM " + table + " "
                "WHERE username = %s AND level_id = %s",
                (session['user']['username'], level,))
        found = cursor.fetchone()
        if not found:
            time = datetime.utcnow()
            aux = ", NULL)" if table == 'user_levelcompletion' else ")"
            cursor.execute("INSERT INTO " + table +
                    " VALUES (%s, %s, %s, %s" + aux,
                    (session['user']['username'], level, time,
                        session['user']['cur_page_count']))

            if table == 'user_levelcompletion':
                # Update global user completion count
                cursor.execute("UPDATE levels "
                        "SET completion_count = completion_count + 1 "
                        "WHERE id = %s", (level,))

                # Update user and country scores
                points = level_ranks[rank][0]
                cursor.execute("UPDATE accounts "
                        "SET score = score + %s WHERE username = %s",
                        (points, session['user']['username']))
                cursor.execute("UPDATE countries "
                        "SET total_score = total_score + %s "
                        "WHERE alpha_2 = %s",
                        (points, session['user']['country']))

                if not 'Status' in level:
                    # Update current_level count and reset user's page count
                    nonlocal current_level
                    current_level = "%02d" % (int(level) + 1)
                    cursor.execute("UPDATE accounts "
                            "SET current_level = %s, cur_page_count = 0 "
                            "WHERE username = %s",
                            (current_level, session['user']['username']))
                    session['user']['current_level'] = current_level
                    session['user']['cur_page_count'] = 0

                    # Update countries table too
                    cursor.execute("UPDATE countries "
                            "SET highest_level = GREATEST(highest_level, %s) "
                            "WHERE alpha_2 = %s",
                            (current_level, session['user']['country']))
                    if int(current_level) > get_level_count()[0]:
                        cursor.execute("UPDATE countries "
                                "SET winners_count = winners_count + 1 "
                                "WHERE alpha_2 = %s",
                                (session['user']['country'],))

    def has_access():
        """Check if user can access level_id,
                having reached current_level so far."""
        # Admins can access everything!
        if session['user']['rank'] == 'Site Administrator':
            return True

        if "Status" in level_id:
            # Secret level, check previous id in respective table
            cursor = get_cursor()
            cursor.execute("SELECT * FROM user_secretsfound "
                    "WHERE level_id = %s", (level_id,))
            secret_found = cursor.fetchone()
            return secret_found

        # Return if level is *at most* the current_level
        return int(level_id) <= int(current_level)

    # Increment user current page count (if it's an .htm one)
    is_htm = path[-4:] == '.htm'
    if is_htm:
        query = 'UPDATE accounts SET cur_page_count = cur_page_count + 1 ' \
                'WHERE username = :user'
        values = {'user': session['user']['username']}
        await database.execute(query, values)
        session['user']['cur_page_count'] += 1
    
    return

    # Get user's current reached level and requested level number
    current_level = session['user']['current_level']
    cursor.execute("SELECT * FROM level_pages WHERE path = %s", (path,))
    page = cursor.fetchone()
    if not page:
        # Page not found!
        abort(404)
    level_id = page["level_id"]

    if htm:
        # Get user's current level info from DB
        cursor.execute("SELECT * FROM levels WHERE id = %s",
                (current_level,))
        level = cursor.fetchone()

        # If user entered a correct and new answer, register time on DB
        total, _ = get_level_count()
        if int(current_level) <= total and path == level["answer"]:
            search_and_add_to_db("user_levelcompletion",
                    current_level, level['rank'])

            # Create unique filename with user/level for Discord use
            discord_tag = session['user']['discord_tag']
            filename = "%s-%s" % (discord_tag, level['id'])
            #os.mknod("tmp/" + filename)

        else:
            # Check if a secret level has been found
            cursor.execute("SELECT * FROM levels "
                    "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
                    "path = %s", (path,))
            secret = cursor.fetchone()
            if secret:
                search_and_add_to_db('user_secretsfound', secret['id'])
            else:
                # Otherwise, check if a secret level has been beaten
                cursor.execute("SELECT * FROM levels "
                        "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
                        "answer = %s", (path,))
                secret = cursor.fetchone()
                if secret:
                    search_and_add_to_db('user_levelcompletion',
                            secret['id'], secret['rank'])

    if not has_access():
        # Forbid user from accessing any level further than permitted
        abort(403)

    # Register into database new page access (if applicable)
    tnow = datetime.utcnow()
    cursor.execute("INSERT IGNORE INTO user_pageaccess VALUES (%s, %s, %s, %s)",
            (session['user']['username'], level_id, path, tnow))

    # If it's an achievement page, add it to user's collection
    cursor.execute("SELECT * FROM achievements "
            "WHERE path = %s", (path,))
    cheevo = cursor.fetchone()
    if cheevo:
        cursor.execute("SELECT username from user_achievements "
                "WHERE username = %s and title = %s",
                (session['user']['username'], cheevo['title']))
        has_cheevo = (cursor.fetchone() is not None)
        if not has_cheevo:
            cursor.execute("INSERT INTO user_achievements VALUES (%s, %s)",
                    (session['user']['username'], cheevo['title']))
            # Update user and country score
            points = cheevo['points']
            cursor.execute("UPDATE accounts "
                    "SET score = score + %s WHERE username = %s",
                    (points, session['user']['username']))
            cursor.execute("UPDATE countries "
                    "SET total_score = total_score + %s "
                    "WHERE alpha_2 = %s",
                    (points, session['user']['country']))


    # Commit changes to DB
    mysql.connection.commit()

    # If the level page is indeed a .htm, render its template
    if htm:
        path = "levels/" + path
        return render_and_count(path, {})
