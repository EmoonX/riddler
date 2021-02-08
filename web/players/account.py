from quart import Blueprint, render_template

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
    return await render_template("players/index.htm",
            riddles=riddles, accounts=accounts)