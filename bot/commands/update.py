import json
import logging
import traceback

from aiohttp import web
import discord
from discord.utils import get

from bot import bot
from riddle import riddles
from commands.unlock import update_nickname
from util.db import database


async def insert(request):
    '''Build guild channels and roles from level data.'''

    # Get riddle and guild info from DB
    data = request.rel_url.query
    query = 'SELECT * FROM riddles ' \
            'WHERE alias = :alias'
    values = {'alias': data['alias']}
    result = await database.fetch_one(query, values)

    # Get guild and riddle objects,
    # and likewise completed and mastered roles
    guild = get(bot.guilds, id=result['guild_id'])
    riddle = get(riddles.values(), guild=guild)
    completed_role = get(guild.roles, name=result['completed_role'])
    mastered_role = get(guild.roles, name=result['mastered_role'])

    async def add(level: dict):
        '''Add guild channels and roles.'''
        
        # Create channel which defaults to no read permission
        name = level['discord_name']
        channel = get(guild.channels, name=name)
        if not channel:
            category = get(guild.categories, name=level['discord_category'])
            if not category:
                # Create category if nonexistent
                category = await guild.create_category(name=level['discord_category'])

            # Create text channel inside category    
            channel = await category.create_text_channel(name)

            # Set read permission for Riddler role
            riddler = get(guild.roles, name='Riddler')
            await channel.set_permissions(riddler, read_messages=True)
            
            # Unset read permission for @everyone
            everyone = guild.default_role
            await channel.set_permissions(everyone, read_messages=False)

        # Create "reached" level role
        role_name = 'reached-' + name
        reached = get(guild.roles, name=role_name)
        if not reached:
            color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
            reached = await guild.create_role(name=role_name, color=color)

        if not level['is_secret']:
            # Add new level immediately to riddle's level list
            riddle.levels[level['name']] = level
            
            # Set read permissions to completed role
            await channel.set_permissions(completed_role, read_messages=True)
            
            # Set read permission to current roles for 
            # this channel and every other level channel before it
            for channel in guild.channels:
                other_level = None
                for other in riddle.levels.values():
                    if other['discord_name'] == channel.name:
                        other_level = other
                        break
                if other_level and other_level['index'] <= level['index']:
                    await channel.set_permissions(reached, read_messages=True)

            # Swap "completed" and "mastered" roles
            # for last "reached" level role
            last_index = level['index'] - 1
            last_level = None
            for level in riddle.levels.values():
                if level['index'] == last_index:
                    last_level = level
                    break
            if last_level:
                last_name = 'reached-' + last_level['discord_name']
                last_reached = get(guild.roles, name=last_name)
                for member in guild.members:
                    if not member.nick or not member.nick[-1] in ('🏅', '💎'):
                        continue
                    if completed_role in member.roles:
                        await member.remove_roles(completed_role)
                        if mastered_role in member.roles:
                            await member.remove_roles(mastered_role)
                    await member.add_roles(last_reached)
                    await update_nickname(member, '[%s]' % last_level['name'])
        
        else:
            # Add new level immediately to riddle's level list
            riddle.secret_levels[name] = level
            
            # Create "solved" secret level role
            role_name = 'solved-' + name
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

    # Add level channels and roles to the guild
    levels = json.loads(data['levels'])
    for level in levels:
        text = '**[%s]** Processing level **%s**...' \
                % (guild.name, level['name'])
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
    text = '**[%s]** Channel and roles building complete :)' % guild.name
    for member in guild.members:
        if member.guild_permissions.administrator and not member.bot:
            await member.send(text)
    
    return web.Response(status=200)


async def update(request):
    '''Úpdate Discord-specific guild info.'''
    
    # Update channel name
    data = request.rel_url.query
    guild = get(bot.guilds, name=int(data['guild_id']))
    channel = get(guild.channels, name=data['old_name'])
    await channel.edit(name=data['new_name'])
    
    # Update "reached" (and possibly "solved") role name(s)
    reached = get(guild.roles, name=('reached-%s' % data['old_name']))
    await reached.edit(name=('reached-%s' % data['new_name']))
    solved = get(guild.roles, name=('solved-%s' % data['old_name']))
    if solved:
        await reached.edit(name=('solved-%s' % data['new_name']))
    
    # Log message to admin by DM
    text = '**[%s]** Renamed level **%s** channel and role(s) to **%s**' \
            % (guild.name, data['old_name'], data['new_name'])
    for member in guild.members:
        if member.guild_permissions.administrator and not member.bot:
            await member.send(text)
    
    return web.Response(status=200)


def setup(_):
    pass
