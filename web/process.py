from urllib.parse import urlparse

from quart import Blueprint, request

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/', methods=['POST'])
async def process_url():
    # Receive URL from request and parse it
    url = (await request.data).decode('utf-8')
    parsed = urlparse(url)

    path = parsed.path
    return {'path': path}
