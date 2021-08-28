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
    last = 20
    inclusive = True
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


@info.route('/theladylady')
async def thelady():
    username = 'Brocoli'
    disc = '8858'
    from process import process_url
    from util.db import database
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = "genius"'
    pages = await database.fetch_all(query)
    for page in pages:
        path = 'https://geniusriddle.000webhostapp.com' + page['path']
        await process_url(username, disc, path)
        from time import sleep
        sleep(0.1)
    
    return 'SUCCESS!', 200
