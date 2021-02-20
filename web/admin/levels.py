from quart import Blueprint, request, render_template
from quart_discord import requires_authorization
from pymysql.err import IntegrityError

from admin.admin import auth, save_image
from ipc import web_ipc
from util.db import database

# Create app blueprint
admin_levels = Blueprint('admin_levels', __name__)


@admin_levels.route('/admin/<alias>/levels/', methods=['GET', 'POST'])
@requires_authorization
async def levels(alias: str):
    '''Riddle level management.'''
    
    # Check for right permissions
    msg, status = await auth(alias)
    if status != 200:
        return msg, status
    
    def r(levels: list, msg: str):
        '''Render page with correct data.'''
        s = 'cipher'
        if alias == 'rns':
            s = 'riddle'
        return render_template('admin/levels.htm', 
                alias=alias, levels=levels, s=s, msg=msg)
    
    # Get initial level data from database
    levels_before = await _fetch_levels(alias)

    # Render page normally on GET
    if request.method == 'GET':
        return await r(levels_before.values(), '')
    
    # Build dict of levels after POST
    form = await request.form
    levels_after = {}
    for name, value in form.items():
        i = name.find('-')
        index, attr = int(name[:i]), name[(i+1):]
        if index not in levels_after:
            levels_after[index] = {}
        levels_after[index][attr] = value
    
    # Update changed levels both on DB and guild
    for index, level in levels_before.items():
        # Remove fields that were not modified by admin
        for attr, value in level.items():
            if attr in levels_after[index] \
                    and value == levels_after[index][attr]:
                levels_after[index].pop(attr)
        
        level_before = levels_before[index]
        level = levels_after[index]
        if len(level) > 1 or (len(level) == 1 and 'imgdata' not in level):
            # Update level(s) database data
            query = 'UPDATE levels SET '
            values = {'riddle': alias, 'index': index}
            aux = []
            for attr, value in level.items():
                if attr == 'imgdata':
                    continue
                s = '`%s` = :%s' % (attr, attr)
                aux.append(s)
                values[attr] = value
            query += ', '.join(aux)
            query += ' WHERE riddle = :riddle AND `index` = :index'
            await database.execute(query, values)
        
        # Swap image file if image was changed
        if 'imgdata' in level and level['imgdata']:
            if 'image' not in level:
                level['image'] = level_before['image']
            await save_image('thumbs', alias,
                    level['image'], level['imgdata'], level_before['image'])
        
        # Update Discord channels and roles names if discord_name changed
        if 'discord_name' in level:
            await web_ipc.request('update', guild_name=full_name,
                    old_name=levels_before[index]['discord_name'],
                    new_name=level['discord_name'])
    
    return 'OK'

    # Insert new level data on database
    query = 'INSERT INTO levels ' \
            '(riddle, level_set, `index`, `name`, path, image, answer, ' \
                '`rank`, discord_category, discord_name) VALUES ' \
            '(:riddle, :set, :index, :name, :path, :image, :answer, ' \
                ':rank, :discord_category, :discord_name)'
    index = len(levels_before) + 1
    values = {'riddle': alias, 'set': 'Normal Levels',
            'index': index, 'name': form['%d-name' % index],
            'path': form['%d-path' % index],
            'image': form['%d-image' % index],
            'answer': form['%d-answer' % index],
            'rank': form['%d-rank' % index],
            'discord_category': 'Normal Levels',
            'discord_name': form['%d-discord_name' % index]}
    await database.execute(query, values)
    # query = 'INSERT IGNORE INTO secret_levels VALUES ' \
    #         '(:guild, :category, :level_name, :path, ' \
    #             ':previous_level, :answer_path)'
    # secret_levels_values = {'guild': alias, 'category': 'Secret Levels',
    #         'level_name': form['new_secret_id'], 'path': form['new_secret_path'],
    #         'previous_level': form['new_secret_prev'],
    #         'answer_path': form['new_secret_answer']}
    # if '' not in secret_levels_values.values():
    #     await database.execute(query, secret_levels_values)
    
    # Get image data and save image on thumbs folder
    filename = form['%d-image' % index]
    imgdata = form['%d-imgdata' % index]
    print(imgdata)
    await save_image(alias, 'thumbs', filename, imgdata)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server.
    values['is_secret'] = 0
    await web_ipc.request('build', guild_name=full_name, levels=[values])
    
    # Fetch levels again to display page correctly on POST
    levels = await fetch_levels(alias)

    return await r('Guild info updated successfully!')


