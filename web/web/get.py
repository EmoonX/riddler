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
    '''Ǵet list of riddle hosts from database.'''

    # Get list of hosts
    riddles = await get_riddles(unlisted=True)
    hosts = [riddle['root_path'] for riddle in riddles]

    # Set wildcard (*) to protocol, subdomain and path
    for i, host in enumerate(hosts):
        host = host.replace('https', '*').replace('http', '*')
        hosts[i] = host[:4] + '*.' + host[4:] + '/*'

    # Join hosts in a space-separated string and return text response
    text = ' '.join(hosts)
    return text


@get.get('/get-current-riddle-data')
async def get_current_riddle_data():
    '''Get current riddle data for authenticated user.'''

    # Get player and riddle data from DB
    user = await discord.get_user()
    query = '''
        SELECT *
        FROM riddles r INNER JOIN accounts acc
        ON r.alias = acc.current_riddle
        WHERE username = :username AND discriminator = :disc
    '''
    values = {'username': user.name, 'disc': user.discriminator}
    current_riddle = await database.fetch_one(query, values)
    if not current_riddle:
        return 'No riddle being played...', 404

    # Get last visited levels for each riddle
    query = '''
        SELECT * FROM riddle_accounts
        WHERE username = :username AND discriminator = :disc
    '''
    result = await database.fetch_all(query, values)
    last_visited_levels = {
        row['riddle']: row['last_visited_level'] for row in result
    }
    # Get level ordering for navigating levels in extension
    query = '''
        SELECT * FROM levels lv
        WHERE `name` IN (
            SELECT level_name FROM user_levels ul
            WHERE ul.riddle = lv.riddle
                AND username = :username AND discriminator = :disc
        )
        ORDER BY is_secret, `index`
    '''
    result = await database.fetch_all(query, values)
    level_orderings = {}
    for row in result:
        alias, level_name = row['riddle'], row['name']
        if not alias in level_orderings:
            level_orderings[alias] = []
        level_orderings[alias].append(level_name)

    # Create and return JSON dict with data
    data = {
        'alias': current_riddle['alias'],
        'fullName': current_riddle['full_name'],
        'lastVisitedLevels': last_visited_levels,
        'levelOrderings': level_orderings,
    }
    data = json.dumps(data)
    return data
