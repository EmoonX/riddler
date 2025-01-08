import json
import logging
import traceback

from aiohttp import web
import discord
from discord.utils import get
from discord.errors import Forbidden

from bot import bot
from riddle import riddles
from commands.unlock import multi_update_nickname
from util.db import database
from util.riddle import get_ancestor_levels


async def insert(request):
    '''Build guild channels and roles from level data.'''

    # Get riddle and guild info from DB
    data = request.rel_url.query
    alias = data['alias']
    query = '''
        SELECT * FROM riddles
        WHERE alias = :alias
    '''
    values = {'alias': alias}
    result = await database.fetch_one(query, values)

    # Get guild and riddle objects,
    # and likewise completed and mastered roles
    guild = get(bot.guilds, id=result['guild_id'])
    riddle = get(riddles.values(), guild=guild)
    completed_role = get(guild.roles, name=result['completed_role'])
    mastered_role = get(guild.roles, name=result['mastered_role'])

    # Build dict of set completion r0les
    query = '''
        SELECT * FROM level_sets
        WHERE riddle = :alias
    '''
    result = await database.fetch_all(query, values)
    set_completion_roles = {}
    for row in result:
        role_name = row['completion_role']
        completion_role = get(guild.roles, name=role_name)
        set_completion_roles[row['name']] = completion_role

    async def clear_mastered():
        '''Remove mastered roles and 💎 in nick from respective members.'''
        for member in guild.members:
            if not mastered_role in member.roles:
                continue
            await member.remove_roles(mastered_role)
            try:
                # Swap 💎 for set progress
                await multi_update_nickname(alias, member)
            except Forbidden:
                pass

    async def add(level: dict):
        '''Add guild channels and roles.'''

        # Create channel which defaults to no read permission
        level_name = level['discord_name']
        category_name = level['discord_category']
        channel = get(guild.channels, name=level_name)
        if not channel:
            category = get(guild.categories, name=category_name)
            if not category:
                # Create category if nonexistent
                category = await guild.create_category(name=category_name)

            # Create text channel inside category
            channel = await category.create_text_channel(level_name)

        # Set read permission for Riddler role
        riddler = get(guild.roles, name='Riddler')
        await channel.set_permissions(riddler, read_messages=True)

        # Unset read permission for @everyone
        everyone = guild.default_role
        await channel.set_permissions(everyone, read_messages=False)

        # Create "reached" level role
        role_name = 'reached-' + level_name
        reached = get(guild.roles, name=role_name)
        if not reached:
            color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
            reached = await guild.create_role(name=role_name, color=color)

        if not level['is_secret']:
            # Add new level immediately to riddle's level list
            riddle.levels[level_name] = level

            # Set read permissions to completed and set completion roles
            set_role = set_completion_roles[category_name]
            await channel.set_permissions(set_role, read_messages=True)

            # Set read permission to current roles for
            # this channel and every other ancestor level channel
            ancestor_levels = await get_ancestor_levels(data['alias'], level)
            for channel in guild.channels:
                if channel.name in ancestor_levels:
                    await channel.set_permissions(reached, read_messages=True)

            # Remove "completed" role from members
            for member in guild.members:
                await member.remove_roles(completed_role)
                await multi_update_nickname(alias, member)

            # Also remove "mastered" status
            await clear_mastered()

        else:
            # Add new level immediately to riddle's level list
            riddle.secret_levels[level_name] = level

            # Create "solved" secret level role
            role_name = 'solved-' + level_name
            solved = get(guild.roles, name=role_name)
            if not solved:
                color = discord.Color.teal()
                solved = await guild.create_role(name=role_name, color=color)

                # Place role just after "winners" on role list (to show color)
                # pos = winners.position - 1
                # positions = {solved: pos}
                # await guild.edit_role_positions(positions)

            # Set "reached" and "solved" read permission to the new channel
            await channel.set_permissions(reached, read_messages=True)
            await channel.set_permissions(solved, read_messages=True)

            # No more masters since max score was increased
            await clear_mastered()

    # If no levels to be added, then it's a request related to new cheevos.
    # So just clear mastered statuses and that's it.
    if not 'levels' in data:
        await clear_mastered()
        return web.Response(status=200)

    # Add level channels and roles to the guild
    levels = json.loads(data['levels'])
    for level in levels:
        text = f"**[{guild.name}]** Processing level **{level['name']}**..."
        for member in guild.members:
            if member.guild_permissions.administrator and not member.bot:
                await member.send(text)
        try:
            await add(level)
        except:
            # Print glorious (and much needed) traceback info
            tb = traceback.format_exc()
            logging.error(tb)

    # Send success message to guild admins
    text = (
        f"**[{guild.name}]** ✨ Channel(s) and role(s) "
            "have been successfully built! ✨"
    )
    for member in guild.members:
        if member.guild_permissions.administrator and not member.bot:
            await member.send(text)

    return web.Response(status=200)


async def update(request):
    '''Úpdate Discord-specific guild info.'''

    # Update channel name
    data = request.rel_url.query
    guild = get(bot.guilds, id=int(data['guild_id']))
    channel = get(guild.channels, name=data['old_name'])
    await channel.edit(name=data['new_name'])

    # Update "reached" (and possibly "solved") role name(s)
    reached = get(guild.roles, name=f"reached-{data['old_name']}")
    await reached.edit(name=f"reached-{data['new_name']}")
    solved = get(guild.roles, name=f"solved-{data['old_name']}")
    if solved:
        await reached.edit(name='solved-{data["new_name"]}')

    # Log message to admin by DM
    text = (
        f"**[{guild.name}]** "
        f"Renamed level **{data['old_name']}** "
            f"channel and role(s) to **{data['new_name']}**"
    )
    for member in guild.members:
        if member.guild_permissions.administrator and not member.bot:
            await member.send(text)

    return web.Response(status=200)


async def setup(_):
    pass
