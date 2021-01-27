import discord
from discord.utils import get
from discord.ext.ipc import Server

from bot import bot

# Bot server for inter-process communication with Quart
bot_ipc = Server(bot, 'localhost', 8765, 'RASPUTIN')


@bot_ipc.route()
async def update(levels: list):
    print('IT WORKS!')
    return

    # Get guild object from guild id
    guild = get(bot.guilds, id=guild_id)

    # Loop between each level
    channels = []
    for level in levels:
        id = level['level_id']
        print('> [%s] Processing ID %d' % (guild.name, id))

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

        # Set read permission to current roles for 
        # this channel and every other before it
        for channel in channels:
            await channel.set_permissions(role, read_messages=True)

    print('> [%s] Channel and roles building complete :)' % guild.name)


# Start the IPC server
bot_ipc.start()
