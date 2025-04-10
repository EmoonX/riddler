import glob
import logging
import os
import sys

import discord
import discord.state
from dotenv import load_dotenv

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import bot
from riddle import create_and_add_riddle
from util.db import database


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''

    logging.info('> Bot up and running!')
    
    def _get_activity():
        '''Get optional custom status message from env variable.'''
        if custom_status := os.getenv('DISCORD_CUSTOM_STATUS'):
            return discord.Activity(
                type=discord.ActivityType.custom,
                name='Custom Status',
                state=custom_status,
            )
        return None
    
    await bot.change_presence(
        status=discord.Status.online,
        activity=_get_activity()
    )

    # Establish database connection and build riddles dict
    await database.connect()
    query = '''SELECT * FROM riddles''' 
    result = await database.fetch_all(query)
    for row in result:
        await create_and_add_riddle(row)
    
    # Iterate through command modules and autoload extensions
    commands_dir = os.getcwd() + '/commands'
    os.chdir(commands_dir)
    for path in glob.glob('**/*.py', recursive=True):
        if path.endswith('.py'):
            name = path.removesuffix('.py').replace('/', '.')
            name = f"commands.{name}"
            logging.info('Loading extension %s…', name)
            await bot.load_extension(name)

    logging.info('> All clear.')


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
