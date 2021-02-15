import asyncio

from discord import Intents
from discord.ext import commands
from discord.ext.ipc import Server
from cogwatch import Watcher


class Bot(commands.Bot):
    '''Extended bot class to contain IPC server.'''

    ipc: Server
    '''Bot server for inter-process communication with Quart'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        
    async def on_ready(self):
        '''Procedures upon bot initialization.'''

        print('> Bot up and running!')
        
        watcher = Watcher(self, path='commands', preload=True)
        await watcher.start()

        # Start IPC server
        self.ipc = Server(self, secret_key='RASPUTIN')
        #self.ipc.start()
        
        # Build riddles dict
        # await build_riddles()
        
        # guild = get(bot.guilds, name='RNS Riddle II')
        # for role in guild.roles:
        #     if 'reached-' in role.name:
        #         name = role.name[8:]
        #         channel = get(guild.channels, name=name)
        #         await channel.delete()
        #         await role.delete()

    async def on_ipc_error(self, endpoint: str, error):
        '''Called upon error being raised within an IPC route.'''
        print(endpoint, 'raised', error)
