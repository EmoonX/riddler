from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand


class Bot(commands.Bot):
    '''Extended bot class.'''
    
    slash: SlashCommand
    '''Slash Commands object for dealing with special "/" commands'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''
        
        # Bot building
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix='/', intents=intents)
        
        # Init Slash Commands object
        self.slash = SlashCommand(self, override_type=True)
        

# Global bot object to be used on other modules
bot: commands.Bot = Bot()
