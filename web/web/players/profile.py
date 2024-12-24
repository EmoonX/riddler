from quart import Blueprint, render_template

from auth import discortd

# Create app blueprint
profile = Blueprint('profile', __name__)


@profile.route('/user/<username>')
async def player_profile(username: str):
    user = await 
    return await render_template('players/profile.htm', user=user)