async def _fetch_levels(alias: str):
    '''Fetch guild levels and pages info from database.'''
    
    # Fetch basic level info
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND is_secret IS FALSE'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    levels = {level['index']: dict(level) for level in result}
    
    # Fetch level pages
    for level in levels.values():
        name = level['name']
        query = 'SELECT * FROM level_pages ' \
                'WHERE riddle = :riddle and level_name = :name'
        values = {'riddle': alias, 'name': name}
        result = await database.fetch_all(query, values)
        await _get_pages(alias, level)
    
    return levels


async def _get_pages(alias: str, level: dict):
    s = 'cipher'
    if alias == 'rns':
        s = 'riddle'
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = :riddle and level_name = :name'
    values = {'riddle': alias, 'name': level['name']}
    result = await database.fetch_all(query, values)
    paths = [(s + '/' + row['path']) for row in result]

    # Build dict of pairs (folder -> list of paths)
    level['folders'] = {}
    folders = level['folders']
    for path in paths:
        folder, page = path.rsplit('/', 1)
        if not folder in folders:
            folders[folder] = []
        folders[folder].append(page)

    # Save number of pages/files in folder
    level['files_count'] = {}
    for folder in folders:
        level['files_count'][folder] = len(folders[folder])

    def _extension_cmp(page: str):
        '''Compare pages based firstly on their extension.
        Order is: folders first, then .htm, then the rest.'''
        if len(page) < 4 or page[-4] != '.':
            return 'aaa'
        if page[-3:] == 'htm':
            return 'aab'
        return page[-3:]

    # Add folders to directories
    aux = {}
    for folder in folders:
        f = folder
        while f.count('/'):
            parent, name = f.rsplit('/', 1)
            if not parent in aux:
                aux[parent] = set()
            aux[parent].add(name)
            f = parent
    for folder, names in aux.items():
        if not folder in folders:
            folders[folder] = []
        folders[folder].extend(names)

    # Sort pages from each folder
    for _, pages in folders.items():
        pages.sort(key=_extension_cmp)

    # Count total number of pages in each folder
    level['files_total'] = {}
    query = 'SELECT path FROM level_pages WHERE ' \
            'riddle = :riddle AND level_name = :id'
    values = {'riddle': alias, 'id': level['name']}
    result = await database.fetch_all(query, values)
    paths = [row['path'] for row in result]
    for path in paths:
        folder = s + '/' + path.rsplit('/', 1)[0]
        if not folder in folders:
            # Avoid spoiling things in HTML!
            continue
        if not folder in level['files_total']:
            level['files_total'][folder] = 0
        level['files_total'][folder] += 1


@admin_levels.route('/admin/level-row/', methods=['GET'])
async def level_row():
    '''Level row HTML code to be fetched by JS script.'''
    return await render_template('admin/level-row.htm',
            level=None, index=request.args['index'],
            image='/static/thumbs/locked.png')


@admin_levels.route('/admin/<alias>/update-pages/', methods=['POST'])
async def update_pages(alias: str):
    '''Update pages list with data sent by admin in text format.'''
    
    # Decode received text data and split into list (ignore empty)
    data = await request.data
    data = data.decode('utf-8')
    data = filter(None, data.replace('\r', '').split('\n'))

    for page in data:
        try:
            query = 'INSERT INTO level_pages ' \
                '(riddle, path) VALUES (:riddle, :path)'
            values = {'riddle': alias, 'path': page}
            await database.execute(query, values)
            print(('> \033[1m[%s]\033[0m Added page \033[1m%s\033[0m ' \
                    'to database!') % (alias, page))
        except IntegrityError:
            print('> \033[1m[%s]\033[0m Skipping page \033[1m%s\033[0m... ' \
                    % (alias, page))
            
    return 'OK', 200
