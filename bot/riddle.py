from typing import OrderedDict, DefaultDict

import discord
from discord.utils import get

from bot import bot
from commands.unlock import UnlockHandler
from util.db import database


class Riddle:
    '''Container for guild's riddle levels and info.'''

    guild: discord.Guild
    '''Discord guild object'''

    levels: OrderedDict[str, dict]
    '''Ordered dict of (normal) levels'''
    
    secret_levels: OrderedDict[str, dict]
    '''Ordered dict of secret levels'''

    winners_suffix: str
    '''Suffix to be appended to winners' nicknames'''

    def __init__(self, riddle: dict, levels: dict, secret_levels: dict):
        '''Build riddle object by row extracted from database.'''

        # Get info from guild's database data
        self.guild = get(bot.guilds, name=riddle['full_name'])
        self.winners_suffix = riddle['winners_suffix']

        # Get riddle's level info from database query
        self.levels = OrderedDict()
        for level in levels:
            id = level['name']
            self.levels[id] = level
        self.secret_levels = OrderedDict()
        for level in secret_levels:
            id = level['name']
            self.secret_levels[id] = level

        # Build dict of riddle's unlock handlers
        self.uh_dict = {}
        for member in self.guild.members:
            uh = UnlockHandler(self.guild, self.levels, member)
            self.uh_dict[member] = uh


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: DefaultDict[str, Riddle] = {}


async def build_riddles():
    '''Build riddles dict from database guild and level data.'''
    await database.connect()
    query = 'SELECT * from riddles'
    result = await database.fetch_all(query)
    for row in result:
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS FALSE'
        values = {'riddle': row['alias']}
        levels = await database.fetch_all(query, values)
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE'
        secret_levels = await database.fetch_all(query, values)
        riddle = Riddle(row, levels, secret_levels)
        riddles[row['alias']] = riddle
