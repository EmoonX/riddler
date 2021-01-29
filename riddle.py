# Global dict of (aliases -> riddles) which bot supervises
riddles = []

class Riddle:
    '''Container for guild's riddle levels and info.'''

    # ID of riddle's guild (so bot can find it)
    guild_id: int

    # Dicts of pairs (level_id -> filename)
    levels = {}
    secret_levels = {}

    # Dict of pairs (secret_level -> answer)
    secret_answers = {}

    def __init__(self, guild_alias: str):
        '''Build riddle object using info extracted from database.'''
