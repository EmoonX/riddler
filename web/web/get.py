from quart import Blueprint

from inject import get_riddles

# Create app blueprint
get = Blueprint('get', __name__)

@get.route('/get-riddle-hosts', methods=['GET'])
async def get_riddle_hosts():
    riddles = await get_riddles()
    hosts = [riddle['root_path'] for riddle in riddles]
    hosts = ' '.join(hosts)
    return hosts
