from typing import OrderedDict, DefaultDict

import discord
from discord.utils import get

from bot import bot
from util.db import database


class Riddle:
    '''Container for guild's riddle levels and info.'''

    full_name: str
    '''Riddle's full name.'''

    guild: discord.Guild
    '''Discord guild object.'''

    levels: OrderedDict[str, dict]
    '''Ordered dict of (normal) levels.'''

    secret_levels: OrderedDict[str, dict]
    '''Ordered dict of secret levels.'''

    def __init__(self, riddle: dict, levels: dict, secret_levels: dict):
        '''Build riddle object by row extracted from database.'''

        # Get info from guild's database data
        self.full_name = riddle['full_name']
        self.guild = get(bot.guilds, id=int(riddle['guild_id']))

        # Get riddle's level info from database query
        self.levels = OrderedDict()
        for level in levels:
            id = level['name']
            self.levels[id] = level
        self.secret_levels = OrderedDict()
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
            WHERE riddle = :riddle AND is_secret IS FALSE
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


async def get_ancestor_levels(riddle: str, root_level: dict):
    '''Build set of ancestor levels (just Discord names)
    by applying a reverse BFS in requirements DAG.'''

    ancestor_levels = set()
    queue = [root_level]
    while queue:
        # Add level to set
        level = queue.pop(0)
        ancestor_levels.add(level['discord_name'])

        # Don't search node's children if level is final in set
        # (except if this is the root level itself, of course)
        query = '''
            SELECT * FROM level_sets
            WHERE riddle = :riddle AND final_level = :level_name
        '''
        values = {'riddle': riddle, 'level_name': level['name']}
        is_final_in_set = await database.fetch_one(query, values)
        if is_final_in_set and len(ancestor_levels) > 1:
            continue

        # Fetch level requirements and add unseen ones to queue
        query = '''
            SELECT * FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        result = await database.fetch_all(query, values)
        for row in result:
            query = '''
                SELECT * FROM levels
                WHERE riddle = :riddle and name = :level_name
            '''
            values['level_name'] = row['requires']
            level = await database.fetch_one(query, values)
            if level['discord_name'] not in ancestor_levels:
                queue.append(dict(level))

    return ancestor_levels
