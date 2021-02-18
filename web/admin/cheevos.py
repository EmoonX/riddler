from quart import Blueprint, request, render_template
from quart_discord import requires_authorization

from admin.admin import auth, save_image
from inject import get_achievements
from ipc import web_ipc
from util.db import database

# Create app blueprint
admin_cheevos = Blueprint('admin_cheevos', __name__)


@admin_cheevos.route('/admin/<alias>/cheevos/', methods=['GET', 'POST'])
@requires_authorization
async def cheevos(alias: str):
    '''Riddle cheevos management.'''
    
    # Check for right permissions
    msg, status = await auth(alias)
    if status != 200:
        return msg, status
    
    def r(cheevos: list, msg: str):
        '''Render page with correct data.'''
        return render_template('admin/cheevos.htm', 
                alias=alias, cheevos=cheevos, msg=msg)
    
    # Get initial cheevos data from database.
    # Also save cheevos state before POST (match by index)
    k = 1
    cheevos_before = {}
    cheevos = await get_achievements(alias)
    for cheevo_list in cheevos.values():
        for cheevo in cheevo_list:    
            cheevo['index'] = k
            cheevos_before[k] = cheevo
            k += 1

    # Render page normally on GET
    if request.method == 'GET':
        return await r(cheevos, '')
    
    # Build dict of cheevos after POST
    form = await request.form
    cheevos_after = {}
    for name, value in form.items():
        i = name.find('-')
        index, attr = int(name[:i]), name[(i+1):]
        if index not in cheevos_after:
            cheevos_after[index] = {}
        cheevos_after[index][attr] = value
    
    # Update changed cheevos on DB
    for index, cheevo_before in cheevos_before.items():
        # Remove fields that were not modified by admin
        cheevo = cheevos_after[index]
        for attr, value in cheevo_before.items():
            if attr in cheevo and value == cheevo[attr]:
                cheevo.pop(attr)
        
        if len(cheevo) > 1 or (len(cheevo) == 1 and 'imgdata' not in cheevo):
            # Update level(s) database data
            query = 'UPDATE achievements SET '
            values = {'riddle': alias, 'prev_title': cheevo_before['title']}
            aux = []
            for attr, value in cheevo.items():
                if attr == 'imgdata':
                    continue
                s = '`%s` = :%s' % (attr, attr)
                aux.append(s)
                values[attr] = value
            query += ', '.join(aux)
            query += ' WHERE riddle = :riddle AND `title` = :prev_title'
            print(query, flush=True)
            print(values, flush=True)
            await database.execute(query, values)
        
        # Swap image file if image was changed
        if 'imgdata' in cheevo and cheevo['imgdata']:
            if 'image' not in cheevo:
                cheevo['image'] = cheevo_before['image']
            await save_image('cheevos', alias,
                    cheevo['image'], cheevo['imgdata'], cheevo_before['image'])
    
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
