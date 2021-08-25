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

    from discord.utils import get
    # try:
    #     for guild in bot.guilds:
    #         member = guild.get_member(491949328202465282)
    #         if not member or not member.nick:
    #             continue
    #         old_nick = member.nick
    #         idx = old_nick.rfind('[')
    #         progress_string = old_nick[idx:]
    #         try:
    #             await update_nickname(member, progress_string)
    #             logging.info('[%s] Nickname "%s" changed to "%s"'
    #                     % (guild.name, old_nick, member.nick))
    #         except:
    #             logging.info('[%s] (403) Can\'t change nick of "%s"'
    #                     % (guild.name, member.name))
    # except:
    #     import traceback
    #     tb = traceback.format_exc()
    #     logging.error(tb)   

    # from util.db import database
    # guild = get(bot.guilds, name='Genius Riddle')
    # for member in guild.members:
    #     if False:
    #         continue
    #     try:
    #         logging.info(member.name)
    #         query = 'DROP TABLE IF EXISTS lv; ' \
    #                 'CREATE TEMPORARY TABLE IF NOT EXISTS lv AS ( ' \
    #                     'SELECT lv.* FROM user_levels AS ulv ' \
    #                     'INNER JOIN levels AS lv ' \
    #                         'ON ulv.riddle = lv.riddle ' \
    #                             'AND ulv.level_name = lv.`name` ' \
    #                     'WHERE lv.riddle = :riddle ' \
    #                         'AND ulv.username = :username ' \
    #                 ')'
    #         values = {'riddle': 'genius',
    #                 'username': member.name}
    #         await database.execute(query, values)

    #         # Get list of farthest reached unlocked levels
    #         query = 'SELECT l1.* FROM lv AS l1 ' \
    #                 'LEFT JOIN lv AS l2 ' \
    #                     'ON l1.riddle = l2.riddle ' \
    #                         'AND l1.level_set = l2.level_set ' \
    #                         'AND l1.`index` < l2.`index` ' \
    #                 'WHERE l2.`index` IS NULL'
    #         current_levels = await database.fetch_all(query)
            
    #         # Get dict of level sets' emoji
    #         query = 'SELECT * FROM level_sets ' \
    #                 'WHERE riddle = :riddle '
    #         values = {'riddle': 'genius'}
    #         result = await database.fetch_all(query, values)
    #         level_sets = {
    #             row['set_name']: row for row in result
    #         }
    #         # Replace explicit set name in level
    #         # names with short emoji form
    #         level_names = {}
    #         for level in current_levels:
    #             set_name = level['level_set']
    #             if not set_name in level_sets:
    #                 continue
    #             level_set = level_sets[set_name]
    #             query = 'SELECT l1.* FROM levels AS l1 ' \
    #                     'LEFT JOIN levels as l2 ' \
	#                         'ON l1.level_set = l2.level_set ' \
	# 	                        'AND l1.`index` < l2.`index` ' \
    #                     'WHERE l1.level_set = :set_name ' \
    #                         'AND l1.name IN ( ' \
    #                             'SELECT level_name AS name FROM user_levels ' \
    #                             'WHERE riddle = :riddle ' \
    #                                 'AND username = :name ' \
    #                                 'AND discriminator = :disc ' \
    #                                 'AND completion_time IS NOT NULL ' \
	#                         ') ' \
	#                     'AND l2.`index` IS NULL'
    #             values = {'riddle': 'genius', 'set_name': set_name,
    #                     'name': member.name, 'disc': member.discriminator}
    #             set_completed = await database.fetch_one(query, values)
    #             if not set_completed:
    #                 short_name = level_set['short_name']
    #                 name = level['name'].replace((set_name + ' '), short_name)
    #                 for digit in '0123456789':
    #                     # Replace numerical digits by their
    #                     # smaller Unicode variants
    #                     if digit in name:
    #                         value = ord(digit) - 0x30 + 0x2080
    #                         small_digit = chr(value)
    #                         name = name.replace(digit, small_digit)
    #             else:
    #                 name = level_set['emoji']
                
    #             index = level_set['index']
    #             level_names[index] = name
    #         aux = sorted(level_names.items())
    #         level_names = [level for _, level in aux]
    #         if not level_names:
    #             await member.edit(nick=None)
    #             continue
    #         s = '[' + ' '.join(level_names) + ']'

    #         # Show current level(s) in nickname
    #         from commands.unlock import update_nickname
    #         await update_nickname(member, s)
    #     except:
    #         import traceback
    #         tb = traceback.format_exc()
    #         logging.error(tb)


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
