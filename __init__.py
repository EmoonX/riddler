import io
import os
import re
import math
import asyncio
import logging
from dotenv import load_dotenv

import discord
from discord.utils import get
from discord.ext import commands

from bot import bot, levels, secret_levels, secret_answers
import begin
import update
import send
import decipher

# Get Discord token securely from environment variable
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Allow logging info
logging.basicConfig(level=logging.INFO)

# List of normal level/channels ids (in order!)
level_order = []


# --------------------------------------------------------------------------- #


@bot.event
async def on_ready():
    print('> Bot up and running!')

    # Build dicts of levels and secret levels from attached file
    category = None
    secret = False
    guild = bot.guilds[0]
    with open('levels.txt', 'r') as file:
        for line in file:
            aux = line.split()
            if not aux:
                continue
            if aux[0] in ('C', 'S'):
                # Get category for the following levels
                name = ' '.join(aux[1:])
                category = get(guild.categories, name=name)
                if aux[0] == 'S':
                    secret = True
            else:
                id, filename = aux[:2]
                level_order.append(id)
                if not secret:
                    levels[id] = filename
                else:
                    secret_levels[id] = filename
                    answer = aux[2]
                    secret_answers[id] = answer

    # # Default all those without nicknames to [01]
    # role = get(guild.roles, name='reached-01')
    # for member in guild.members:
    #     if member.bot:
    #         await member.edit(nick=None)
    #     elif not member.nick:
    #         await update_nickname(member, '[01]')
    #         await member.add_roles(role)


@bot.event
async def on_member_join(member):
    # Add "[01]" immediatelly on member join
    guild = bot.guilds[0]
    if not member.bot:
        role = get(guild.roles, name='reached-01')
        await update_nickname(member, '[01]')
        await member.add_roles(role)


@bot.command()
async def ping(ctx):
    # Ping-pong
    await ctx.send('pong')


# --------------------------------------------------------------------------- #


@bot.command()
async def build(ctx):
    if ctx.message.guild:
        # Avoid sending file to public channel
        await ctx.message.delete()
        return

    author = ctx.message.author
    guild = bot.guilds[0]
    member = get(guild.members, name=author.name)
    if not member or not member.guild_permissions.administrator:
        # You are not an admin of given guild
        text = '> `!build` - Access denied'
        await author.send(text)
        return

    aux = ctx.message.content.split(maxsplit=1)
    if len(aux) < 2 or aux[1] != 'yes':
        # Command usage info
        text = '> `!build` - Create channels and roles based on .txt file\n' \
                '> Send `!build yes` if you\'re _really_ sure about it'
        await author.send(text)
        return

    text = '> `!build` - Started building level channels and roles...'
    await author.send(text)

    # Loop between each level
    channels = []
    for id in {**levels, **secret_levels}:
        text = '> Processing ID ' + id
        await author.send(text)

        # Create channel which defaults to no read permission
        channel = get(guild.channels, name=id)
        if not channel:
            category = get(guild.categories, name=name)
            if not category:
                # Create category if nonexistent
                category = await guild.create_category(name=name)
            channel = await category.create_text_channel(id)
        if channel:
            overwrite = discord.PermissionOverwrite(read_messages=False)
            overwrites = { guild.default_role: overwrite }
            await channel.edit(overwrites=overwrites)
            channels.append(channel)

        # Create level user role
        name = 'reached-' + id
        if id == 'winners':
            name = 'winners'
        role = get(guild.roles, name=name)
        if not role:
            color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
            role = await guild.create_role(name=name, color=color)

        # Create secret "solved" role, if applicable
        role2 = None
        if id in secret_levels:
            name = 'solved-' + id
            role2 = get(guild.roles, name=name)
            if not role2:
                role2 = await guild.create_role(name=name)

        # Set read permission to current roles
        # for this channel and every other before it (except secret levels)
        if id not in secret_levels:
            for channel in channels:
                await channel.set_permissions(role, read_messages=True)
        else:
            channel = get(guild.channels, name=id)
            await channel.set_permissions(role, read_messages=True)
            if role2:
                await channel.set_permissions(role2, read_messages=True)

    text = '> Channel and roles building complete :)'
    await author.send(text)


# --------------------------------------------------------------------------- #


