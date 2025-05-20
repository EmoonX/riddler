import json
from typing import overload

import country_converter as coco
from flag import flag
from pycountry import pycountry

from admin.admin_auth import is_admin_of
from auth import discord
from countries import country_names
from riddles import level_ranks, cheevo_ranks, player_ranks
from webclient import bot_request
from util.db import database


async def get_riddle(alias: str) -> dict:
    '''Return riddle info + icon from a given alias.'''

    # Get DB row data
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    riddle = await database.fetch_one(query, {'alias': alias})
    if not riddle:
        return None

    # Account for multi-root-path riddles
    riddle = dict(riddle)
    if riddle['root_path'][0] == '[':
        riddle['root_path'] = riddle['root_path'].split('"')[1]

    # Get icon URL
    riddle['icon_url'] = f"/static/riddles/{alias}.png"

    return riddle


async def get_riddles(unlisted: bool = False) -> list[dict]:
    '''
    Return a list of all riddles.
    :param unlisted: Whether to also return unlisted riddles.
    '''
    query = f"""
        SELECT * FROM riddles
        {'WHERE unlisted IS NOT TRUE' if not unlisted else ''}
    """
    riddles = await database.fetch_all(query)
    return riddles


async def get_levels(alias: str) -> dict[str, dict]:
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle
        ORDER BY set_index, `index`
    '''
    ordered_levels = await database.fetch_all(query, {'riddle': alias})
    return {level['name']: dict(level) for level in ordered_levels}


async def get_achievements(alias: str, user: dict = None) -> dict[str, dict]:
    '''Get riddle achievements grouped by points.
    If user is specified, then only return cheevos user has gotten.'''

    # Build dict of cheevos with titles as keys
    query = 'SELECT * FROM achievements WHERE riddle = :riddle'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    cheevos = {row['title']: dict(row) for row in result}

    if not user:
        # Get riddle's achievement list
        query = 'SELECT * FROM achievements WHERE riddle = :riddle '
    else:
        # Get user's riddle achievement list
        query = '''
            SELECT * FROM user_achievements
            WHERE riddle = :riddle AND username = :name
        '''
        values |= {'name': user['username']}
    user_cheevos = await database.fetch_all(query, values)

    # Create dict of pairs (rank -> list of cheevos)
    cheevos_by_rank = {'C': [], 'B': [], 'A': [], 'S': []}
    for user_cheevo in user_cheevos:
        cheevo = cheevos[user_cheevo['title']]
        rank = cheevo['rank']
        cheevos_by_rank[rank].append(cheevo)

    return cheevos_by_rank


async def get_accounts(alias: str | None = None):
    '''Get players data from database.

    :param alias: if present, also get riddle-specific data.'''

    if not alias:
        query = 'SELECT * FROM accounts'
        accounts = await database.fetch_all(query)
    else:
        query = '''
            SELECT *
            FROM accounts INNER JOIN riddle_accounts
                ON accounts.username = riddle_accounts.username
            WHERE riddle = :riddle
        '''
        values = {'riddle': alias}
        accounts = await database.fetch_all(query, values)

    accounts = {
        account['username']: account
        for account in accounts
    }
    return accounts


@overload
async def get_display_name(user: dict):
    ...

@overload
async def get_display_name(username: str):
    ...

async def get_display_name(user):
    '''Get display name from either username or user dict.'''

    if isinstance(user, str) or 'display_name' not in user:
        username = user if isinstance(user, str) else user['username']
        query = '''
            SELECT display_name, username FROM accounts
            WHERE username = :username
        '''
        values = {'username': username}
        user = await database.fetch_one(query, values)
    
    return user['display_name'] or user['username']


async def context_processor():
    '''Inject variables and functions in Jinja.'''

    async def fetch_riddles() -> list[dict]:
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
            url = urls.get(guild_id)
            if not url:
                url = f"/static/riddles/{row['alias']}.png"
            row['icon_url'] = url
            riddles[row['alias']] = row

        return riddles

    def is_authorized() -> bool:
        '''Return if the user is currently logged in.'''
        return discord.authorized

    async def get_session_user():
        '''Return current Discord OAuth2 session user.'''
        user = await discord.get_user()
        return user

    async def get_avatar_url(username: str = None, discord_id: int = None):
        '''Returns user's avatar url from a request sent to bot.'''
        url = await bot_request('get-avatar-url', discord_id=discord_id)
        return url

    async def get_all_avatar_urls(guild_id: int = None):

        # data = None
        # if guild_id:
        # if False:
        #     data = await bot_request('fetch-avatar-urls', guild_id=guild_id)
        # else:
        # data = await bot_request('fetch-avatar-urls')
        
        query = '''
            SELECT username, discord_id, avatar_url FROM accounts
            WHERE discord_id IS NOT NULL
        '''
        result = await database.fetch_all(query)
        discord_ids = set(row['discord_id'] for row in result)
        
        data = await bot_request('get-all-avatar-urls', discord_ids=discord_ids)
        urls = json.loads(data)
        
        for row in result:
            if row['username'] in urls or not row['avatar_url']:
                continue
            urls[row['username']] = row['avatar_url']
        
        return urls

    def get_sorted_countries():
        '''Get sorted list of country pairs (short_name, alpha_2).'''

        countries = []
        for alpha_2, short_name in country_names.items():
            country = (short_name, alpha_2)
            countries.append(country)
        countries.sort()
        return countries

    async def get_user_country(username: str = None):
        '''Ǵet user's country code.
        If no username is given, use current user.'''

        if not username:
            user = await discord.get_user()
            username = user.name
        query = '''
            SELECT * FROM accounts
            WHERE username = :name
        '''
        values = {'name': username}
        result = await database.fetch_one(query, values)
        country = result['country']
        return country

    def get_score_ranked_color(user: dict):
        '''Get rank color based on score lower bound.'''
        for rank in player_ranks:
            if user['global_score'] >= rank['min_score']:
                return rank['color']

    # Build dict of country names
    # (also a separate loop for UK nations)
    cc = coco.CountryConverter()
    for country in pycountry.countries:
        alpha_2 = country.alpha_2
        name = cc.convert(alpha_2, to='short_name')
        country_names[alpha_2] = name
    uk_nations = (
        ('GB-ENG', 'England'), ('GB-SCT', 'Scotland'),
        ('GB-WLS', 'Wales'), ('GB-NIR', 'Northern Ireland')
    )
    for country in uk_nations:
        code = country[0]
        name = f"United Kingdom ({country[1]})"
        country_names[code] = name

    # Dict for extra variables
    extra = {
        'get_riddle': get_riddle,
        'get_riddles': get_riddles,
        'get_achievements': get_achievements,
        'get_accounts': get_accounts,
        'get_display_name': get_display_name,
        'level_ranks': level_ranks,
        'cheevo_ranks': cheevo_ranks,
        'country_names': country_names,
        'is_admin_of': is_admin_of,
        'get_emoji_flag': flag,
        'pycountries': pycountry.countries,
    }
    # Return concatenated dict with pairs (var -> var_value)
    return locals() | extra
