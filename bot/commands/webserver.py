import asyncio
import json
import logging
import traceback

from aiohttp import web
from discord.ext import commands

from commands.get import (
    is_member_of_guild, is_member_and_has_permissions,
    get_riddle_icon_url, fetch_riddle_icon_urls,
    get_avatar_url, get_all_avatar_urls,
)
from commands.unlock import UnlockHandler
from commands.update import insert, update
# from commands.wonderland import update_score_role
from util.db import database


class WebServer(commands.Cog):
    '''`aiohttp` webserver to process HTTP requests from webapp.'''

    def __init__(self, bot):
        self.bot = bot
        self.site = None

    async def webserver(self):
        '''Set up `aiohttp `webserver.'''

        # Create application and add GET routes
        app = web.Application()
        app.router.add_get('/is-member-of-guild', is_member_of_guild)
        app.router.add_get(
            '/is-member-and-has-permissions', is_member_and_has_permissions
        )
        app.router.add_get('/get-riddle-icon-url', get_riddle_icon_url)
        app.router.add_get('/fetch-riddle-icon-urls', fetch_riddle_icon_urls)
        app.router.add_get('/get-avatar-url', get_avatar_url)
        app.router.add_get('/get-all-avatar-urls', get_all_avatar_urls)
        app.router.add_get('/insert', insert)
        app.router.add_get('/update', update)
        app.router.add_get('/unlock', unlock)

        # Set up runner running on `localhost:4757`
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', 4757)
        await self.bot.wait_until_ready()
        await self.site.start()

    def __unload(self):
        asyncio.ensure_future(self.site.stop())


async def unlock(request):
    '''Ŕeceive data from web request and issue unlocking method.'''

    # Build unlock handler for guild member
    data = request.rel_url.query
    alias = data['alias']
    unlock_handler = UnlockHandler(alias, data['username'])

    # Parse JSON params into dicts
    params = {}
    for param, value in data.items():
        try:
            value = json.loads(value)
        except ValueError:
            # Ignore non-JSON params
            pass
        params[param] = value

    # Get argument tuple according to method to be called
    if params['method'] == 'advance':
        args = (params['level'],)
    elif params['method'] == 'beat':
        args = (params['level'], params['points'])
    elif params['method'] == 'cheevo_found':
        args = (params['cheevo'], params['points'], params['page'])
    else:
        args = ()

    # Call unlocking method by name with correct number of args
    try:
        method = getattr(unlock_handler, params['method'])
        await method(*args)
    except:
        # Print glorious (and much needed) traceback info
        tb = traceback.format_exc()
        logging.error(tb)
        return web.Response(status=500)

    # Special procedures to be done upon score increase
    methods = ['beat', 'cheevo_found', 'game_completed']
    if params['method'] in methods:
        # Check if player completed all levels
        query = '''
            SELECT COUNT(*) AS cnt FROM levels
            WHERE riddle = :riddle
        '''
        values = {'riddle': alias}
        result = await database.fetch_one(query, values)
        total_level_count = result['cnt']
        query = '''
            SELECT COUNT(*) AS cnt FROM user_levels
            WHERE riddle = :riddle
                AND username = :username
                AND completion_time IS NOT NULL
        '''
        values = {'riddle': alias, 'username': data['username']}
        result = await database.fetch_one(query, values)
        user_completed_count = result['cnt']
        if total_level_count == user_completed_count:
            # Check if player unlocked all achievements
            query = '''
                SELECT * FROM achievements
                WHERE riddle = :riddle AND title NOT IN (
                    SELECT title FROM user_achievements
                    WHERE riddle = :riddle AND username = :username
                )
            '''
            has_unfound_cheevos = await database.fetch_one(query, values)

            # If nothing was found, then player got everything
            if not has_unfound_cheevos:
                await unlock_handler.game_mastered()

    if 'points' in params and unlock_handler.member:
        # Update Wonderland guild score-based role, if the case
        pass
        # await update_score_role(unlock_handler.member)

    return web.Response(status=200)


async def setup(bot):
    '''Add cog and run webserver loop.'''
    _web = WebServer(bot)
    await bot.add_cog(_web)
    await bot.loop.create_task(_web.webserver())
