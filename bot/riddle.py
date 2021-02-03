from typing import Dict, OrderedDict

import discord

from bot import bot


class Riddle:
    '''Container for guild's riddle levels and info.'''

    # Discord guild object
    guild: discord.Guild

    # Ordered dict of pairs (level_id -> path)
    levels: OrderedDict[str, dict] = {}
    secret_levels: OrderedDict[str, dict] = {}

    # Suffix to be appended to winners' nicknames
    winner_suffix: str

    def __init__(self, guild: dict, levels: dict, secret_levels: dict):
        '''Build riddle object by row extracted from database.'''
        # Get info from guild's database data
        self.guild = bot.get_guild(guild['id'])
        self.final_answer_hash = guild['final_answer_hash'].encode('utf-8')
        self.winner_suffix = guild['winner_suffix']

        # Get riddle's level info from database query
        for level in levels:
            id = level['level_id']
            self.levels[id] = level['path']
        for level in secret_levels:
            id = level['level_id']
            self.secret_levels[id] = level


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: Dict[str, Riddle] = {}
