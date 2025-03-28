from typing import OrderedDict, DefaultDict

import discord
from discord.utils import get

from bot import bot
from util.db import database


class Riddle:
    '''Container for guild's riddle levels and info.'''

    full_name: str
    '''Riddle's full name.'''

    guild: discord.Guild = None
    '''Discord guild object.'''

    levels: OrderedDict[str, dict]
    '''Ordered dict of (normal) levels.'''

    secret_levels: OrderedDict[str, dict]
    '''Ordered dict of secret levels.'''

    def __init__(self, riddle: dict, levels: dict, secret_levels: dict):
        '''Build riddle object by row extracted from database.'''

        # Get info from guild's database data
        self.full_name = riddle['full_name']
        if riddle['guild_id']:
            self.guild = get(bot.guilds, id=int(riddle['guild_id']))

        # Get riddle's level info from database query
        self.levels = {}
        for level in levels:
            id = level['name']
            self.levels[id] = level
        self.secret_levels = {}
        for level in secret_levels:
            id = level['name']
            self.secret_levels[id] = level


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: DefaultDict[str, Riddle] = {}


async def build_riddles():
    '''Build riddles dict from database guild and level data.'''

    await database.connect()
    query = 'SELECT * from riddles'
    result = await database.fetch_all(query)
    for row in result:
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle AND is_secret IS NOT TRUE
        '''
        values = {'riddle': row['alias']}
        levels = await database.fetch_all(query, values)
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle AND is_secret IS TRUE
        '''
        secret_levels = await database.fetch_all(query, values)
        riddle = Riddle(row, levels, secret_levels)
        riddles[row['alias']] = riddle
