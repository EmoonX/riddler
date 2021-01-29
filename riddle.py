from collections import OrderedDict
from typing import Dict

from discord import Guild

from bot import bot
from util.db import database


class Riddle:
    '''Container for guild's riddle levels and info.'''

    # Discord guild object
    guild: Guild

    # Ordered dicts of pairs (level_id -> filename)
    levels: OrderedDict
    secret_levels: OrderedDict

    # Ordered dict of pairs (secret_level -> answer)
    secret_answers: OrderedDict

    def __init__(self, guild: dict, levels: dict):
        '''Build riddle object by row extracted from database.'''
        # Get riddle's guild
        self.guild = bot.get_guild(guild['id'])

        # Get riddle's levels from database query
        self.levels = \
                {level['level_id']: level['filename'] for level in levels}


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: Dict[str, Riddle] = {}