@bot.command()
async def add(ctx):
    if ctx.message.guild:
        # Avoid sending query to public channel
        await ctx.message.delete()
        return

    author = ctx.message.author
    guild = bot.guilds[0]
    member = get(guild.members, name=author.name)
    if not member or not member.guild_permissions.administrator:
        # You are not an admin of given guild
        text = '> `!add` - Access denied'
        await author.send(text)
        return

    aux = ctx.message.content.split("\n")
    if len(aux) != 3 or len(aux[1].split()) < 2 \
            or aux[1][0] not in ('C', 'S') or len(aux[2].split()) != 3:
        # Command usage info
        text = '> `!add` - Add level channel and role to server\n' \
                '> \n' \
                '> • Usage (normal levels):\n' \
                '> `!add\n' \
                '> <type> <category>\n' \
                '> <level_id> <filename> <answer>`\n' \
                '> \n' \
                '> • `type`: C if normal level, S in case of secret one\n' \
                '> `category`: name of the category\n' \
                '> `level_id`: an identifier representing current level\n' \
                '> `filename`: the last part of the URL of the level' \
                    ' frontpage, minus extensions (like .htm) or slashes' \
                    ' (exception goes for the #winners channel, which needs' \
                    ' instead the final level\'s answer as the word)\n' \
                '> `answer`: the level\'s answer\n' \
                '> \n' \
                '> • Please note that the command consists of three lines'
        await author.send(text)
        return

    # Get info from message
    type, cat_name = aux[1].split(maxsplit=1)
    id, filename, answer = aux[2].split()
    channel = get(guild.channels, name=id)

    if channel:
        text = '> Channel **#' + id + '** already exists!'
        await author.send(text)
        return

    # Create channel which defaults to no read permission
    category = get(guild.categories, name=cat_name)
    if not category:
        # Create category if nonexistent
        category = await guild.create_category(name=cat_name)
    channel = await category.create_text_channel(id)
    overwrite = discord.PermissionOverwrite(read_messages=False)
    overwrites = { guild.default_role: overwrite }
    await channel.edit(overwrites=overwrites)

    # Create level user role
    name = 'reached-' + id
    color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
    role = await guild.create_role(name=name, color=color)

    # Add level list and dict(s)
    if type == 'C':
        levels[id] = filename

        # Set read permission to current roles
        # for this channel and every other before it (except secret levels)
        last = ''
        await channel.set_permissions(role, read_messages=True)
        for i in range(len(level_order)):
            other = level_order[i]
            if other == 'winners':
                # Insert ID just before winners in list
                level_order.insert(i, id)
                break
            last = other
            channel = get(guild.channels, name=other)
            await channel.set_permissions(role, read_messages=True)

        # Set also read permission to "winner" role
        role = get(guild.roles, name='winners')
        channel = get(guild.channels, name=id)
        await channel.set_permissions(role, read_messages=True)

        # Swap "winners" role for "reached" one on all electable members
        for member in guild.members:
            role = get(member.roles, name='winners')
            if role:
                await member.remove_roles(role)
                role2 = get(guild.roles, name=('reached-' + id))
                await member.add_roles(role2)

        # "winners" channel !unlock answer is now the added level's answer
        levels['winners'] = answer

    else:
        secret_levels[id] = filename
        secret_answers[id] = answer

        # Create secret "solved" role
        name = 'solved-' + id
        color = discord.Color.from_rgb(0x1a, 0xd6, 0xd0)
        role2 = await guild.create_role(name=name, color=color)

        # Add "reached" and "solved" read permissions
        channel = get(guild.channels, name=id)
        await channel.set_permissions(role, read_messages=True)
        if role2:
            await channel.set_permissions(role2, read_messages=True)

        # Add sercret to the end of list
        level_order.append(id)

    rebuild_file()

    text = '> Level channel **#' + id + '** and roles building complete :)'
    await author.send(text)


