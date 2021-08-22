import os
import sys
import logging

from dotenv import load_dotenv
from cogwatch import Watcher

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import bot
from riddle import build_riddles


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''

    logging.info('> Bot up and running!')
    
    # Start cogwatch on commands folder
    watcher = Watcher(bot, path='commands', preload=True)
    await watcher.start()

    # Build riddles dict
    await build_riddles()

    # Create a temporary reusable table for easing queries
    from util.db import database
    from discord.utils import get
    guild = get(bot.guilds, name='Genius Riddle')
    for member in guild.members:
        try:
            logging.info(member.name)
            query = 'DROP TABLE IF EXISTS lv; ' \
                    'CREATE TEMPORARY TABLE IF NOT EXISTS lv AS ( ' \
                        'SELECT lv.* FROM user_levels AS ulv ' \
                        'INNER JOIN levels AS lv ' \
                            'ON ulv.riddle = lv.riddle ' \
                                'AND ulv.level_name = lv.`name` ' \
                        'WHERE lv.riddle = :riddle ' \
                            'AND ulv.username = :username ' \
                    ')'
            values = {'riddle': 'genius',
                    'username': member.name}
            await database.execute(query, values)

            # Get list of farthest reached unlocked levels
            query = 'SELECT l1.* FROM lv AS l1 ' \
                    'LEFT JOIN lv AS l2 ' \
                        'ON l1.riddle = l2.riddle ' \
                            'AND l1.level_set = l2.level_set ' \
                            'AND l1.`index` < l2.`index` ' \
                    'WHERE l2.`index` IS NULL'
            current_levels = await database.fetch_all(query)
            
            # Get dict of level sets' emoji
            query = 'SELECT * FROM level_set_emoji ' \
                    'WHERE riddle = :riddle '
            values = {'riddle': 'genius'}
            result = await database.fetch_all(query, values)
            level_set_emoji = {
                row['level_set']: row for row in result
            }
            # Replace explicit set name in level
            # names with short emoji form
            level_names = {}
            for level in current_levels:
                set_name = level['level_set']
                if 'Bonus' in set_name:
                    continue
                level_set = level_set_emoji[set_name]
                emoji = level_set['emoji']
                name = level['name'].replace((set_name + ' '), emoji)
                for digit in '0123456789':
                    if digit in name:
                        value = ord(digit) - 0x30 + 0x2080
                        small_digit = chr(value)
                        name = name.replace(digit, small_digit)
                index = level_set['index']
                level_names[index] = name
            aux = sorted(level_names.items())
            level_names = [level for _, level in aux]
            if not level_names:
                continue
            s = '[' + ' '.join(level_names) + ']'

            # Show current level(s) in nickname
            from commands.unlock import update_nickname
            await update_nickname(member, s)
        except:
            pass


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
