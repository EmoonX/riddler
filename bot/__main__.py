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
    from util.db import database
    # guild = get(bot.guilds, name='Genius Riddle')
    # role = get(guild.roles, name='Spring Florists')
    # for channel in guild.channels:
    #     if 'spring' in channel.name:
    #         await channel.set_permissions(role, read_messages=True)


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
