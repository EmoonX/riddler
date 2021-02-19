from quart import Blueprint, request, render_template
from quart_discord import requires_authorization

from admin.admin import auth, save_image
from inject import get_achievements
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
    
    def r(msg: str):
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
        return await r('')
    
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
            await database.execute(query, values)
        
        # Swap image file if image was changed
        if 'imgdata' in cheevo and cheevo['imgdata']:
            if 'image' not in cheevo:
                cheevo['image'] = cheevo_before['image']
            await save_image('cheevos', alias,
                    cheevo['image'], cheevo['imgdata'], cheevo_before['image'])

    if len(cheevos_after) > len(cheevos_before):
        # Insert new level data on database
        query = 'INSERT INTO achievements VALUES ' \
                '(:riddle, :title, :description, :image, :rank, :paths_json)'
        index = len(cheevos_before) + 1
        values = {'riddle': alias, 'title': form['%d-title' % index],
                'description': form['%d-description' % index],
                'image': form['%d-image' % index],
                'rank': form['%d-rank' % index],
                'paths_json': form['%d-paths_json' % index]}
        await database.execute(query, values)
        
        # Get image data and save image on thumbs folder
        filename = form['%d-image' % index]
        imgdata = form['%d-imgdata' % index]
        await save_image('cheevos', alias, filename, imgdata)
    
    # Fetch cheevos again to display page correctly on POST
    cheevos = await get_achievements(alias)
    k = 1
    for cheevo_list in cheevos.values():
        for cheevo in cheevo_list:    
            cheevo['index'] = k
            k += 1

    return await r('Guild info updated successfully!')


@admin_cheevos.route('/admin/cheevo-row/', methods=['GET'])
async def cheevo_row():
    '''Çheevo row HTML code to be fetched by JS script.'''
    return await render_template('admin/cheevo-row.htm')
