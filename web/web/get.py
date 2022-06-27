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
async def get_user_riddle_data(alias: str = '%'):
    '''Get riddle data for authenticated user.
    If `alias` is passed, restrict results to just given riddle.'''

    # Get player and riddle data from DB
    riddles = {}
    user = await discord.get_user()
    values = {'username': user.name, 'disc': user.discriminator}
    if alias == '%':
        query = '''
            SELECT * FROM riddles
            WHERE alias IN (
                SELECT current_riddle FROM accounts
                WHERE username = :username AND discriminator = :disc
            )
        '''
        current_riddle = await database.fetch_one(query, values)
        if not current_riddle:
            return 'No riddle being played...', 404
    query = '''
        SELECT * FROM riddles r
        WHERE alias IN (
            SELECT riddle FROM user_levels ul
            WHERE r.alias = ul.riddle
                AND username = :username AND discriminator = :disc
        ) AND alias LIKE :alias
    '''
    values['alias'] = alias
    result = await database.fetch_all(query, values)
    for row in result:
        _alias, full_name = row['alias'], row['full_name']
        riddles[_alias] = {
            'alias': _alias, 'fullName': full_name, 'levelOrdering': [],
        }
    # Build set of solved levels
    query = '''
        SELECT * FROM user_levels
        WHERE riddle LIKE :alias
            AND username = :username AND discriminator = :disc
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        _alias, level_name = row['riddle'], row['level_name']
        if not _alias in riddles:
            continue
        if not 'solvedLevels' in riddles[_alias]:
            riddles[_alias]['solvedLevels'] = {}
        if row['completion_time']:
            riddles[_alias]['solvedLevels'][level_name] = True

    # Get last visited levels for each riddle
    query = '''
        SELECT * FROM riddle_accounts
        WHERE riddle LIKE :alias
            AND username = :username AND discriminator = :disc
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        _alias, last_visited = row['riddle'], row['last_visited_level']
        if last_visited:
            riddles[_alias]['visitedLevel'] = last_visited

    # Get level ordering for navigating levels in extension
    query = '''
        SELECT * FROM levels lv
        WHERE `name` IN (
            SELECT level_name FROM user_levels ul
            WHERE ul.riddle = lv.riddle
                AND username = :username AND discriminator = :disc
        ) AND riddle LIKE :alias
        ORDER BY is_secret, `index`
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        _alias, level_name = row['riddle'], row['name']
        riddles[_alias]['levelOrdering'].append(level_name)

    # Create and return JSON dict with data
    if alias == '%':
        data = {'riddles': riddles, 'currentRiddle': current_riddle['alias']}
    else:
        data = riddles[alias] if alias in riddles else {}
    data = json.dumps(data)
    return data


@get.get('/get-current-riddle-data')
async def get_current_riddle_data():
    '''Get currently being played riddle data for authenticated user.'''

    # Get player and riddle data from DB
    user = await discord.get_user()
    query = '''
        SELECT * FROM accounts acc
        INNER JOIN riddles r ON acc.current_riddle = r.alias
        INNER JOIN riddle_accounts racc
            ON r.alias = racc.riddle
                AND acc.username = racc.username
                AND acc.discriminator = racc.discriminator
        WHERE acc.username = :username AND acc.discriminator = :disc
    '''
    values = {'username': user.name, 'disc': user.discriminator}
    riddle = await database.fetch_one(query, values)
    if not riddle:
        return 'No riddle being played...', 404
    alias = riddle['alias']

    # Get guild icon URL by bot request (or static one)
    icon_url = await bot_request(
        'get-riddle-icon-url', guild_id=riddle['guild_id']
    )
    if not icon_url:
        icon_url = f"https://riddler.app/static/riddles/{alias}.png"

    # Create and return JSON dict with data
    data = {
        'alias': alias,
        'full_name': riddle['full_name'], 'icon_url': icon_url,
        'visited_level': riddle['last_visited_level'],
    }
    data = json.dumps(data)
    return data
