from quart import Blueprint, request, session, \
        render_template, redirect, url_for

from ipc import web_ipc
from util.db import database

# Create app blueprint
account = Blueprint('account', __name__)


@account.route('/settings/', methods=['GET', 'POST'])
async def settings():
    '''Account update form submission.'''
    def r(msg):
        '''Render page with **kwargs.'''
        return render_template('players/settings.htm', msg=msg)
    
    # Render page normally on GET
    if request.method == 'GET':
        return await r('')

    # Must not have logged out meanwhile
    if not 'user' in session:
        return await redirect(url_for("auth.login"))

    # Check if user entered required fields in form
    form = await request.form
    if not 'country' in form:
        return await r('Please fill out the required form fields!')
    
    # Update info in accounts table
    query = 'UPDATE accounts SET country = :country ' \
            'WHERE username = :name AND discriminator = :disc'
    values = {'country': form['country'],
            'name': session['user']['username'],
            'disc': session['user']['discriminator']}
    await database.execute(query, values)

    # Also update session data
    session['user']['country'] = form['country']

    return await r('Account details updated successfully!')
