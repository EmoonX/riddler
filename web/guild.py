from quart import Blueprint, request, render_template, \
        session, redirect, url_for
from MySQLdb.cursors import DictCursor
from discord.ext.ipc import Client

from util import mysql

# Create app blueprint
guild = Blueprint('guild', __name__)

# Web client for inter-process communication with discord.py bot
web_ipc = Client(secret_key='RASPUTIN')


@guild.before_app_first_request
async def discover():
    '''Discover bot IPC server on network.'''
    guild.ipc_node = await web_ipc.discover()


@guild.route('/guild/<guild>/', methods=('GET', 'POST'))
async def config(guild: str):
    '''Guild configuration.'''

    def r(msg):
        return render_template('guild.htm', msg=msg, alias=guild)
    
    # Need to be corrrectly logged to access guild config
    if not 'guild' in session or session['guild'] != guild:
        return redirect(url_for('auth.login'))

    # Just render page normally on GET
    if request.method == 'GET':
        return r('')
    
    category = 'Levels'
    level_id = '001'
    filename = 'potato'

    # Insert level info on database
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute('INSERT INTO levels VALUES (%s, %s, %s, %s)',
            (session['guild'], category, level_id, filename))
    mysql.connection.commit()

    cursor.execute('SELECT * FROM levels WHERE guild = %s',
            (session['guild'],))
    levels = cursor.fetchall()

    # Update Discord guild channels and roles with new levels info.
    # This is done by sending an request to the bot's IPC server
    await guild.ipc_node.request('update', levels=levels)

    return r('Guild info updated successfully!')
