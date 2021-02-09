import discord
from discord.ext import commands
from discord.ext.ipc import Server

# intents thingamajig for newer discord.py API version
intents = discord.Intents.default()
intents.members = True


class Bot(commands.Bot):
    '''Extended class to contain IPC server.'''

    # Bot server for inter-process communication with Quart
    ipc: Server

    def __init__(self, *args, **kwargs):
        '''Build and start bot and IPC server.'''
        super().__init__(*args, **kwargs)
        self.ipc = Server(self, secret_key='RASPUTIN')
        self.ipc.start()

    async def on_ipc_error(self, endpoint: str, error):
        '''Called upon an error being raised within an IPC route.'''
        print(endpoint, 'raised', error)


# Create bot (commands are designated starting with '!')
bot = Bot(command_prefix='!', intents=intents)

