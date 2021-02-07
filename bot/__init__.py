import os
import sys
import logging
from dotenv import load_dotenv

# Allow util folder to be visible
sys.path.append('..')

import discord
from discord.utils import get

from bot import bot
from util.db import database
from riddle import Riddle, riddles
import begin
import unlock
import update
import send

# Get Discord token securely from environment variable
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Allow logging info
logging.basicConfig(level=logging.INFO)


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''
    print('> Bot up and running!')

    # Build riddles dict from database guild and level data
    await database.connect()
    query = 'SELECT * from riddles'
    result = await database.fetch_all(query)
    for riddle in result:
        query = 'SELECT * FROM levels WHERE riddle = :riddle'
        values = {'riddle': riddle['alias']}
        levels = await database.fetch_all(query, values)
        # query = 'SELECT * FROM secret_levels WHERE guild = :guild'
        # secret_levels = await database.fetch_all(query, values)
        riddles[riddle['alias']] = Riddle(riddle, levels)


@bot.command()
async def ping(ctx):
    # Ping-pong
    await ctx.send('pong')


@bot.command()
async def balthify(ctx):
    text = ctx.message.content.split()
    if len(text) == 1:
        # Command usage
        text = '> `!balthify` - Turn text into Balthazar-speak\n' \
                '> • Usage: `!balthify <text>`'
    else:
        # Transform text into uppercase, remove spaces
        # and punctuation and keep numbers
        text = list(''.join(text[1:]))
        for i in range((len(text))):
            if text[i].isalpha():
                text[i] = text[i].upper()
            elif not text[i].isdigit():
                text[i] = ''
        text = ''.join(text)

    # Send message
    if text:
        if not ctx.guild:
            await ctx.author.send(text)
        else:
            await ctx.channel.send(text)


bot.run(token)
