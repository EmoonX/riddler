from quart import Blueprint, request, session, \
        render_template, redirect, url_for

from ipc import web_ipc
from util.db import database

# Create app blueprint
account = Blueprint("account", __name__, template_folder="templates")


@account.route("/players/")
async def players():
    """Player list page and table."""

    # Get riddles data from database
    query = 'SELECT * from riddles'
    result = await database.fetch_all(query)
    riddles = [dict(riddle) for riddle in result]

    # Get riddles' icon URLs
    for riddle in riddles:
        url = await web_ipc.request('get_riddle_icon_url',
                id=riddle['guild_id'])
        riddle['icon_url'] = url
    
    # Get players data from database
    query = 'SELECT * FROM accounts'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]

    # Get players' avatar URLs
    for account in accounts:
        url = await web_ipc.request('get_avatar_url',
                username=account['username'], disc=account['discriminator'])
        account['avatar_url'] = url

        # Build list of riddle current account plays
        account['riddles'] = []
        for riddle in riddles:
            query = 'SELECT * FROM riddle_accounts WHERE ' \
                    'riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
            values = {'riddle': riddle['alias'],
                    'name': account['username'], 'disc': account['discriminator']}
            found = await database.fetch_one(query, values)
            if found:
                account['riddles'].append(riddle)

    # Render page with account info
    return await render_template('players/index.htm',
            riddles=riddles, accounts=accounts)


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
