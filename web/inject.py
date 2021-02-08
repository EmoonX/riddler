from quart import session

from players.auth import discord


async def context_processor():
    '''Inject variables and functions in Jinja.'''
    
    # Get Discord user object and their avatar (if logged in)
    avatar_url = None
    if await discord.authorized:
        user = await discord.fetch_user()
        avatar_url = str(user.avatar_url)

    # Return dict of variables to be injected
    inject = {'session': session, 'avatar_url': avatar_url}
    return inject
