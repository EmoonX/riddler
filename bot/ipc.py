from discord.utils import get

from bot import bot
from riddle import riddles


@bot.ipc.route()
async def get_riddle_icon_url(data):
    '''Get riddle's Discord guild info (in dict form) from name.'''
    guild = get(bot.guilds, name=data.name)
    url = str(guild.icon_url)
    return url


@bot.ipc.route()
async def get_avatar_url(data):
    '''Get avatar URL from a user by their DiscordTag.'''
    members = bot.get_all_members()
    user = get(members, name=data.username, discriminator=data.disc)
    url = str(user.avatar_url)
    return url


@bot.ipc.route()
async def unlock(data):
    
    # Get unlock handler for guild member
    riddle = riddles[data.alias]
    member = get(riddle.guild.members,
            name=data.name, discriminator=data.disc)
    uh = riddle.uh_dict[member]

    # Call unlocking method by name
    method = uh.__getattribute__(data.method)
    await method(data.level, data.points)
