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

    # Get riddle/guild full name from database
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    if not result:
        abort(404)

    # Root can access everything
    try:
        await root_auth()
    except werkzeug.exceptions.Forbidden:
        pass
    else:
        return

    # Check if user is riddle's admin and has rights for it
    user = await discord.get_user()
    query = '''
        SELECT * FROM riddles
        WHERE alias = :alias
            AND creator_username = :username
            AND has_admin_rights IS TRUE
    '''
    values = {'alias': alias, 'username': user.name}    
    is_riddle_admin = bool(await database.fetch_one(query, values))
    if is_riddle_admin:
        return

    # Otherwise, check if user has enough permissions in given guild
    ok = await bot_request(
        'is-member-and-has-permissions',
        guild_id=result['guild_id'],
        username=user.name
    )
    if ok != "True":
        abort(403)


async def is_admin_of(alias: str) -> bool:
    '''Check for admin rights on given riddle.'''
    if not await discord.authorized:
        return False
    try:
        await admin_auth(alias)
    except werkzeug.exceptions.Forbidden:
        return False
    return True
