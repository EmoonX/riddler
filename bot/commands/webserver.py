import asyncio
import json
import logging
import traceback

from aiohttp import web
from discord.ext import commands
from discord.utils import get

from riddle import riddles
from commands.get import is_member_and_has_permissions, \
        get_riddle_icon_url, get_avatar_url, fetch_avatar_urls
from commands.update import insert, update
from commands.unlock import UnlockHandler
from util.db import database

      
class WebServer(commands.Cog):
        
    def __init__(self, bot):
        self.bot = bot
        
    async def webserver(self):
        '''Set up aiohttp webserver for handling
        requests from the Quart webserver.'''
        app = web.Application()
        app.router.add_get('/is-member-and-has-permissions',
                is_member_and_has_permissions)
        app.router.add_get('/get-riddle-icon-url', get_riddle_icon_url)
        app.router.add_get('/get-avatar-url', get_avatar_url)
        app.router.add_get('/fetch-avatar-urls', fetch_avatar_urls)
        app.router.add_get('/insert', insert)
        app.router.add_get('/update', update)
        app.router.add_get('/unlock', unlock)
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
    alias = data['alias']
    riddle = riddles[alias]
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
        return web.Response(status=500)
    
    # If player has gotten max score,
    # give him mastered special role and 💎 on nick 
    methods = ('cheevo_found', 'secret_solve', 'game_completed')
    if params['method'] in methods:
        # Check if player completed all levels
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name NOT IN ' \
                    '(SELECT name FROM user_levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND completion_time IS NOT NULL)'
        values = {'riddle': alias,
                'name': data['username'], 'disc': data['disc']}
        result_levels = await database.fetch_one(query, values)

        # Check if player unlocked all achievements
        query = 'SELECT * FROM achievements ' \
                'WHERE riddle = :riddle AND title NOT IN ' \
                    '(SELECT title FROM user_achievements ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc)'
        result_cheevos = await database.fetch_one(query, values)

        # If nothing was found, then player got everything
        if not result_levels and not result_cheevos:
            await uh.game_mastered(alias)        
    
    return web.Response(status=200)


def setup(bot):
    web = WebServer(bot)
    bot.add_cog(web)
    bot.loop.create_task(web.webserver())
