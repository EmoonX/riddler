from quart import Blueprint, render_template

# Create app blueprint
info = Blueprint('info', __name__)


@info.route('/about')
async def about():
    return await render_template('about.htm')


@info.route('/thedudedude')
async def thedude():
    username = '???'
    disc = '???'
    from process import process_url
    from util.db import database
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = "cipher" AND `index` >= 64 AND `index` <= 65 AND is_secret IS FALSE'
    levels = await database.fetch_all(query)
    for level in levels:
        front_path = 'http://gamemastertips.com/cipher' + level['path']
        answer_path = 'http://gamemastertips.com/cipher' + level['answer']
        image_path = front_path.rsplit('/', maxsplit=1)[0] + '/' + level['image']
        from time import sleep
        await process_url(username, disc, front_path)
        await process_url(username, disc, image_path)
        sleep(2)
        # await process_url(username, disc, answer_path)
        # sleep(2)
    
    return 'SUCCESS!', 200
