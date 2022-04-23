import glob
import os
import logging

from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand


class Bot(commands.Bot):
    '''Extended bot class.'''

    slash: SlashCommand
    '''Slash Commands object for dealing with interactions.'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''

        # Bot building (native discord.py commands won't be used)
        intents = Intents.default()
        intents.members = True
        super().__init__('%', help_command=None, intents=intents)

        # Create Slash Commands object
        self.slash = SlashCommand(self, sync_commands=True)


# Global bot object to be used on other modules
bot: commands.Bot = Bot()

# Iterate through command modules and automatically load extensions
commands_dir = os.getcwd() + '/commands'
os.chdir(commands_dir)
for path in glob.glob('**/*.py', recursive=True):
    if path.endswith('.py'):
        if 'mark' in path or 'send' in path:
            continue
        name = path.removesuffix('.py').replace('/', '.')
        name = 'commands.' + name
        logging.info('Loading extension %s...', name)
        bot.load_extension(name)
