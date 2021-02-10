from collections import OrderedDict

import discord
from discord.utils import get

from bot import bot


class Riddle:
    '''Container for guild's riddle levels and info.'''

    # Discord guild object
    guild: discord.Guild

    # Ordered dict of pairs (level_id -> path)
    levels = OrderedDict()
    secret_levels = OrderedDict()

    # Suffix to be appended to winners' nicknames
    winner_suffix: str

    def __init__(self, riddle: dict, levels: dict):
        '''Build riddle object by row extracted from database.'''
        # Get info from guild's database data
        self.guild = get(bot.guilds, name=riddle['full_name'])
        self.winner_suffix = riddle['winner_suffix']

        # Get riddle's level info from database query
        for level in levels:
            id = level['name']
            self.levels[id] = level
        # for level in secret_levels:
        #     id = level['level_id']
        #     self.secret_levels[id] = level


# Global dict of (guild_alias -> riddle) which bot supervises
riddles = {}
