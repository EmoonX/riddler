from quart import Blueprint, render_template

# Create app blueprint
profile = Blueprint('profile', __name__)


@profile.route('/user/<username>')
async def player_profile(username: str):
    return await render_template('players/profile.htm', username=username)
