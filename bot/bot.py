from discord import Intents
from discord.ext import commands
from discord.ext.ipc import Server
from discord_slash import SlashCommand


class Bot(commands.Bot):
    '''Extended bot class to contain IPC server.'''

    ipc: Server
    '''Bot server for inter-process communication with Quart'''
    
    slash: SlashCommand
    '''Slash Commands object for dealing with special "/" commands'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''
        
        # Bot building
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix='/', intents=intents)
        
        # Init Slash Commands object
        self.slash = SlashCommand(self, override_type=True,)
        
        # Load commands extensions
        # self.load_extension('decipher')
        
        # Start IPC server
        self.ipc = Server(self, secret_key='RASPUTIN')
        self.ipc.start()

    async def on_ipc_error(self, endpoint: str, error):
        '''Called upon error being raised within an IPC route.'''
        print('[ERROR]', endpoint, 'raised', error)


# Global bot object to be used on other modules
bot: commands.Bot = Bot()
