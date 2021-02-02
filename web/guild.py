from quart import Blueprint, request, render_template, \
        session, redirect, url_for, make_response
from discord.ext.ipc import Client
import bcrypt

from util.db import database

# Create app blueprint
guild = Blueprint('guild', __name__)

# Web client for inter-process communication with discord.py bot
web_ipc = Client(secret_key='RASPUTIN')


@guild.route('/guild/<alias>/', methods=['GET', 'POST'])
async def config(alias: str):
    '''Guild configuration.'''
    
    # Need to be corrrectly logged to access guild config
    if not 'guild' in session or session['guild'] != alias:
        return redirect(url_for('auth.login'))
    
    # Fetch guild levels info from database
    query = 'SELECT * FROM levels WHERE guild = :guild'
    levels = await database.fetch_all(query, {'guild': alias})
    
    def r(msg, new_id='', new_filename=''):
        '''Render page and get filename cookies locally.'''
        filenames = {}
        s = 'path_%s_' % alias
        for name, value in request.cookies.items():
            print(name, value)
            if s in name:
                id = name.replace(s, '')
                filenames[id] = value
        if new_id:
            # Add new inserted level on filenames divt on POST request
            filenames[new_id] = new_filename
        print(filenames)
        return render_template('guild.htm', 
                alias=alias, levels=levels, msg=msg, filenames=filenames)

    # Render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Insert new level info on database
    form = await request.form
    query = 'INSERT IGNORE INTO levels VALUES ' \
            '(:guild, :category, :level_id, :path)'
    values = {'guild': alias, 'category': 'Levels',
            'level_id': form['new_id'], 'path': form['new_path']}
    await database.execute(query, values)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server
    levels.append(values)
    # await web_ipc.request('update',
    #         guild_id=session['id'], levels=values)

    # Save cookie for locally setting level filenames and render page
    resp = await make_response(
            await r('Guild info updated successfully!',
                values['level_id'], values['path']))
    name = 'path_%s_%s' % (alias, values['level_id'])
    resp.set_cookie(name, values['path'])
    return resp
