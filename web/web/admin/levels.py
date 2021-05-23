import json
from copy import deepcopy

from quart import Blueprint, request, render_template
from quart_discord import requires_authorization
from pymysql.err import IntegrityError

from admin.admin import auth, save_image
from webclient import bot_request
from util.db import database

# Create app blueprint
admin_levels = Blueprint('admin_levels', __name__)


@admin_levels.route('/admin/<alias>/levels', methods=['GET', 'POST'])
@requires_authorization
async def levels(alias: str):
    '''Riddle level management.'''
    
    # Check for admin permissions
    msg, status = await auth(alias)
    if status != 200:
        return msg, status
    
    async def r(levels: list, secret_levels: list, msg: str):
        '''Render page with correct data.'''

        return await render_template('admin/levels.htm',
                alias=alias, levels=levels,
                secret_levels=secret_levels, msg=msg)
    
    # Get initial level data from database
    levels_before = await _fetch_levels(alias)
    secrets_before = await _fetch_levels(alias, is_secret=True)

    # Render page normally on GET
    if request.method == 'GET':
        return await r(levels_before.values(),
                secrets_before.values(), '')
    
    # Build dicts of levels after POST
    form = await request.form
    levels_after = {}
    secrets_after = {}
    for name, value in form.items():
        i = name.find('-')
        if i == -1 or name[:i] == 'removed':
            continue
        index, attr = name[:i], name[(i+1):]
        if 's' not in index:
            index = int(index)
            if index not in levels_after:
                levels_after[index] = {}
            levels_after[index][attr] = value
        else:
            index = int(index[1:])
            if index not in secrets_after:
                secrets_after[index] = {}
            secrets_after[index][attr] = value
    
    # Get full name of guild
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    guild_id = result['guild_id']
    
    async def _update_levels(levels_before: dict,
            levels_after: dict, is_secret=False):
        '''Update new/changed levels both on DB and guild.'''
        
        # Check and update existing levels
        for index, level in levels_before.items():
            # Remove fields that were not modified by admin
            for attr, value in level.items():
                if attr in levels_after[index] \
                        and value == levels_after[index][attr]:
                    levels_after[index].pop(attr)
            
            level_before = levels_before[index]
            level = levels_after[index]
            if not set(level.keys()).issubset({'imgdata', 'added-pages'}):
                # Update level(s) database data
                query = 'UPDATE levels SET '
                values = {'riddle': alias,
                        'is_secret': is_secret, 'index': index}
                aux = []
                for attr, value in level.items():
                    if attr in ('imgdata', 'added-pages'):
                        continue
                    s = '`%s` = :%s' % (attr, attr)
                    aux.append(s)
                    if attr == 'discord_category':
                        other = 'level_set'
                        t = '`%s` = :%s' % (other, attr)
                        aux.append(t)
                    values[attr] = value
                query += ', '.join(aux)
                query += ' WHERE riddle = :riddle ' \
                        'AND is_secret = :is_secret AND `index` = :index'
                await database.execute(query, values)
            
            # Swap image file if image was changed
            if 'imgdata' in level and level['imgdata']:
                if 'image' not in level:
                    level['image'] = level_before['image']
                await save_image('thumbs', alias,
                        level['image'], level['imgdata'], level_before['image'])
            
            # Update Discord channels and roles names if discord_name changed
            if 'discord_name' in level:
                await bot_request('update', guild_id=guild_id,
                        old_name=levels_before[index]['discord_name'],
                        new_name=level['discord_name'])
        
        # Add new levels, if any
        if len(levels_after) > len(levels_before):
            if not is_secret and levels_before:
                # Swap winners current level (medal) for last old level
                index = len(levels_before)
                query = 'UPDATE riddle_accounts ' \
                        'SET current_level = :level ' \
                        'WHERE riddle = :riddle AND current_level = "🏅"'
                values = {'riddle': alias, 'level': form['%s-name' % index]}
                await database.execute(query, values)
            
            levels = [] 
            for i in range(len(levels_before) + 1, len(levels_after) + 1):
                index = str(i) if not is_secret else 's%d' % i
                
                # Insert new level data on database
                query = 'INSERT INTO levels ' \
                        '(riddle, is_secret, level_set, `index`, `name`, ' \
                            'path, image, answer, `rank`, ' \
                            'discord_category, discord_name) VALUES ' \
                        '(:riddle, :is_secret, :set, :index, ' \
                            ':name, :path, :image, :answer, :rank, ' \
                            ':discord_category, :discord_name)'
                values = {'riddle': alias, 'is_secret': is_secret,
                        'set': form['%s-discord_category' % index],
                        'index': i, 'name': form['%s-name' % index],
                        'path': form['%s-path' % index],
                        'image': form['%s-image' % index],
                        'answer': form['%s-answer' % index],
                        'rank': form['%s-rank' % index],
                        'discord_category': \
                            form['%s-discord_category' % index],
                        'discord_name': form['%s-discord_name' % index]}
                await database.execute(query, values)
            
                # Get image data and save image on thumbs folder
                filename = form['%s-image' % index]
                imgdata = form['%s-imgdata' % index]
                await save_image('thumbs', alias, filename, imgdata)
                
                # Append values to new levels list for bot request
                values['is_secret'] = is_secret
                levels.append(values)

            # Update Discord guild channels and roles with new levels info
            await bot_request('insert', alias=alias, levels=levels)
        
        # Delete removed pages from main table and insert them into null one
        aux = form['removed-pages']
        if aux:
            removed_pages = json.loads(aux)
            for page in removed_pages:
                query = 'DELETE FROM level_pages ' + \
                        'WHERE riddle = :riddle AND `path` = :path'
                values = {'riddle': alias, 'path': page}
                await database.execute(query, values)
                query = 'INSERT IGNORE INTO level_pages_null ' + \
                        'VALUES (:riddle, :path)'
                await database.execute(query, values)

        # Update pages data to changed or new levels
        for i in range(1, len(levels_after) + 1):
            index = str(i) if not is_secret else 's%d' % i
            aux = form['%s-added-pages' % index]
            if not aux:
                continue
            added_pages = json.loads(aux)
            for page in added_pages:
                # Delete page from old table, whichever it is
                for table in ('level_pages', 'level_pages_null'):
                    query = ('DELETE FROM %s ' % table) + \
                            'WHERE riddle = :riddle AND path = :path'
                    values = {'riddle': alias, 'path': page}
                    await database.execute(query, values)

                # Insert new page into table
                level_to = form['%s-name' % index]
                query = 'INSERT INTO level_pages ' \
                        'VALUES (:riddle, :path, :level_name)'
                values = {'riddle': alias, 'path': page,
                        'level_name': level_to}
                await database.execute(query, values)
    
    # Update both normal and secret levels
    await _update_levels(levels_before, levels_after)
    await _update_levels(secrets_before, secrets_after, is_secret=True)
    
    # Fetch levels again to display page correctly on POST
    levels = await _fetch_levels(alias)
    secret_levels = await _fetch_levels(alias, is_secret=True)

    return await r(levels.values(),
            secret_levels.values(), 'Guild info updated successfully!')


