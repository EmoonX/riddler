from quart import Blueprint, request, render_template, \
        session, redirect, url_for
from MySQLdb.cursors import DictCursor
import bcrypt

from util import database

# Create app blueprint
auth = Blueprint('auth', __name__)


@auth.route('/login/', methods=['GET', 'POST'])
async def login():
    '''Guild login system.'''

    def r(msg):
        return render_template('login.htm', msg=msg)

    # Just render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Check if user entered guild alias and password in form
    form = await request.form
    if not ('alias' in form and 'password' in form):
        return await r('Please fill out the form!')

    # Check if alias exists in database
    alias = form['alias']
    query = 'SELECT * FROM guilds where alias = :alias'
    values = {'alias': alias}
    guild = await database.fetch_one(query, values)
    if not guild:
        return await r('Guild alias doesn\'t exist in database.')

    # Check if password's hash matches stored hash
    password = form['password']
    match = bcrypt.checkpw(
            password.encode('utf-8'), guild['password_hash'].encode('utf-8'))
    if not match:
        return await r('Wrong password.')
    
    # Create session data
    session['guild'] = alias

    # Login is successful, redirect to guild page
    return redirect(url_for("guild.config", alias=alias))


@auth.route('/logout/', methods=['GET'])
async def logout():
    '''Logout from session and return to login page.'''

    # Pop alias from session (if still logged)
    if 'guild' in session:
        session.pop('guild')
    
    return redirect(url_for('auth.login'))
