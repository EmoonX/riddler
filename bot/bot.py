from typing import DefaultDict

from discord import Intents
from discord.ext import commands
from discord.ext.ipc import Server


class Bot(commands.Bot):
    '''Extended bot class to contain IPC server.'''

    ipc: Server
    '''Bot server for inter-process communication with Quart'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''
        
        # Bot building
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Start IPC server
        self.ipc = Server(self, secret_key='RASPUTIN')
        self.ipc.start()

    async def on_ipc_error(self, endpoint: str, error):
        '''Called upon error being raised within an IPC route.'''
        print(endpoint, 'raised', error)


# Global bot object to be used on other modules
bot: commands.Bot = Bot()
