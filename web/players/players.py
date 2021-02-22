from quart import Blueprint, render_template

from ipc import web_ipc
from util.db import database

# Create app blueprint
players = Blueprint('players', __name__)


@players.route("/players/")
async def global_list():
    """Global player list."""

    # Get riddles data from database
    query = 'SELECT * from riddles'
    result = await database.fetch_all(query)
    riddles = [dict(riddle) for riddle in result]

    # Get riddles' icon URLs
    for riddle in riddles:
        url = await web_ipc.request('get_riddle_icon_url',
                name=riddle['full_name'])
        riddle['icon_url'] = url
    
    # Get players data from database
    query = 'SELECT * FROM accounts'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]
    
    for account in accounts:
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
    return await render_template('players/list.htm',
            accounts=accounts, riddles=riddles)


@players.route("/<alias>/players/")
async def riddle_list(alias: str):
    """Riddle player list."""

    # Get riddle data from database
    query = 'SELECT * from riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    riddle = dict(result)

    # Get riddles' icon URL
    url = await web_ipc.request('get_riddle_icon_url',
                name=riddle['full_name'])
    riddle['icon_url'] = url
    
    # Get players data from database
    query = 'SELECT * FROM riddle_accounts WHERE riddle = :riddle'
    result = await database.fetch_all(query, {'riddle': alias})
    accounts = [dict(account) for account in result]

    # Get players' countries
    for account in accounts:
        query = 'SELECT * FROM accounts WHERE ' \
                'username = :name AND discriminator = :disc'
        values = {'name': account['username'],
                'disc': account['discriminator']}
        result = await database.fetch_one(query, values)
        account['country'] = result['country']

    # Render page with account info
    return await render_template('players/riddle/list.htm', riddle=riddle)
