import discord
from discord.utils import get

from bot import bot
from riddle import riddles
from unlock import update_nickname


@bot.ipc.route()
async def update(data):
    '''Update guild channels and roles according to database changes.'''

    # Get guild and riddle objects from guild id
    guild = get(bot.guilds, id=data.guild_id)
    riddle = get(riddles.values(), guild=guild)

    # Loop between each level
    for level in (data.levels, data.secret_levels):
        id = level['level_id']
        if not id:
            continue
        print('> [%s] Processing level %s...' % (guild.name, id))

        # Create channel which defaults to no read permission
        channel = get(guild.channels, name=id)
        if not channel:
            category = get(guild.categories, name=level['category'])
            if not category:
                # Create category if nonexistent
                category = await guild.create_category(name=level['category'])
            channel = await category.create_text_channel(id)
        if channel:
            overwrite = discord.PermissionOverwrite(read_messages=False)
            overwrites = {guild.default_role: overwrite}
            await channel.edit(overwrites=overwrites)

        # Create "reached" level role
        name = 'reached-' + id
        reached = get(guild.roles, name=name)
        if not reached:
            color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
            reached = await guild.create_role(name=name, color=color)  

        winners = get(guild.roles, name='winners')
        if id in data.levels.values():
            # Set read permission to current roles for 
            # this channel and every other level channel before it
            for channel in guild.channels:
                name = 'reached-%s' % channel.name
                level_role = get(guild.roles, name=name)
                if level_role:
                    await channel.set_permissions(reached, read_messages=True)

            # Add new level immediately to riddle's level list
            riddle.levels[id] = level

            # Swap "winners" role for just created "reached" level role
            for member in guild.members:
                if winners in member.roles:
                    await member.remove_roles(winners)
                    await member.add_roles(reached)
                    await update_nickname(member, '[%s]' % id)
        
        elif id in data.secret_levels.values():
            # Create "solved" secret level role
            name = 'solved-' + id
            solved = get(guild.roles, name=name)
            if not solved:
                color = discord.Color.teal()
                solved = await guild.create_role(name=name, color=color)

                # Place role just after "winners" on role list (to show color)
                pos = winners.position - 1
                positions = {solved: pos}
                await guild.edit_role_positions(positions)

            # Set "reached" and "solved" read permission to the new channel
            await channel.set_permissions(reached, read_messages=True)
            await channel.set_permissions(solved, read_messages=True)

            # Add new level immediately to riddle's level list
            riddle.secret_levels[id] = level

    print('> [%s] Channel and roles building complete :)' % guild.name)
