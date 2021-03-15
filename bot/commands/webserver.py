import asyncio
import traceback
import logging

from aiohttp import web
from discord.ext import commands
from discord.utils import get

from bot import bot
from riddle import riddles
from commands.unlock import UnlockHandler

      
class WebServer(commands.Cog):
        
    def __init__(self, bot):
        self.bot = bot
        
    async def webserver(self):
        async def get_riddle_icon_url(request):
            '''Get riddle's Discord guild info (in dict form) from name.'''
            logging.info(request.rel_url.query)
            name = request.rel_url.query['name']
            guild = get(bot.guilds, name=name)
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
        
        app = web.Application()
        app.router.add_get('/get-riddle-icon-url', get_riddle_icon_url)
        app.router.add_get('/get-avatar-url', get_avatar_url)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', 4757)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())

    
def setup(bot):
    web = WebServer(bot)
    bot.add_cog(web)
    bot.loop.create_task(web.webserver())


async def is_member_and_has_permissions(data) -> bool:
    '''Return if user is a member AND has enough permissions in given guild.'''
    guild = get(bot.guilds, name=data.full_name)
    member = get(guild.members,
            name=data.username, discriminator=data.disc)
    if not member:
        return False
    permissions = ('manage_roles', 'manage_channels', 'manage_nicknames')
    for s in permissions:
        permission = getattr(member.guild_permissions, s)
        if not permission:
            return False
    return True


async def unlock(data):
    '''Ŕeceive data from web request and issue unlocking method.'''
    
    # Get unlock handler for guild member
    riddle = riddles[data.alias]
    member = get(riddle.guild.members,
            name=data.name, discriminator=data.disc)
    uh = UnlockHandler(riddle.guild, riddle.levels, member)

    # Get argument tuple according to method to be called
    args = ()
    if data.method in ('advance', 'secret_found'):
        args = (data.level,)
    elif data.method == 'beat':
        args = (data.level, data.points, data.first_to_solve, data.milestone)
    elif data.method == 'secret_solve':
        args = (data.level, data.points, data.first_to_solve)
    elif data.method == 'cheevo_found':
        args = (data.cheevo, data.points)
    elif data.method == 'game_completed':
        args = (data.winners_role,)

    # Call unlocking method by name with correct number of args
    try:
        method = getattr(uh, data.method)
        await method(*args)
    except:
        # Print glorious (and much needed) traceback info
        tb = traceback.format_exc()
        logging.error(tb)
