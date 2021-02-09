import discord
from discord.utils import get

from bot import bot
from riddle import riddles
from unlock import update_nickname


@bot.ipc.route()
async def build(data):
    '''Build guild channels and roles from level data.'''

    # Get guild and riddle objects from guild id
    guild = get(bot.guilds, name=data.guild_name)

    # Add level channels and roles to the guild
    for level in data.levels:
        text = '**[%s]** Processing level **%s**...' \
                 % (guild.name, level['name'])
        for member in guild.members:
            if member.name == 'NinthLyfe':
                continue
            if member.guild_permissions.administrator and not member.bot:
                await member.send(text)
        await add(guild, level)

    # Send success message to guild admins
    text = '**[%s]** Channel and roles building complete :)' % guild.name
    for member in guild.members:
        if member.name == 'NinthLyfe':
            continue
        if member.guild_permissions.administrator and not member.bot:
            await member.send(text)


async def add(guild: discord.Guild, level: dict, is_secret=False):
    '''Add guild channels and roles.'''
    
    # Create channel which defaults to no read permission
    name = level['name']
    channel = get(guild.channels, name=name)
    if not channel:
        category = get(guild.categories, name=level['category'])
        if not category:
            # Create category if nonexistent
            category = await guild.create_category(name=level['category'])
        channel = await category.create_text_channel(name)
    if channel:
        overwrite = discord.PermissionOverwrite(read_messages=False)
        overwrites = {guild.default_role: overwrite}
        await channel.edit(overwrites=overwrites)

    # Create "reached" level role
    role_name = 'reached-' + name
    reached = get(guild.roles, name=role_name)
    if not reached:
        color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
        reached = await guild.create_role(name=role_name, color=color)  

    riddle = get(riddles.values(), guild=guild)
    winners = get(guild.roles, name='winners')
    if not is_secret:
        # Set read permission to current roles for 
        # this channel and every other level channel before it
        for channel in guild.channels:
            role_name = 'reached-%s' % channel.name
            level_role = get(guild.roles, name=role_name)
            if level_role:
                await channel.set_permissions(reached, read_messages=True)
        
        # Set read permission for @winners too
        await channel.set_permissions(winners, read_messages=True)

        # Add new level immediately to riddle's level list
        riddle.levels[name] = level

        # Swap "winners" role for just created "reached" level role
        for member in guild.members:
            if winners in member.roles:
                await member.remove_roles(winners)
                await member.add_roles(reached)
                await update_nickname(member, '[%s]' % name)
    
    else:
        # Create "solved" secret level role
        role_name = 'solved-' + name
        solved = get(guild.roles, name=role_name)
        if not solved:
            color = discord.Color.teal()
            solved = await guild.create_role(name=role_name, color=color)

            # Place role just after "winners" on role list (to show color)
            pos = winners.position - 1
            positions = {solved: pos}
            await guild.edit_role_positions(positions)

        # Set "reached" and "solved" read permission to the new channel
        await channel.set_permissions(reached, read_messages=True)
        await channel.set_permissions(solved, read_messages=True)

        # Add new level immediately to riddle's level list
        riddle.secret_levels[id] = level
