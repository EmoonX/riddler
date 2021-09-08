from quart import Blueprint, request, render_template, abort
from jinja2.exceptions import TemplateNotFound

# Create app blueprint
info = Blueprint('info', __name__)


@info.route('/<page>')
async def info_page(page: str):
    '''Simply show a info page by rendering its immediate template.
    Throws 404 if such template doesn't exist.'''
    path = 'info/%s.htm' % page
    try:
        return await render_template(path)
    except TemplateNotFound:
        abort(404)


@info.route('/thedudedude')
async def thedude():
    username = 'Broccoli'
    disc = '8858'
    from process import process_url
    from util.db import database
    first = 65
    last = 65
    inclusive = True
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = "cipher" AND `index` >= :first AND `index` <= :last AND is_secret IS FALSE'
    values = {'first': first, 'last': last}
    levels = await database.fetch_all(query, values)
    for level in levels:
        front_path = 'http://gamemastertips.com/cipher' + level['path']
        answer_path = 'http://gamemastertips.com/cipher' + level['answer']
        image_path = front_path.rsplit('/', maxsplit=1)[0] + '/' + level['image']
        from time import sleep
        await process_url(username, disc, front_path)
        await process_url(username, disc, image_path)
        sleep(1)
        if level['index'] == last and not inclusive:
            break
        await process_url(username, disc, answer_path)
        sleep(1)
    
    return 'SUCCESS!', 200


@info.route('/theladylady')
async def thelady():
    username = 'Broccoli'
    disc = '8858'
    from process import process_url
    from util.db import database
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = "cipher"'
    pages = await database.fetch_all(query)
    for page in pages:
        path = 'http://gamemastertips.com/cipher' + page['path']
        await process_url(username, disc, path)
        from time import sleep
        sleep(0.1)
    
    return 'SUCCESS!', 200
