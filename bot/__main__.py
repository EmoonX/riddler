import os
import sys
import logging

from dotenv import load_dotenv

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

    # Build riddles dict
    await build_riddles()

    from discord.utils import get
    from util.db import database


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
