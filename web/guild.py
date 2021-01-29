from databases.core import Database
from quart import Blueprint, request, render_template, \
        session, redirect, url_for
from MySQLdb.cursors import DictCursor
from discord.ext.ipc import Client

from util import database

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
    
    def r(msg):
        return render_template('guild.htm', 
                alias=alias, levels=levels, msg=msg)

    # Just render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Insert new level info on database
    form = await request.form
    query = 'INSERT IGNORE INTO levels VALUES ' \
            '(:guild, :category, :level_id, :filename)'
    values = {'guild': alias, 'category': 'Levels',
            'level_id': form['new_id'], 'filename': form['new_filename']}
    await database.execute(query, values)

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server
    levels.append(values)
    await web_ipc.request('update',
            guild_id=session['id'], levels=values)

    return await r('Guild info updated successfully!')
