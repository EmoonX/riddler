from quart import Blueprint, make_response, request

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/', methods=['POST'])
async def proc():
    url = (await request.data).decode('utf-8')
    return {'url': url}
