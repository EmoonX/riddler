from discord.utils import get

from bot import bot
from commands.riddle import riddles


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
    '''Ŕeceive data from IPC request and issue unlocking method.'''
    
    # Get unlock handler for guild member
    riddle = riddles[data.alias]
    member = get(riddle.guild.members,
            name=data.name, discriminator=data.disc)
    uh = riddle.uh_dict[member]

    # Get argument tuple according to method to be called
    args = ()
    if data.method in ('advance', 'secret_found'):
        args = (data.level,)
    elif data.method in ('beat', 'secret_solve'):
        args = (data.level, data.points)
    elif data.method == 'cheevo_found':
        args = (data.cheevo,)

    # Call unlocking method by name with correct number of args
    method = getattr(uh, data.method)
    await method(*args)


def setup(_):
    pass
