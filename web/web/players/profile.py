from quart import Blueprint, render_template

from auth import discord

# Create app blueprint
profile = Blueprint('profile', __name__)


@profile.route('/user/<username>')
async def player_profile(username: str):
    user = await discord.get_user()
    return await render_template('players/profile.htm',
        username=username, disc=user.discriminator
    )
