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
from unlock import update_nickname
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
    query = 'SELECT * from guilds'
    guilds = await database.fetch_all(query)
    for guild in guilds:
        query = 'SELECT * FROM levels WHERE guild = :guild'
        values = {'guild': guild['alias']}
        levels = await database.fetch_all(query, values)
        riddle = Riddle(guild, levels)
        riddles[guild['alias']] = riddle
    
    # Grant initial attributes to those without nicknames
    for riddle in riddles.values():
        for member in riddle.guild.members:
            if not member.nick:
                await init_member(member, riddle)


@bot.event
async def on_member_join(member: discord.Member):
    '''Initialize member features upon join.'''
    guild = member.guild
    riddle = get(riddles.values(), guild=guild)
    await init_member(member, riddle)


async def init_member(member: discord.Member, riddle: Riddle):
    '''Grant first level role and nickname to member.'''
    # Ignore bots and admins
    if member.bot or member.guild_permissions.administrator:
        return
    
    # Find first level ID from riddle's level list
    id = next(iter(riddle.levels))
    
    # Process changes to member
    name = 'reached-%s' % id
    role = get(riddle.guild.roles, name=name)
    await member.add_roles(role)
    await update_nickname(member, '[%s]' % id)


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
