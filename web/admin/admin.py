from quart import Blueprint
from quart_discord import requires_authorization

from auth import discord
from util.db import database

# Create app blueprint
admin = Blueprint('admin', __name__)


@requires_authorization
async def auth(alias: str):
    '''Check if alias is valid and user is admin of guild.'''
    
    # Get riddle/guild full name from database
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    if not result:
        # Invalid alias...
        return 'Riddle not found!', 404
    full_name = result['full_name']
    
    # Check if user is indeed an admin of given guild
    guilds = await discord.fetch_guilds()
    for guild in guilds:
        if guild.name == full_name:
            if not guild.permissions.administrator:
                return 'Unauthorized', 401
            break
    
    return 'OK', 200


async def save_image(alias: str,
        filename: str, prev_filename: str, imgdata: str):
    '''Create a image from base64 string and 
    save it on riddle's thumbs folder.'''
    
    # Get pure base64 data from URL and convert it to image
    mime, data = imgdata.split(',', maxsplit=1)
    mime += ','
    data = b64decode(data)
    img = Image.open(BytesIO(data))
    
    # Get correct riddle thumbs dir
    dir = Path(os.path.dirname(os.path.realpath(__file__)))
    dir = str(dir.parent) + ('/static/thumbs/%s' % alias)
    
    # Erase previous file if filename was changed
    if filename != prev_filename:
        prev_path = '%s/%s' % (dir, prev_filename)
        try:
            os.remove(prev_path)
            print('[%s] Image %s successfully removed'
                    % (alias, prev_filename))
        except:
            print('[%s] Couldn\'t remove image %s'
                    % (alias, prev_filename))

    # Save image on riddle's thumbs folder
    path = '%s/%s' % (dir, filename)
    img.save(path)
    print('Image %s successfully saved'
            % (alias, filename))
