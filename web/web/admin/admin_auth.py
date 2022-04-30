from quart import abort
from quart_discord import requires_authorization
from werkzeug.exceptions import HTTPException

from auth import discord
from webclient import bot_request
from util.db import database


@requires_authorization
async def root_auth() -> bool:
    '''Check if you are... Emoon.'''
    user = await discord.get_user()
    return user.id == 315940379553955844


@requires_authorization
async def admin_auth(alias: str):
    '''Check if alias is valid and user an admin of guild.'''

    # Get riddle/guild full name from database
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    if not result:
        # Invalid alias...
        abort(404)

    # Big boss can access everything 8)
    user = await discord.get_user()
    if user.id == 315940379553955844:
        return

    # Check if user is riddle's creator/admin
    query = '''
        SELECT * FROM riddles
        WHERE alias = :alias
            AND creator_username = :username AND creator_disc = :disc
    '''
    values = {
        'alias': alias,
        'username': user.name, 'disc': user.discriminator
    }
    is_creator = await database.fetch_one(query, values)
    if is_creator:
        return

    # Otherwise, check if user has enough permissions in given guild
    ok = await bot_request(
        'is-member-and-has-permissions',
        guild_id=result['guild_id'],
        username=user.name, disc=user.discriminator
    )
    if ok != "True":
        abort(401)


async def is_admin_of(alias: str) -> bool:
    if not await discord.authorized:
        return False
    try:
        await admin_auth(alias)
    except HTTPException:
        return False
    return True