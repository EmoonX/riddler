from quart import abort
from quartcord import requires_authorization
import werkzeug

from auth import discord
from webclient import bot_request
from util.db import database


@requires_authorization
async def root_auth():
    '''Assert you are really important.'''
    user = await discord.get_user()
    if user.id == 315940379553955844:
        return
    ok = await bot_request(
        'is-member-and-has-permissions',
        guild_id=859797827554770955,  # Wonderland
        username=user.name,
    )
    if ok != 'True':
        abort(403)


@requires_authorization
async def admin_auth(alias: str):
    '''Check if alias is valid and user an admin of guild.'''

    # Get riddle data from DB
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    riddle = await database.fetch_one(query, {'alias': alias})
    if not riddle:
        abort(404)

    # Root can access everything
    try:
        await root_auth()
    except werkzeug.exceptions.Forbidden:
        pass
    else:
        return

    # Check if user is given riddle's creator AND has admin rights for it
    user = await discord.get_user()
    if riddle['creator_username'] == user.name and riddle['has_admin_rights']:
        return

    abort(403)


async def is_admin_of(alias: str) -> bool:
    '''Check for admin rights on given riddle or root.'''
    if not await discord.authorized:
        return False
    try:
        if alias == '*':
            await root_auth()
        else:
            await admin_auth(alias)
    except werkzeug.exceptions.Forbidden:
        return False
    return True