async def _fetch_levels(alias: str, is_secret=False):
    '''Fetch guild levels info from database.'''
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = :riddle AND is_secret = :is_secret ' \
            'ORDER BY `index`'
    values = {'riddle': alias, 'is_secret': is_secret}
    result = await database.fetch_all(query, values)
    levels = {level['index']: dict(level) for level in result}
    return levels


@admin_levels.route('/admin/<alias>/levels/get-pages', methods=['GET'])
@requires_authorization
async def get_pages(alias: str) -> str:
    '''Return a recursive JSON of all riddle folders and pages.'''
    
    # Check for right permissions
    msg, status = await auth(alias)
    if status != 200:
        return msg, status
    
    # Build list of paths from database data
    query = 'SELECT riddle, path, level_name FROM level_pages ' \
            'WHERE riddle = :riddle ' \
            'UNION ' \
            'SELECT riddle, path, NULL FROM level_pages_null ' \
            'WHERE riddle = :riddle ' \
            'ORDER BY `path`'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    paths = []
    for row in result:
        row = dict(row)
        row['page'] = row['path'].rsplit('/', 1)[-1]
        row['folder'] = 0
        paths.append(row)

    # Build recursive dict of folders and files
    base = {'children': {}, 'levels': {}, 'folder': 1}
    pages = {'/': deepcopy(base)}
    for row in paths:
        parent = pages['/']
        segments = row['path'].split('/')[1:]
        for seg in segments:
            levels = parent['levels']
            if not row['level_name'] in levels:
                levels[row['level_name']] = 0
            levels[row['level_name']] += 1
            children = parent['children']
            if seg not in children:
                if seg != row['page']:
                    children[seg] = deepcopy(base)
                else:
                    children[seg] = row
            parent = children[seg]
    
    # def _extension_cmp(row: dict):
    #     '''Compare pages based firstly on their extension.
    #     Order is: folders first, then .htm, then the rest.'''
    #     page = row['page']
    #     index = page.rfind('.')
    #     if index == -1:
    #         return 'aaa' + page
    #     if page[index:] in ('.htm', '.html'):
    #         return 'aab' + page
    #     return 'zzz' + page[-3:]

    # # Sort pages from each folder
    # for folder in folders.values():
    #     folder['files'].sort(key=_extension_cmp)
    
    # # Save number of pages/files in folder
    # for folder in folders.values():
    #     folder['files_total'] = len(folder['files'])
    
    # Return JSON dump
    return json.dumps(pages)


@admin_levels.route('/admin/level-row', methods=['GET'])
async def level_row():
    '''Level row HTML code to be fetched by JS script.'''
    return await render_template('admin/level-row.htm',
            level=None, index=request.args['index'],
            image='/static/thumbs/locked.png')


@admin_levels.route('/admin/<alias>/update-pages', methods=['POST'])
async def update_pages(alias: str):
    '''Update pages list with data sent by admin in text format.'''
    
    # Decode received text data and split into list (ignore empty)
    data = await request.data
    data = data.decode('utf-8')
    data = filter(None, data.replace('\r', '').split('\n'))

    for page in data:
        try:
            query = 'INSERT INTO level_pages_null ' \
                'VALUES (:riddle, :path)'
            values = {'riddle': alias, 'path': page}
            await database.execute(query, values)
            print(('> \033[1m[%s]\033[0m Added page \033[1m%s\033[0m ' \
                    'to database!') % (alias, page))
        except IntegrityError:
            print('> \033[1m[%s]\033[0m Skipping page \033[1m%s\033[0m... ' \
                    % (alias, page))
            
    return 'OK', 200
