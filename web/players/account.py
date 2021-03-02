from quart import Blueprint, request, session, \
        render_template, redirect, url_for
from quart_discord import requires_authorization

from auth import discord
from util.db import database

# Create app blueprint
account = Blueprint('account', __name__)


@account.route('/settings', methods=['GET', 'POST'])
@requires_authorization
async def settings():
    '''Account update form submission.'''
    
    def r(msg):
        '''Render page with **kwargs.'''
        return render_template('players/settings.htm',
                user=user, msg=msg)
    
    # Render page normally on GET
    user = await discord.fetch_user()
    if request.method == 'GET':
        return await r('')

    # Check if user entered required fields in form
    form = await request.form
    if not 'country' in form:
        return await r('Please fill out the required form fields!')
    
    # Update info in accounts table
    query = 'UPDATE accounts SET country = :country ' \
            'WHERE username = :name AND discriminator = :disc'
    values = {'country': form['country'],
            'name': user.name, 'disc': user.discriminator}
    await database.execute(query, values)

    # Also update session data
    session['country'] = form['country']

    return await r('Account details updated successfully!')
