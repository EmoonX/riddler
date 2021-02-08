from quart import session
from pycountry import pycountry

from players.auth import discord


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

    # Return dict of variables to be injected
    return locals()
