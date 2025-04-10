from typing import Self

import discord
from discord.utils import get
from more_itertools import partition

from bot import bot
from util.db import database


class Riddle:
    '''Container for riddle's info and levels.'''

    alias: str
    '''Riddle's short lowercase alphanumeric alias.'''

    full_name: str
    '''Riddle's full name.'''

    guild: discord.Guild | None = None
    '''Discord guild object.'''

    levels: dict[str, dict]
    '''Ordered dict of (normal) levels.'''

    secret_levels: dict[str, dict]
    '''Ordered dict of secret levels.'''

    def __init__(self, riddle: dict):
        '''Init `Riddle` object from basic riddle info.'''
        self.alias = riddle['alias']
        self.full_name = riddle['full_name']
        if riddle['guild_id']:
            self.guild = get(bot.guilds, id=int(riddle['guild_id']))
    
    async def build_levels(self):
        '''Populate object with levels and secret levels data.'''
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle
        '''
        result = await database.fetch_all(query, {'riddle': self.alias})
        self.levels, self.secret_levels = map( 
            lambda levels: {level['name']: level for level in levels},
            partition(lambda level: not level['is_secret'], result),
        )


# Global dict of (alias -> `Riddle`)
riddles: dict[str, Riddle] = {}


async def create_and_add_riddle(riddle_data: dict):
    '''Create and add new `Riddle` entry to riddles dict.'''
    riddle = Riddle(riddle_data)
    await riddle.build_levels()
    riddles[riddle.alias] = riddle
