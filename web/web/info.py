from quart import Blueprint, render_template

# Create app blueprint
info = Blueprint('info', __name__)


@info.route('/about')
async def about():
    return await render_template('about.htm')


@info.route('/thedudedude')
async def thedude():
    username = '????'
    disc = '????'
    from process import process_url
    from util.db import database
    first = 1
    last = 42
    inclusive = False
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = "string" AND `index` >= :first AND `index` <= :last AND is_secret IS FALSE'
    values = {'first': first, 'last': last}
    levels = await database.fetch_all(query, values)
    for level in levels:
        front_path = 'https://thestringharmony.com' + level['path']
        answer_path = 'https://thestringharmony.com' + level['answer']
        image_path = front_path.rsplit('/', maxsplit=1)[0] + '/' + level['image']
        from time import sleep
        await process_url(username, disc, front_path)
        await process_url(username, disc, image_path)
        sleep(2)
        if level['index'] == last and not inclusive:
            break
        await process_url(username, disc, answer_path)
        sleep(2)
    
    return 'SUCCESS!', 200
