import os
from base64 import b64decode
from io import BytesIO
from pathlib import Path

from quart import Blueprint, request, render_template
from quart_discord import requires_authorization
from PIL import Image

from auth import discord
from ipc import web_ipc
from util.db import database

# Create app blueprint
admin = Blueprint('admin', __name__)


@admin.route('/admin/<alias>/', methods=['GET', 'POST'])
@requires_authorization
async def config(alias: str):
    '''Riddle administration configuration.'''
    
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
    
    # Get initial level data from database
    levels_before = await fetch_levels(alias)
    
    def r(levels: dict, msg: str):
        '''Render page and get filename cookies locally.'''
        return render_template('admin/admin.htm', 
                alias=alias, levels=levels, msg=msg)

    # Render page normally on GET
    if request.method == 'GET':
        return await r(levels_before.values(), '')
    
    # Build dict of levels after POST
    form = await request.form
    levels_after = {}
    for name, value in form.items():
        i = name.find('-')
        index, attr = int(name[:i]), name[(i+1):]
        if attr != 'imgdata':
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
        if not levels_after[index]:
            # Nothing to be done if no changes
            continue

        # Update level(s) database data
        level = levels_after[index]
        query = 'UPDATE levels SET '
        values = {'riddle': alias, 'index': index}
        aux = []
        for attr, value in level.items():
            s = '`%s` = :%s' % (attr, attr)
            aux.append(s)
            values[attr] = value
        query += ', '.join(aux)
        query += ' WHERE riddle = :riddle AND `index` = :index'
        await database.execute(query, values)
        
        # Update Discord channels and roles names if discord_name changed
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
    await _save_image(alias, filename, imgdata)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server.
    values['is_secret'] = 0
    await web_ipc.request('build', guild_name=full_name, levels=[values])
    
    # Fetch levels again to display page correctly on POST
    levels = await fetch_levels(alias)

    return await r('Guild info updated successfully!')


async def fetch_levels(alias: str):
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
        pages = tuple(page['path'] for page in result)
        level['pages'] = pages
    
    return levels


async def _save_image(alias: str, filename: str, imgdata: str):
    '''Create a image from base64 string and 
    save it on riddle's thumbs folder.'''
    
    # Get pure base64 data from URL and convert it to image
    mime, data = imgdata.split(',', maxsplit=1)
    mime += ','
    data = b64decode(data)
    img = Image.open(BytesIO(data))

    # Save image on riddle's thumbs folder
    dir = Path(os.path.dirname(os.path.realpath(__file__)))
    dir = str(dir.parent) + ('/static/thumbs/%s' % alias)
    path = '%s/%s' % (dir, filename)
    print(path)
    img.save(path)
