import asyncio
import json
import logging
import traceback

from aiohttp import web
from discord.ext import commands
from discord.utils import get

from riddle import riddles
from commands.get import is_member_and_has_permissions, \
        get_riddle_icon_url, get_avatar_url
from commands.update import insert, update
from commands.unlock import UnlockHandler
from commands.user import update_user

      
class WebServer(commands.Cog):
        
    def __init__(self, bot):
        self.bot = bot
        
    async def webserver(self):
        
        app = web.Application()
        app.router.add_get('/is-member-and-has-permissions',
                is_member_and_has_permissions)
        app.router.add_get('/get-riddle-icon-url', get_riddle_icon_url)
        app.router.add_get('/get-avatar-url', get_avatar_url)
        app.router.add_get('/insert', insert)
        app.router.add_get('/update', update)
        app.router.add_get('/unlock', unlock)
        app.router.add_get('/update-user', update_user)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', 4757)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


async def unlock(request):
    '''Ŕeceive data from web request and issue unlocking method.'''
    
    # Get unlock handler for guild member
    data = request.rel_url.query
    riddle = riddles[data['alias']]
    member = get(riddle.guild.members,
            name=data['username'], discriminator=data['disc'])
    uh = UnlockHandler(riddle.guild, riddle.levels, member)
    
    # Parse JSON params into dicts
    params = {}
    for param, value in data.items():
        try:
            value = json.loads(value)
        except:
            # Ignore non-JSON params
            pass  
        params[param] = value

    # Get argument tuple according to method to be called
    args = ()
    if params['method'] in ('advance', 'secret_found'):
        args = (params['level'],)
    elif params['method'] == 'beat':
        args = (params['level'], params['points'],
                params['first_to_solve'], params['milestone'])
    elif params['method'] == 'secret_solve':
        args = (params['level'], params['points'],
                params['first_to_solve'])
    elif params['method'] == 'cheevo_found':
        args = (params['cheevo'], params['points'])
    elif params['method'] == 'game_completed':
        args = (params['winners_role'],)

    # Call unlocking method by name with correct number of args
    try:
        method = getattr(uh, params['method'])
        await method(*args)
    except:
        # Print glorious (and much needed) traceback info
        tb = traceback.format_exc()
        logging.error(tb)
    
    return web.Response(status=200)


def setup(bot):
    web = WebServer(bot)
    bot.add_cog(web)
    bot.loop.create_task(web.webserver())
