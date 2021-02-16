import os
import sys
import asyncio
import logging

from dotenv import load_dotenv

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import Bot, bot
import commands.riddle


if __name__ == '__main__':
    # Create bot and start asyncio main loop
    bot = Bot()
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
