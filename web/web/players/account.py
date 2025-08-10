from quart import Blueprint, request, render_template
from quartcord import requires_authorization

from auth import discord
from inject import country_names
from util.db import database

# Create app blueprint
account = Blueprint('account', __name__)


@account.route('/settings', methods=['GET', 'POST'])
@requires_authorization
async def settings():
    '''Account update form submission.'''

    def r(msg):
        '''Render page with **kwargs.'''
        return render_template('players/settings.htm', user=user, msg=msg)

    # Render page normally on GET
    user = await discord.get_user()
    if request.method == 'GET':
        return await r('')

    # Check if user entered required fields in form
    form = await request.form
    if not 'country' in form:
        return await r('Please fill out the required form fields!')

    # Check if user tried to submit a phony country code
    country = country_names.get(form['country'])
    if not country:
        return await r('Something went wrong. Please try again.')

    # Update info in accounts table
    query = '''
        UPDATE accounts
        SET country = :country, incognito = :incognito
        WHERE username = :username
    '''
    values = {
        'username': user.name,
        'country': form['country'],
        'incognito': 'incognito' in form,
    }
    await database.execute(query, values)

    return await r('Account details successfully updated!')


async def is_user_incognito() -> bool:
    '''Return whether user has incognito mode activated.'''
    user = await discord.get_user()
    query = '''
        SELECT incognito FROM accounts
        WHERE username = :username
    '''
    return await database.fetch_val(query, {'username': user.name})
