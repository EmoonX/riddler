import asyncio
import json
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
        
        app = web.Application()
        app.router.add_get('/is-member-and-has-permissions',
                is_member_and_has_permissions)
        app.router.add_get('/get-riddle-icon-url', get_riddle_icon_url)
        app.router.add_get('/get-avatar-url', get_avatar_url)
        app.router.add_get('/unlock', unlock)
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
