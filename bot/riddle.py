from typing import Dict, OrderedDict

import discord

from bot import bot


class Riddle:
    '''Container for guild's riddle levels and info.'''

    # Discord guild object
    guild: discord.Guild

    # Lists of level IDs
    levels = []
    secret_levels = []

    # Suffix to be appended to winners' nicknames
    winner_suffix: str

    def __init__(self, guild: dict, levels: dict):
        '''Build riddle object by row extracted from database.'''
        # Get info from guild's database data
        self.guild = bot.get_guild(guild['id'])
        self.final_answer_hash = guild['final_answer_hash'].encode('utf-8')
        self.winner_suffix = guild['winner_suffix']

        # Get riddle's level info from database query
        for level in levels:
            id = level['level_id']
            filename_hash = level['filename_hash'].encode('utf-8')
            self.levels[id] = filename_hash


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: Dict[str, Riddle] = {}
