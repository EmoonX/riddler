import json

from pycountry import pycountry
import country_converter as coco
from flag import flag

from auth import discord
from countries import country_names
from webclient import bot_request
from util.db import database


# Dict of pairs rank -> (points, color)
f = lambda p, c : {'points': p, 'color': c}
level_ranks = {
    'D': f(50, 'cornflowerblue'),
    'C': f(100, 'lawngreen'),
    'B': f(200, 'gold'),
    'A': f(400, 'crimson'),
    'S': f(1000, 'lightcyan')
}

# Colors for achievements outline based on ranks
g = lambda e, p, s, c, d : \
        {'emoji': e, 'points': p, 'size': s, 'color': c, 'description': d}
cheevo_ranks = {
    'C': g('🥉', 50, 40, 'firebrick', '"Dumb" and/or easy-to-reach cheevos.'),
    'B': g('🥈', 100, 50, 'lightcyan', 'Substancial ones that require creativity and/or out-of-the-box thinking.'),
    'A': g('🥇', 200, 60, 'gold', 'Good challenges like secret levels or very well hidden eggs.'),
    'S': g('💎', 500, 80, 'darkturquoise', 'Should be reserved for the best among the best (like reaching a vital game\'s landmark).')
}


async def get_riddles(unlisted=False):
    '''Return list of all riddles from DB.
    
    :param unlisted: if True, returns also unlisted riddles'''
    query = ''
    if not unlisted:
        query = 'SELECT * FROM riddles WHERE unlisted IS FALSE'
    else:
        query = 'SELECT * FROM riddles'
    riddles = await database.fetch_all(query)
    return riddles


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
        cheevo['color'] = cheevo_ranks[rank]['color']
        cheevos[rank].append(cheevo)
    
    # # Ignore ranks without cheevos
    # erasable = []
    # for key, value in cheevos.items():
    #     if not value:
    #         erasable.append(key)
    # for key in erasable:
    #     cheevos.pop(key)

    return cheevos
    

async def context_processor():
    '''Inject variables and functions in Jinja.'''
    
    async def get_riddle(alias):
        '''Return riddle info + icon from a given alias.'''
        
        # Get DB row data
        query = 'SELECT * FROM riddles WHERE alias = :alias'
        riddle = await database.fetch_one(query, {'alias': alias})
        
        if riddle:
            # Get icon URL by bot request
            url = await bot_request('get-riddle-icon-url',
                    guild_id=riddle['guild_id'])
            riddle = dict(riddle)
            riddle['icon_url'] = url
        
        return riddle

    async def fetch_riddles():
        '''Return all riddles info + icons.'''
        
        # Get DB row data
        query = 'SELECT * FROM riddles'
        result = await database.fetch_all(query)
        
        # Fetch icon URLs by bot request
        data = await bot_request('fetch-riddle-icon-urls')
        urls = json.loads(data)

        # Build dict of riddles
        riddles = {}
        for row in result:
            row = dict(row)
            guild_id = str(row['guild_id'])
            row['icon_url'] = urls[guild_id]
            riddles[row['alias']] = row
        
        return riddles

    async def get_accounts(alias=''):
        '''Get players data from database.
        
        :param alias: if present, also get riddle-specific data.'''
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
    
    def is_authorized() -> bool:
        '''Return if the user is currently logged in.'''
        return discord.authorized
    
    async def get_session_user():
        '''Return current Discord OAuth2 session user.'''
        user = await discord.fetch_user()
        return user
    
    async def get_avatar_url(username: str, disc: str):
        '''Returns user's avatar url from a request sent to bot.'''
        url = await bot_request('get-avatar-url',
                username=username, disc=disc)
        return url
    
    async def fetch_avatar_urls(guild_id: int = None):
        '''Fetch avatar URLs from bot request, parse then and return a dict.
        If `guild` is present, fetch only from given guild;
        otherwise, return all avatars bot has access.'''
        data = None
        if guild_id:
            data = await bot_request('fetch-avatar-urls', guild_id=guild_id)
        else:
            data = await bot_request('fetch-avatar-urls')
        urls = json.loads(data)
        return urls

    def get_sorted_countries():
        '''Get sorted list of country pairs (short_name, alpha_2).'''
        countries = []
        for alpha_2, short_name in country_names.items():
            country = (short_name, alpha_2)
            countries.append(country)
        countries.sort()
        return countries
    
    async def get_user_country():
        '''Ǵet current user's country code.'''
        user = await discord.fetch_user()
        query = 'SELECT * FROM accounts ' \
                'WHERE username = :name AND discriminator = :disc'
        values = {'name': user.name, 'disc': user.discriminator}
        result = await database.fetch_one(query, values)
        country = result['country']
        return country
    
    # Build dict of country names
    cc = coco.CountryConverter()
    for country in pycountry.countries:
        alpha_2 = country.alpha_2
        short_name = cc.convert(alpha_2, to='short_name')
        country_names[alpha_2] = short_name

    # Dict for extra variables
    extra = {
        'level_ranks': level_ranks, 'cheevo_ranks': cheevo_ranks,
        'get_riddles': get_riddles, 'get_achievements': get_achievements,
        'country_names': country_names, 'get_emoji_flag': flag,
        'pycountries': pycountry.countries
    }
    # Return concatenated dict with pairs ("var" -> var_value)
    return {**locals(), **extra}
