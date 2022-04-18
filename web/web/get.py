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
