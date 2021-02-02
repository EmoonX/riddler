from quart import Blueprint, request, render_template, \
        session, redirect, url_for, make_response

from ipc import web_ipc
from util.db import database

# Create app blueprint
guild = Blueprint('guild', __name__)


@guild.route('/guild/<alias>/', methods=['GET', 'POST'])
async def config(alias: str):
    '''Guild configuration.'''
    
    # Need to be corrrectly logged to access guild config
    if not 'guild' in session or session['guild'] != alias:
        return redirect(url_for('auth.login'))
    
    # Fetch guild levels info from database
    query = 'SELECT * FROM levels WHERE guild = :guild'
    levels = await database.fetch_all(query, {'guild': alias})
    query = 'SELECT * FROM secret_levels WHERE guild = :guild'
    secret_levels = await database.fetch_all(query, {'guild': alias})
    
    def r(msg):
        '''Render page and get filename cookies locally.'''
        return render_template('guild.htm', 
                alias=alias, levels=levels,
                secret_levels=secret_levels, msg=msg)

    # Render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Insert new level and secret_level info on database
    form = await request.form
    query = 'INSERT IGNORE INTO levels VALUES ' \
            '(:guild, :category, :level_id, :path)'
    levels_values = {'guild': alias, 'category': 'Levels',
            'level_id': form['new_id'], 'path': form['new_path']}
    if '' not in levels_values.values():
        await database.execute(query, levels_values)
    query = 'INSERT IGNORE INTO secret_levels VALUES ' \
            '(:guild, :category, :level_id, :path)'
    secret_levels_values = {'guild': alias, 'category': 'Levels',
            'level_id': form['new_secret_id'], 'path': form['new_secret_path']}
    if '' not in secret_levels_values.values():
        await database.execute(query, secret_levels_values)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server
    levels.append(levels_values)
    secret_levels.append(secret_levels_values)
    await web_ipc.request('update',
            guild_id=session['id'],
            levels=levels_values, secret_levels=secret_levels_values)

    return r('Guild info updated successfully!')

