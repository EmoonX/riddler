from quart import Blueprint, make_response

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process/', methods=['POST'])
async def proc():
    resp = await make_response('LOL')
    #resp.headers['Access-Control-Allow-Origin'] = '*'
    #resp.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST, DELETE, OPTIONS'
    #resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    return resp
