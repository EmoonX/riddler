import json
import os
from typing import overload

from babel import Locale
from babel.core import get_global
import country_converter as coco
from flag import flag
from pycountry import pycountry

from admin.admin_auth import is_admin_of
from auth import discord
from countries import country_names
from levels import get_root_path
from players.account import is_user_incognito
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
    riddle['root_path'] = await get_root_path(alias)

    # Get icon URL
    riddle['icon_url'] = f"/static/riddles/{alias}.png"

    return riddle


async def get_riddles(
    unlisted: bool = False, include_counters: bool = False
) -> list[dict]:
    '''
    Return a list of all riddles.
        :param unlisted: Whether to also return unlisted riddles.
        :param include_counters: Whether to include counter data.
    '''

    query = f"""
        SELECT * FROM riddles
        {'WHERE unlisted IS NOT TRUE' if not unlisted else ''}
    """
    riddles = [dict(row) for row in await database.fetch_all(query)]
    if not include_counters:
        return riddles

    # Add counter data
    for riddle in riddles:
        query = '''
            SELECT COUNT(*) FROM riddle_accounts
            WHERE riddle = :riddle AND score > 0
        '''
        values = {'riddle': riddle['alias']}
        riddle['player_count'] = await database.fetch_val(query, values)
        query = '''
            SELECT COUNT(*) FROM levels
            WHERE riddle = :riddle
        '''
        riddle['level_count'] = await database.fetch_val(query, values)
        query = '''
            SELECT COUNT(*) FROM achievements
            WHERE riddle = :riddle
        '''
        riddle['achievement_count'] = await database.fetch_val(query, values)
        query = '''
            SELECT COUNT(*), SUM(level_name IS NOT NULL AND hidden IS NOT TRUE)
            FROM level_pages
            WHERE riddle = :riddle
        '''
        result = await database.fetch_one(query, values)
        riddle['raw_page_count'], riddle['page_count'] = result.values()
    return riddles


async def get_levels(alias: str) -> dict[str, dict]:
    query = '''
        SELECT * FROM levels
        WHERE riddle = :riddle
        ORDER BY set_index, `index`
    '''
    ordered_levels = await database.fetch_all(query, {'riddle': alias})
    return {level['name']: dict(level) for level in ordered_levels}


async def get_achievements(
    alias: str, account: dict | None = None
) -> dict[str, dict]:
    '''Get riddle achievements grouped by points.
    If user is specified, then only return cheevos user has gotten.'''

    # Build dict of cheevos with titles as keys
    query = 'SELECT * FROM achievements WHERE riddle = :riddle'
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    all_cheevos = {row['title']: dict(row) for row in result}

    user = await discord.get_user() if discord.user_id else None
    if not account:
        # Get riddle's achievement list
        query = 'SELECT * FROM achievements WHERE riddle = :riddle'
    else:
        # Get user's riddle achievement list
        query = '''
            SELECT * FROM user_achievements
            WHERE riddle = :riddle AND username = :username
        '''
        if not user or account['username'] != user.name:
            query += 'AND incognito IS NOT TRUE'
        values |= {'username': account['username']}
    cheevos = await database.fetch_all(query, values)

    # Get unlocked achievements for current session user (if any)
    unlocked_cheevos = set()
    if user:
        query = '''
            SELECT * FROM user_achievements
            WHERE riddle = :riddle AND username = :username
        '''
        values = {'riddle': alias, 'username': user.name}
        result = await database.fetch_all(query, values)
        unlocked_cheevos = {cheevo['title'] for cheevo in result}

    # Create dict of pairs (rank -> list of cheevos)
    cheevos_by_rank = {rank: [] for rank in 'CBAS'}
    for cheevo in cheevos:
        cheevo = all_cheevos[cheevo['title']]
        cheevo |= {'unlocked': cheevo['title'] in unlocked_cheevos}
        cheevos_by_rank[cheevo['rank']].append(cheevo)

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

    async def get_session_user() -> User | None:
        '''Return current Discord OAuth2 session user (if any).'''
        if not discord.user_id:
            return None
        return await discord.get_user()

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

    def file_exists(absolute_path: str) -> bool:
        '''Check whether file exists in the given path.'''
        return os.path.exists(f"..{absolute_path}")

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

    # Country -> language mapping for `/riddles`
    territories = get_global('territory_languages')

    # Dict for extra variables
    extra = {
        'get_riddle': get_riddle,
        'get_riddles': get_riddles,
        'get_achievements': get_achievements,
        'get_accounts': get_accounts,
        'get_display_name': get_display_name,
        'is_user_incognito': is_user_incognito,
        'level_ranks': level_ranks,
        'cheevo_ranks': cheevo_ranks,
        'country_names': country_names,
        'is_admin_of': is_admin_of,
        'get_emoji_flag': flag,
        'Locale': Locale,
        'pycountries': pycountry.countries,
        'territories': territories,
    }
    # Return concatenated dict with pairs (var -> var_value)
    return locals() | extra
