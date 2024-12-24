import json

from aiohttp import web
from discord.ext import commands
from discord.utils import get

from bot import bot


async def is_member_of_guild(request):
    '''Check if user is currently member of given guild'''

    data = request.rel_url.query
    guild = get(bot.guilds, id=int(data['guild_id']))
    if guild:
        member = get(guild.members, name=data['username'])
        if member:
            return web.Response(text="True")
    return web.Response(text="False")


async def is_member_and_has_permissions(request):
    '''Check if user is a current member
    AND has enough permissions in given guild.'''

    # Get Discord member object
    data = request.rel_url.query
    guild = get(bot.guilds, id=int(data['guild_id']))
    if not guild:
        # No associated guild
        return web.Response(text="False")
    member = get(guild.members, name=data['username'])
    if not member:
        # Not a member
        return web.Response(text="False")

    # Check if all needed permissions are on
    permissions = ('manage_roles', 'manage_channels', 'manage_nicknames')
    for s in permissions:
        permission = getattr(member.guild_permissions, s)
        if not permission:
            return web.Response(text="False")

    return web.Response(text="True")


async def get_riddle_icon_url(request):
    '''Get riddle's icon URL from its guild ID.'''

    guild_id = int(request.rel_url.query['guild_id'])
    guild = get(bot.guilds, id=guild_id)
    if not guild:
        return web.Response(status=404)
    url = str(guild.icon)
    return web.Response(text=url)


async def fetch_riddle_icon_urls(_request):
    '''Fetch all riddles' icon URLs,
    returning a JSON dict of pairs (guild ID -> url).'''

    urls = {}
    for guild in bot.guilds:
        url = str(guild.icon)
        urls[guild.id] = url
    data = json.dumps(urls)
    return web.Response(text=data)


async def get_avatar_url(request):
    '''Get avatar URL from a user by their Discord handle.'''

    # members = bot.get_all_members()
    # username = request.rel_url.query['username']
    # user = get(members, name=username)
    discord_id = request.rel_url.query['discord_id']
    print(discord_id)
    url = (
        str((await bot.fetch_user(discord_id)).avatar) if discord_id != '0'
        else '/static/images/locked.png'
    )
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
        # members = bot.get_all_members()
        data = request.rel_url.query.get('discord_ids')
        members = [await bot.fetch_user(discord_id) for discord_id in json.loads(data)]

    # Build dict of (username -> URL)
    urls = {}
    for member in members:
        url = str(member.avatar)
        urls[member.name] = url

    # Convert dict to JSON format and return response with it
    data = json.dumps(urls)
    return web.Response(text=data)


async def setup(_):
    pass
