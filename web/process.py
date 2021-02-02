from urllib.parse import urlparse

from quart import Blueprint, request

from ipc import web_ipc

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/', methods=['POST'])
async def process_url():
    # Receive URL from request and parse it
    url = (await request.data).decode('utf-8')
    parsed = urlparse(url)

    # Send Unlocking request to bot's IPC server
    path = parsed.path
    await web_ipc.request('unlock',
            alias='snowflake', player_id=315940379553955844,
            path=path)
    
    return {'path': path}
