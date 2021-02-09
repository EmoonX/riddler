from pycountry import pycountry
from flag import flag

from players.auth import discord
from ipc import web_ipc
from util.db import database


async def context_processor():
    '''Inject variables and functions in Jinja.'''

    # List of pycountry country objects
    pycountries = pycountry.countries

    def get_sorted_countries():
        '''Get sorted list of countries by name.'''
        def comp_names(country):
            '''Sort countries by real name (instead of alpha_2).'''
            return country.name
        countries = list(pycountries)
        countries.sort(key=comp_names)
        return countries
    
    # Get Discord user object and their avatar (if logged in)
    avatar_url = None
    if await discord.authorized:
        user = await discord.fetch_user()
        avatar_url = str(user.avatar_url)
    
    # Get players data from database
    query = 'SELECT * FROM accounts'
    result = await database.fetch_all(query)
    accounts = {account['username']: dict(account)
            for account in result}

    for account in accounts.values():
        # Get players' avatar URLs
        url = await web_ipc.request('get_avatar_url',
                username=account['username'],
                disc=account['discriminator'])
        account['avatar_url'] = url
    
    # Get emoji flag from alpha_2 code (for players pages titles)
    get_emoji_flag = flag

    # Return dict of variables to be injected
    return locals()
