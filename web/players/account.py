from quart import Blueprint, render_template, session

from util.db import database

# Create app blueprint
account = Blueprint("account", __name__, template_folder="templates")


@account.route("/players/")
async def players():
    """Player list page and table."""

    # Get player data from database
    query = 'SELECT * FROM accounts'
    accounts = await database.fetch_all(query)

    return await render_template("players/index.htm",
            accounts=accounts, session=session)
