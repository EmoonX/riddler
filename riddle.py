from typing import Dict

from util.db import database


class Riddle:
    '''Container for guild's riddle levels and info.'''

    # Application-exclusive guild alias
    guild_alias: str

    # ID of riddle's guild (thus bot can find it)
    guild_id: int

    # Dicts of pairs (level_id -> filename)
    levels = {}
    secret_levels = {}

    # Dict of pairs (secret_level -> answer)
    secret_answers = {}

    def __init__(self, guild: dict, levels: dict):
        '''Build riddle object by row extracted from database.'''

        # Basic guild info
        self.guild_alias = guild['alias']
        self.guild_id = guild['id']

        # Fetch riddle's levels from database
        self.levels = \
                {level['level_id']: level['filename'] for level in levels}


# Global dict of (guild_alias -> riddle) which bot supervises
riddles: Dict[str, Riddle] = {}
