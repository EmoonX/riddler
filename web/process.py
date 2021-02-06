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
    status = None
    if not await discord.authorized:
        # Unauthorized, return status 401
        response = jsonify({'message': 'Unauthorized'})
        status = 401 if request.method == 'POST' else 200
    else:
        # Send Unlocking request to bot's IPC server
        user = await discord.fetch_user()
        await web_ipc.request('unlock',
                alias='snowflake', player_id=user.id,
                path=path)
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
