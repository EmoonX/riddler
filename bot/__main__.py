import os
import sys
import pkgutil
import logging
from importlib.util import module_from_spec

from dotenv import load_dotenv
from cogwatch import Watcher

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import bot
from commands.riddle import build_riddles


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''

    print('> Bot up and running!')
    
    # Start cogwatch on commands folder
    watcher = Watcher(bot, path='commands', preload=True)
    await watcher.start()
    
    # Build riddles dict
    await build_riddles()
    
    # guild = get(bot.guilds, name='RNS Riddle II')
    # for role in guild.roles:
    #     if 'reached-' in role.name:
    #         name = role.name[8:]
    #         channel = get(guild.channels, name=name)
    #         await channel.delete()
    #         await role.delete()
        

if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