@bot.command()
async def rename(ctx):
    if ctx.message.guild:
        # Avoid sending query to public channel
        await ctx.message.delete()
        return

    author = ctx.message.author
    guild = bot.guilds[0]
    member = get(guild.members, name=author.name)
    if not member or not member.guild_permissions.administrator:
        # You are not an admin of given guild
        text = '> `!rename` - Access denied'
        await author.send(text)
        return

    aux = ctx.message.content.split()
    if len(aux) < 3:
        # Command usage info
        text = '> `!rename` - Batch rename channels, roles and nicknames\n' \
                '> \n' \
                '> • Usage: `!rename <pattern> <replacement> [yes]`\n' \
                '> \n' \
                '> • `pattern`: Regular expression matching desired names\n' \
                '> `replacement`: Pattern that should result from renaming\n' \
                '> Put `yes` afterwards if you are really sure about it! \n'
        await author.send(text)
        return

    # Get pattern and replacement from message
    pattern, replacement = aux[1], aux[2]
    yes = (len(aux) == 4 and aux[3] == 'yes')

    # Dict of {cur_names -> new_names}
    changes = {}

    # Change channels and roles name
    ok = False
    for channel in guild.channels:
        # Do regex matching and substitution
        cur_name = channel.name
        if not re.match(pattern, cur_name):
            continue
        new_name = re.sub(pattern, replacement, cur_name)
        if new_name == cur_name:
            continue
        ok = True
        changes[cur_name] = new_name

        # Send confirmation
        s = 'will be replaced' if not yes else 'being replaced'
        text = '> ID **' + cur_name \
                + '** ' + s + ' with **' + new_name + '**...'
        await author.send(text)
        if not yes:
            continue

        # Edit channel and role names
        await channel.edit(name=new_name)
        role = get(guild.roles, name=('reached-' + cur_name))
        if role:
            await role.edit(name=('reached-' + new_name))
        if cur_name in levels:
            # Update levels dict
            filename = levels[cur_name]
            levels.pop(cur_name)
            levels[new_name] = filename
        elif cur_name in secret_levels:
            # Update "solved" roles too
            role = get(guild.roles, name=('solved-' + cur_name))
            await role.edit(name=('solved-' + new_name))

            # Update secret_levels dict
            filename = secret_levels[cur_name]
            secret_levels.pop(cur_name)
            secret_levels[new_name] = filename

        # Update level_order list
        level_order[level_order.index(cur_name)] = new_name

    if ok and yes:
        rebuild_file()

        # Update eligible nicknames
        for member in guild.members:
            if member.nick:
                aux = re.search(r'\[.*\]', member.nick)
                if not aux:
                    continue
                name = aux[0][1:-1]
                if name and name in changes:
                    await update_nickname(member, '[' + changes[name] + ']')

    if not ok:
        text = '> No channels found :('
    elif not yes:
        text = '> Send same !rename command with **yes** for confirming it'
    else:
        text = '> Channel, roles and nicknames renaming completed :)'
    await author.send(text)


# --------------------------------------------------------------------------- #


@bot.command()
async def info(ctx):
    # Build dict of (certified riddlers -> max level)
    # (where "certified" means having unlocked at least one channel)
    riddlers = {}
    guild = bot.guilds[0]
    for member in guild.members:
        if 'Creator' in member.roles:
            continue
        for role in member.roles:
            if ('reached-' in role.name and role.name != 'reached-01') \
                    or role.name == 'winners':
                id = role.name.strip('reached-')
                riddlers[member.name] = id
                break

    # Info about total number of riddlers
    text = '> `!info`: show general riddlers\' info\n' \
            '> \n' \
            '> • There is a total of **' + str(len(riddlers)) \
            + '** certified riddlers on the _' + guild.name + '_ server\n' \
            '> \n' \
            '> • Distribution of members\' highest reached milestones:\n'

    # Count how many riddlers have reached certain milestones
    milestone_count = \
            { '02': 0, '11': 0, '21': 0, \
                '31': 0, '41': 0, '51': 0, '61': 0, 'winners': 0}
    max_count = 0
    for riddler in riddlers:
        member = get(guild.members, name=riddler)
        for role in member.roles:
            if role.name == 'winners':
                milestone_count['winners'] += 1
                break
            elif 'reached-' in role.name:
                cur_id = role.name.strip('reached-')
                if cur_id in secret_levels:
                    continue
                max_id = ''
                if cur_id in levels:
                    for id in level_order:
                        if id in milestone_count:
                            max_id = id
                        if id == cur_id:
                            break
                if max_id:
                    milestone_count[max_id] += 1
                    max_count = max(max_count, milestone_count[max_id])
                    break

    # Show milestones percentage of reaching, including the cool row bars
    size = max(size for size in map(len, milestone_count.keys()))
    format_id = '> ` %%%ds ' % size
    for id in milestone_count.keys():
        ratio_rel = milestone_count[id] / max_count
        ratio_abs = milestone_count[id] / len(riddlers)
        s = ''
        if id != 'winners':
            s = format_id % (id + '+')
        else:
            s = format_id % 'winners'
        count = round(20 * ratio_rel)
        if count == 0 and ratio_rel > 0:
            count = 1
        s += '[' + ''.join('█' for k in range(count))
        s += ''.join(' ' for k in range(20 - count)) + ']'
        s += ' %2d (%4.1f%%)`\n' % (milestone_count[id], 100 * ratio_abs)
        text += s

    # Finally, send the message
    if ctx.message.guild:
        await ctx.message.channel.send(text)
    else:
        await ctx.message.author.send(text)


