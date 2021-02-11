from pycountry import pycountry
from flag import flag

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
    
    # Get players data from database
    query = 'SELECT * FROM accounts'
    result = await database.fetch_all(query)
    accounts = {account['username']: dict(account)
            for account in result}
    
    async def get_avatar_url(account):
        '''Returns user's avatar url from a request sent to bot.'''
        url = await web_ipc.request('get_avatar_url',
                username=account['username'],
                disc=account['discriminator'])
        return url
    
    # Get emoji flag from alpha_2 code (for players pages titles)
    get_emoji_flag = flag

    # Return dict of variables to be injected
    return locals()
