from urllib.parse import urlparse

from quart import Blueprint, request, jsonify

from ipc import web_ipc

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/<player_id>', methods=['POST', 'OPTIONS'])
async def process_url(player_id: str):
    # Receive URL from request and parse it
    url = (await request.data).decode('utf-8')
    parsed = urlparse(url)

    # Send Unlocking request to bot's IPC server
    path = parsed.path
    player_id = int(player_id)
    await web_ipc.request('unlock',
            alias='snowflake', player_id=player_id,
            path=path)
    
    # Allow CORS to be requested from other domains and Chrome
    response = jsonify({'path': path})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    
    # Return response
    return response
