import os
import sys
import asyncio
import logging

from dotenv import load_dotenv

# Allow util folder to be visible
sys.path.append('..')

from bot import Bot

# Load environment variables from .env file
load_dotenv(verbose=True)

# Get Discord token securely from environment variable
token = os.getenv('DISCORD_TOKEN')

# Allow logging info
logging.basicConfig(level=logging.INFO)


async def main():
    '''Create/start bot.'''
    bot = Bot()
    await bot.start(token)


if __name__ == '__main__':
    asyncio.run(main())
