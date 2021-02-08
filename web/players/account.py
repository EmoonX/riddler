from quart import Blueprint, render_template, session

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

    # Get players' avatar URLs
    for riddle in riddles:
        url = await web_ipc.request('get_riddle_icon_url',
                id=riddle['guild_id'])
        riddle['icon_url'] = url
        print(url)

    # Get players data from database
    query = 'SELECT * FROM accounts'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]

    # Get players' avatar URLs
    for account in accounts:
        url = await web_ipc.request('get_avatar_url',
                username=account['username'], disc=account['discriminator'])
        account['avatar_url'] = url

    # Render page with account info
    return await render_template("players/index.htm",
            riddles=riddles, accounts=accounts)
