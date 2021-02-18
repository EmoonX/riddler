from pycountry import pycountry
from flag import flag

from ipc import web_ipc
from util.db import database

# Colors for achievements outline based on ranks
cheevo_colors = {
    'C': 'firebrick',
    'B': 'lightcyan',
    'A': 'gold',
    'S': 'darkturquoise'
}


async def get_achievements(alias: str, user: dict = None):
    '''Get riddle achievements grouped by points.
    If user is specified, return only cheevos user has gotten'''
    
    if not user:
        # Get riddle's achievement list
        query = 'SELECT title FROM achievements ' \
                'WHERE riddle = :riddle '
        values = {'riddle': alias}
    else:
        # Get user's riddle achievement list
        query = 'SELECT title FROM user_achievements ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'riddle': alias,
                'name': user['username'], 'disc': user['discriminator']}
    result = await database.fetch_all(query, values)
    
    # Create dict of pairs (rank -> list of cheevos)
    cheevos = {'C': [], 'B': [], 'A': [], 'S': []}
    for row in result:
        title = row['title']
        query = 'SELECT * FROM achievements ' \
                'WHERE riddle = :riddle AND title = :title'
        values = {'riddle': alias, 'title': title}
        cheevo = await database.fetch_one(query, values)
        cheevo = dict(cheevo)
        rank = cheevo['rank']
        cheevo['color'] = cheevo_colors[rank]
        cheevos[rank].append(cheevo)
    
    # Ignore ranks without cheevos
    erasable = []
    for key, value in cheevos.items():
        if not value:
            erasable.append(key)
    for key in erasable:
        cheevos.pop(key)

    return cheevos
    

async def context_processor():
    '''Inject variables and functions in Jinja.'''

    # List of pycountry country objects
    pycountries = pycountry.countries

    async def get_accounts(alias=''):
        '''Get players data from database.
            riddle: if present, also get riddle-specific data.'''
        accounts = []
        if not alias:
            query = 'SELECT * FROM accounts'
            accounts = await database.fetch_all(query)
        else:
            query = 'SELECT * FROM accounts ' \
                    'INNER JOIN riddle_accounts ' \
                    'ON accounts.username = riddle_accounts.username ' \
                        'AND accounts.discriminator ' \
                        '= riddle_accounts.discriminator ' \
                    'WHERE riddle = :riddle'
            values = {'riddle': alias}
            accounts = await database.fetch_all(query, values)
        accounts = {account['username']: account for account in accounts}
        return accounts

    def get_sorted_countries():
        '''Get sorted list of countries by name.'''
        def comp_names(country):
            '''Sort countries by real name (instead of alpha_2).'''
            return country.name
        countries = list(pycountries)
        countries.sort(key=comp_names)
        return countries
    
    async def get_avatar_url(account):
        '''Returns user's avatar url from a request sent to bot.'''
        url = await web_ipc.request('get_avatar_url',
                username=account['username'],
                disc=account['discriminator'])
        return url

    # Dict for extra variables
    extra = {
        'cheevo_colors': cheevo_colors,
        'get_achievements': get_achievements, 'get_emoji_flag': flag
    }
    # Return concatenated dict with pairs ("var" -> var_value)
    return {**locals(), **extra}
