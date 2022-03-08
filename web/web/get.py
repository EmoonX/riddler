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
    for i in range(len(hosts)):
        host = hosts[i]
        host = host.replace('https', '*').replace('http', '*')
        host = host[:4] + '*.' + host[4:] + '/*'
        hosts[i] = host
    
    # Join hosts in a space-separated string and return text response
    hosts = ' '.join(hosts)
    return hosts


@get.get('/get-current-riddle-data')
async def get_current_riddle_data():
    '''Get currently being played riddle data
    for current authenticated user.'''
   
    # Get riddle data from DB 
    user = await discord.get_user()
    query = '''SELECT * FROM accounts acc
        INNER JOIN riddles r ON acc.current_riddle = r.alias
        WHERE username = :username AND discriminator = :disc'''
    values = {'username': user.name, 'disc': user.discriminator}
    riddle = await database.fetch_one(query, values)
    if not riddle:
        return 'No riddle being played...', 404
    alias = riddle['alias']

    # Get guild icon URL by bot request (or static one)
    icon_url = await bot_request('get-riddle-icon-url',
        guild_id=riddle['guild_id'])
    if not icon_url:
        icon_url = 'https://riddler.app/static/riddles/%s.png' % alias

    # Create and return JSON dict with data
    data = { 'alias': alias,
        'full_name': riddle['full_name'], 'icon_url': icon_url }
    data = json.dumps(data)
    return data
