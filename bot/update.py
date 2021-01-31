import discord
from discord.utils import get
from discord.ext.ipc import Server

from bot import bot
from riddle import riddles

# Bot server for inter-process communication with Quart
bot_ipc = Server(bot, secret_key='RASPUTIN')


@bot_ipc.route()
async def update(data):
    '''Update guild channels and roles according to database changes.'''

    # Get guild object from guild id
    guild = get(bot.guilds, id=data.guild_id)

    # Loop between each level
    for level in (data.levels,):
        id = level['level_id']
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

        # Create level user role
        name = 'reached-' + id
        role = get(guild.roles, name=name)
        if not role:
            color = discord.Color.from_rgb(0xcc, 0xcc, 0xcc)
            role = await guild.create_role(name=name, color=color)

        # Set read permission to current roles for 
        # this channel and every other level channel before it
        for channel in guild.channels:
            name = 'reached-%s' % channel.name
            level_role = get(guild.roles, name=name)
            if level_role:
                await channel.set_permissions(role, read_messages=True)
        
        # Add new level imediatelly to riddle's level list
        riddle = get(riddles.values(), guild=guild)
        riddle.levels[id] = level['filename_hash']

    print('> [%s] Channel and roles building complete :)' % guild.name)


# Start the IPC server
bot_ipc.start()
