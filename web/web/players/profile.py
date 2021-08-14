from quart import Blueprint, render_template

# Create app blueprint
profile = Blueprint('profile', __name__)


@profile.route('/players/<username>/<disc>')
async def player_profile(username: str, disc: str = None):
    return await render_template('players/profile.htm',
            username=username, disc=disc)