@bot.command()
async def secret(ctx):
    # Only allow unlocking by PM to bot
    message = ctx.message
    if message.guild and not message.author.administrator:
        # Purge all traces of wrong message >:)
        author = message.author
        await message.delete()
        text = '> `!secret` must be sent by PM to me!'
        await author.send(text)
        return

    aux = message.content.split(maxsplit=2)[1:]
    text = ''

    if len(aux) != 2:
        # Command usage
        text = '> `!secret`: proof of secret level completion (PM ONLY!)\n' \
                '> \n' \
                '> • Usage: `!secret <level_id> <answer>`\n' \
                '> `level_id`: an identifier representing the secret level\n' \
                '> `answer`: the answer itself\n' \
                '> \n' \
                '> • Secret level IDs: **' \
                    + ' '.join(id for id in secret_levels.keys()) \
                    + '**\n'
        await message.author.send(text)
        return

    # Get level ID and filename
    id, answer = aux

    # Get guild member object from message author
    guild = bot.guilds[0]
    member = get(guild.members, name=message.author.name)

    if not id in secret_levels:
        # User entered a wrong level ID
        text = '> Secret level ID **' + id + '** not found!\n' \
                '> Try `!secret help` for command usage'
    else:
        name = 'solved-' + id
        role = get(member.roles, name=name)
        if role:
            # User already completed that elvel
            text = '> Secret level **' + id + '** has already been beaten!\n' \
            '> Try `!secret help` for command usage'

        elif id in secret_levels and secret_answers[id] != answer:
            # User entered a wrong answer
            text = '> Wrong answer for ID **' + id + '**!\n' \
            '> Try `!secret help` for command usage'

    if text:
        # In case of anything wrong, just show message and return
        await message.author.send(text)
        return

    # Remove old "reached" role from user
    name = 'reached-' + id
    role = get(guild.roles, name=name)
    await member.remove_roles(role)

    # Add "solved" role to member
    name = 'solved-' + id
    role = get(guild.roles, name=name)
    await member.add_roles(role)

    # Send confirmation message
    print('Member ' + member.name +  ' completed secret level '  + id)
    text = '> You successfuly completed secret level **' + id + '**!'
    await message.author.send(text)

    # Send congratulations message to channel :)
    channel = get(guild.channels, name=id)
    first_to_solve = (len(role.members) == 1)
    text = ''
    if first_to_solve:
        text = '> **🏅 FIRST TO SOLVE 🏅**\n'
    text += '> **<@!%d> has completed secret level _%s_. Congratulations!**' \
            % (member.id, id)
    await channel.send(text)
    if first_to_solve:
        channel = get(guild.channels, name='achievements')
        await channel.send(text)


# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #


async def update_nickname(member: discord.Member, s: str):
    # Update user's nickname to reflect current level
    # In case of it exceding 32 characters, shorten the member name to fit
    name = member.name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:-(excess + 5)] + '(...)'
    nick = name + ' ' + s
    await member.edit(nick=nick)


def rebuild_file():
    # Rebuild levels.txt file
    cat_name = ''
    guild = bot.guilds[0]
    with open('levels.txt', 'w') as file:
        for level in level_order:
            channel = get(guild.channels, name=level)
            if channel.category.name != cat_name:
                if cat_name:
                    file.write('\n')
                cat_name = channel.category.name
                type = 'C' if level in levels else 'S'
                file.write(type + ' ' + cat_name + '\n')
            if level in levels:
                file.write(level + ' ' + levels[level] + '\n')
            else:
                file.write(level + ' ' + secret_levels[level] + ' '
                        + secret_answers[level] + '\n')


# --------------------------------------------------------------------------- #


bot.run(token)
