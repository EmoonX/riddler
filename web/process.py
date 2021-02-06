from urllib.parse import urlparse

from quart import Blueprint, request, jsonify

from user.auth import discord
from ipc import web_ipc

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
    if not await discord.authorized:
        # Unauthorized, return status 401
        response = jsonify({'message': 'Unauthorized'})
        return response, 401
    else:
        # Send Unlocking request to bot's IPC server
        # player_id = int(player_id)
        # await web_ipc.request('unlock',
        #         alias='snowflake', player_id=player_id,
        #         path=path)
        response = jsonify({'path': path})
    
    # (Chrome fix) Allow CORS to be requested from other domains
    response.headers.add('Access-Control-Allow-Origin',
            'http://gamemastertips.com')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Headers', 'Cookie')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    
    # Return response
    return response
