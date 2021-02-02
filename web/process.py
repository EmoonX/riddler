from urllib.parse import urlparse

from quart import Blueprint, request

from ipc import web_ipc

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/<player_id>', methods=['POST'])
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
    
    return {'path': path}
