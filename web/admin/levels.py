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
    
    async def r(levels: list, msg: str):
        '''Render page with correct data.'''
        s = 'cipher'
        if alias == 'rns':
            s = 'riddle'
        folders = await _get_pages(alias)
        return await render_template('admin/levels.htm', 
                alias=alias, levels=levels,
                folders=folders, s=s, msg=msg)
    
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
    '''Fetch guild levels info from database.'''
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND is_secret IS FALSE'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    levels = {level['index']: dict(level) for level in result}
    return levels


async def _get_pages(alias: str) -> dict:
    '''Get a recursive dict of all riddle pages sorted in folders.'''
    
    # Build list of paths from database data
    query = 'SELECT * FROM level_pages WHERE riddle = :riddle'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    paths = []
    for row in result:
        path = dict(row)
        path['path'] = '/' + path['path']
        path['page'] = path['path'].rsplit('/', 1)[-1]
        paths.append(path)

    # Build dict of dict of list of folders and files
    folders = {'/': {'files': []}}
    for row in paths:
        folder = row['path'].rsplit('/', 1)[0]
        folder += '/'
        if not folder in folders:
            folders[folder] = {}
            folders[folder]['files'] = []
        folders[folder]['files'].append(row)

    # Add folders to directory structure
    aux = {}
    for folder_path in folders:
        # Build recursive dict of folders
        f = folder_path
        while f != '/':
            parent, name = f[:-1].rsplit('/', 1)
            #print(parent, name)
            parent += '/'
            if not parent in aux:
                aux[parent] = set()
            aux[parent].add(name)
            f = parent
    for folder, names in aux.items():
        # Add folder to parent folder as a "no level file"
        if not folder in folders:
            folders[folder] = {}
            folders[folder]['files'] = []
        for name in names:
            path = folder + name
            if path in paths:
                row = paths[path]
            else:
                row = {'path': path, 'page': name}
            print(folder, name)
            folders[folder]['files'].append(row)
    
    def _extension_cmp(row: dict):
        '''Compare pages based firstly on their extension.
        Order is: folders first, then .htm, then the rest.'''
        page = row['page']
        if len(page) < 4 or page[-4] != '.':
            return 'aaa' + page
        if page[-3:] == 'htm':
            return 'aab' + page
        return 'zzz' + page[-3:]

    # Sort pages from each folder
    for folder in folders.values():
        folder['files'].sort(key=_extension_cmp)
    
    # Save number of pages/files in folder
    for folder in folders.values():
        folder['files_total'] = len(folder['files'])
    
    return folders


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
