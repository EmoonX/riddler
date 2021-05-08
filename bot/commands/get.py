import json

from aiohttp import web
from discord.utils import get

from bot import bot


async def is_member_and_has_permissions(request):
    '''Return if user is a current member 
    AND has enough permissions in given guild.'''
    
    # Get Discord member object
    data = request.rel_url.query
    guild = get(bot.guilds, id=int(data['guild_id']))
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
    guild_id = int(request.rel_url.query['guild_id'])
    guild = get(bot.guilds, id=guild_id)
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


async def fetch_avatar_urls(request):
    '''Fetch avatar URLs and return a dict of them. If `guild`
    is given, fetch all user avatars from a given guild;
    otherwise, just fetch avatars from all guilds.'''

    guild_id = request.rel_url.query.get('guild_id')
    members = None
    if guild_id:
        # Get all given guild members
        guild_id = int(guild_id)
        guild = get(bot.guilds, id=guild_id)
        members = guild.members
    else:
        # Get members from all guilds bot has access
        members = bot.get_all_members()
    
    # Build dict of pairs (DiscordTag -> URL)
    urls = {}
    for member in members:
        tag = member.name + '#' + member.discriminator
        url = str(member.avatar_url)
        urls[tag] = url
    
    # Convert dict to JSON format and return response with it
    data = json.dumps(urls)
    return web.Response(text=data)


def setup(_):
    pass
