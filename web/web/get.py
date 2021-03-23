from quart import Blueprint

from inject import get_riddles

# Create app blueprint
get = Blueprint('get', __name__)


@get.route('/get-riddle-hosts', methods=['GET'])
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
