import json

from quart import Blueprint

from auth import discord
from inject import get_riddles
from webclient import bot_request
from util.db import database

# Create app blueprint
get = Blueprint('get', __name__)


@get.get('/get-riddle-hosts')
async def get_riddle_hosts():
    '''Get list of riddle hosts from database.'''

    # Get list of hosts
    riddles = await get_riddles(unlisted=False)
    hosts = []
    for riddle in riddles:
        root_path = riddle['root_path']
        if root_path[0] == '[':
            root_path = ' '.join(root_path.split('"')[1::2])
        hosts.append(root_path)

    # Set wildcard (*) to protocol, subdomain and path
    for i, host in enumerate(hosts):
        host = host.replace('https', '*').replace('http', '*')
        hosts[i] = host[:4] + '*.' + host[4:] + '/*'

    # Join hosts in a space-separated string and return text response
    text = ' '.join(hosts)
    return text


@get.get('/get-user-riddle-data')
@get.get('/get-user-riddle-data/<alias>')
async def get_user_riddle_data(alias: str | None = None):
    '''
    Get riddle data for authenticated user.
    If `alias` is passed, restrict results to just given riddle.
    '''

    user = await discord.get_user()
    values = {'username': user.name}
    if not alias:
        # Get currently being played riddle from DB (if any)
        query = '''
            SELECT alias FROM riddles
            WHERE alias = (
                SELECT current_riddle FROM accounts
                WHERE username = :username
            )
        '''
        current_riddle = await database.fetch_val(query, values)
        if not current_riddle:
            return 'No riddle being played...', 404

    # Build initial riddle(s) dict
    query = '''
        SELECT alias, full_name AS fullName FROM riddles
        WHERE alias LIKE :riddle
    '''
    values = {'riddle': alias or '%'}
    result = await database.fetch_all(query, values)
    riddles = {
        row['alias']: dict(row) | {'levels': {}}
        for row in result
    }

    # Fetch list of levels found/unlocked/solved by user (with correct ordering)
    query = '''
        SELECT
            up.riddle, ls.name AS set_name, up.level_name,
            find_time, completion_time
        FROM user_pages up
            LEFT JOIN user_levels ul
                ON up.riddle = ul.riddle AND up.level_name = ul.level_name
                    AND up.username = ul.username
            INNER JOIN levels lv
                ON up.riddle = lv.riddle AND up.level_name = lv.name
            INNER JOIN level_sets ls
                ON up.riddle = ls.riddle AND lv.level_set = ls.name
        WHERE up.riddle LIKE :riddle AND up.username = :username
        ORDER BY ls.`index`, lv.`index`
    '''
    values |= {'username': user.name}
    result = await database.fetch_all(query, values)
    for row in result:
        _alias = row['riddle']
        set_name, level_name = row['set_name'], row['level_name']
        levels = riddles[_alias]['levels']
        if not set_name in levels:
            levels[set_name] = {}
        levels[set_name][level_name] = {
            'unlocked': row['find_time'] is not None,
            'beaten': row['completion_time'] is not None,
        }

    # Get last visited level/set for riddle(s)
    query = '''
        SELECT ra.riddle, last_visited_level, lv.level_set
        FROM riddle_accounts ra INNER JOIN levels lv
            ON ra.riddle = lv.riddle AND last_visited_level = lv.name
        WHERE ra.riddle LIKE :riddle AND username = :username
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        _alias, level = row['riddle'], row['last_visited_level']
        if level:
            riddles[_alias]['lastVisitedSet'] = row['level_set']
            riddles[_alias]['lastVisitedLevel'] = level

    # Create and return JSON dict with data
    if not alias:
        data = {'riddles': riddles, 'currentRiddle': current_riddle}
    else:
        data = riddles.get(alias, {})

    return json.dumps(data)


@get.get('/get-current-riddle-data')
async def get_current_riddle_data():
    '''Get currently being played riddle data for authenticated user.'''

    # Get player and riddle data from DB
    user = await discord.get_user()
    query = '''
        SELECT * FROM accounts acc
        INNER JOIN riddles r ON acc.current_riddle = r.alias
        INNER JOIN riddle_accounts racc
            ON r.alias = racc.riddle AND acc.username = racc.username
        WHERE acc.username = :username
    '''
    values = {'username': user.name}
    riddle = await database.fetch_one(query, values)
    if not riddle:
        return 'No riddle being played...', 404
    alias = riddle['alias']

    # Get guild icon URL by bot request (or static one)
    icon_url = await bot_request(
        'get-riddle-icon-url', guild_id=riddle['guild_id']
    )
    if not icon_url:
        icon_url = f"/static/riddles/{alias}.png"

    # Create and return JSON dict with data
    data = {
        'alias': alias,
        'full_name': riddle['full_name'], 'icon_url': icon_url,
        'visited_level': riddle['last_visited_level'],
    }
    data = json.dumps(data)
    return data
