from discord.utils import get

from bot import bot


@bot.ipc.route()
async def get_riddle_icon_url(data):
    '''Get riddle/guild icon URL from guild's ID.'''
    print(data)
    guild = get(bot.guilds, id=data.id)
    print(guild.icon)
    url = str(guild.icon_url)
    return url


@bot.ipc.route()
async def get_avatar_url(data):
    '''Get avatar URL from a user by their DiscordTag.'''
    members = bot.get_all_members()
    user = get(members, name=data.username, discriminator=data.disc)
    url = str(user.avatar_url)
    return url
