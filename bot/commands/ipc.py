import traceback
import logging

from discord.utils import get

from bot import bot
from riddle import riddles
from commands.unlock import UnlockHandler


@bot.ipc.route()
async def is_member_and_admin_of_guild(data):
    '''Return if user is a member AND admin of given guild.'''
    guild = get(bot.guilds, name=data.full_name)
    member = get(guild.members, name=data.username, discriminator=data.disc)
    return member and member.guild_permissions.administrator


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
    uh = UnlockHandler(riddle.guild, riddle.levels, member)

    # Get argument tuple according to method to be called
    args = ()
    if data.method in ('advance', 'secret_found'):
        args = (data.level,)
    elif data.method in ('beat', 'secret_solve'):
        args = (data.level, data.points, data.first_to_solve)
    elif data.method == 'cheevo_found':
        args = (data.cheevo, data.points)

    # Call unlocking method by name with correct number of args
    try:
        method = getattr(uh, data.method)
        await method(*args)
    except:
        # Print glorious (and much needed) traceback info
        tb = traceback.format_exc()
        logging.error(tb)


def setup(_):
    pass
