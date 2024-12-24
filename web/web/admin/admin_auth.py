from quart import abort
from quartcord import requires_authorization
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
        abort(404)

    # Big boss can access everything 8)
    user = await discord.get_user()
    if user.id == 315940379553955844:
        return

    # Check if user is riddle's creator/admin and has rights for it
    query = '''
        SELECT * FROM riddles
        WHERE alias = :alias
            AND creator_username = :username
            AND has_admin_rights IS TRUE
    '''
    values = {'alias': alias, 'username': user.name}    
    is_creator = await database.fetch_one(query, values)
    if is_creator:
        return

    # Otherwise, check if user has enough permissions in given guild
    ok = await bot_request(
        'is-member-and-has-permissions',
        guild_id=result['guild_id'],
        username=user.name
    )
    if ok != "True":
        abort(401)


async def is_admin_of(alias: str) -> bool:
    '''Quick boolean method to check
    for admin rights for given riddle.'''
    if not await discord.authorized:
        return False
    try:
        await admin_auth(alias)
    except HTTPException:
        return False
    return True
