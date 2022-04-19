import json

import country_converter as coco
from flag import flag
from pycountry import pycountry

from admin.admin_auth import is_admin_of
from auth import discord
from countries import country_names
from riddle import level_ranks, cheevo_ranks
from webclient import bot_request
from util.db import database


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


async def get_achievements(alias: str, user: dict = None) -> dict:
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
            WHERE riddle = :riddle
                AND username = :name AND discriminator = :disc
        '''
        values |= {'name': user['username'], 'disc': user['discriminator']}
    user_cheevos = await database.fetch_all(query, values)

    # Create dict of pairs (rank -> list of cheevos)
    cheevos_by_rank = {'C': [], 'B': [], 'A': [], 'S': []}
    for user_cheevo in user_cheevos:
        cheevo = cheevos[user_cheevo['title']]
        rank = cheevo['rank']
        cheevos_by_rank[rank].append(cheevo)

    return cheevos_by_rank


async def context_processor():
    '''Inject variables and functions in Jinja.'''

    async def get_riddle(alias):
        '''Return riddle info + icon from a given alias.'''

        # Get DB row data
        query = 'SELECT * FROM riddles WHERE alias = :alias'
        riddle = await database.fetch_one(query, {'alias': alias})

        if riddle:
            # Get icon URL by bot request
            url = await bot_request(
                'get-riddle-icon-url', guild_id=riddle['guild_id']
            )
            if not url:
                url = f"/static/riddles/{alias}.png"
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
            url = urls.get(guild_id)
            if not url:
                url = f"/static/riddles/{row['alias']}.png"
            row['icon_url'] = url
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
            query = '''
                SELECT *
                FROM accounts INNER JOIN riddle_accounts
                ON accounts.username = riddle_accounts.username
                    AND accounts.discriminator = riddle_accounts.discriminator
                WHERE riddle = :riddle
            '''
            values = {'riddle': alias}
            accounts = await database.fetch_all(query, values)
        accounts = {account['username']: account for account in accounts}
        return accounts

    def is_authorized() -> bool:
        '''Return if the user is currently logged in.'''
        return discord.authorized

    async def get_session_user():
        '''Return current Discord OAuth2 session user.'''
        user = await discord.get_user()
        return user

    async def get_avatar_url(username: str, disc: str):
        '''Returns user's avatar url from a request sent to bot.'''
        url = await bot_request(
            'get-avatar-url', username=username, disc=disc
        )
        return url

    async def fetch_avatar_urls(guild_id: int = None):
        '''Fetch avatar URLs from bot request, parse then and return a dict.
        If `guild` is present, fetch only from given guild;
        otherwise, return all avatars bot has access.'''

        # data = None
        # if guild_id:
        # if False:
        #     data = await bot_request('fetch-avatar-urls', guild_id=guild_id)
        # else:
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

    async def get_user_country(username: str = None, disc: str = None):
        '''Ǵet user's country code.
        If no username or disc is given, use current user.'''

        if not username:
            user = await discord.get_user()
            username = user.name
            disc = user.discriminator
        query = '''
            SELECT * FROM accounts
            WHERE username = :name AND discriminator = :disc
        '''
        values = {'name': username, 'disc': disc}
        result = await database.fetch_one(query, values)
        country = result['country']
        return country

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
        'level_ranks': level_ranks, 'cheevo_ranks': cheevo_ranks,
        'get_riddles': get_riddles, 'get_achievements': get_achievements,
        'country_names': country_names,
        'is_admin_of': is_admin_of,
        'get_emoji_flag': flag, 'pycountries': pycountry.countries,
    }
    # Return concatenated dict with pairs ("var" -> var_value)
    return locals() | extra
