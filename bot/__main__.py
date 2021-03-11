import os
import sys
import logging

from discord.utils import get
from dotenv import load_dotenv
from cogwatch import Watcher

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import bot
from riddle import build_riddles, riddles


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''

    print('> Bot up and running!')
    
    # Start cogwatch on commands folder
    watcher = Watcher(bot, path='commands', preload=True)
    await watcher.start()
    
    # Build riddles dict
    await build_riddles()
    
    # guild = get(bot.guilds, name='Cipher: Crack the Code')
    # riddler = get(guild.roles, name='Riddler')
    # for channel in guild.channels:
    #     await channel.set_permissions(riddler, read_messages=True)

if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
