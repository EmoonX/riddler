from aiohttp import web
from discord.utils import get

from bot import bot


async def is_member_and_has_permissions(request):
    '''Return if user is a current member 
    AND has enough permissions in given guild.'''
    
    # Get Discord member object
    data = request.rel_url.query
    guild = get(bot.guilds, name=data['full_name'])
    member = get(guild.members,
            name=data['username'], discriminator=data['disc'])
    
    # Check if it's a member of guild
    if not member:
        return web.Response(text="False")
    
    # Check if all needed permissions are on
    permissions = ('manage_roles', 'manage_channels', 'manage_nicknames')
    for s in permissions:
        permission = getattr(member.guild_permissions, s)
        if not permission:
            return web.Response(text="False")
    return web.Response(text="True")


async def get_riddle_icon_url(request):
    '''Get riddle's Discord guild info (in dict form) from name.'''
    full_name = request.rel_url.query['full_name']
    guild = get(bot.guilds, name=full_name)
    url = str(guild.icon_url)
    return web.Response(text=url)


async def get_avatar_url(request):
    '''Get avatar URL from a user by their DiscordTag.'''
    members = bot.get_all_members()
    username = request.rel_url.query['username']
    disc = request.rel_url.query['disc']
    user = get(members, name=username, discriminator=disc)
    url = str(user.avatar_url)
    return web.Response(text=url)


def setup(_):
    pass
