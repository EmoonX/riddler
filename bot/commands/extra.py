from discord import app_commands
from discord.ext import commands

from commands.util import Interaction


class Extra(commands.Cog):
    '''Extra bot commands.'''

    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command()
    async def ping(self, interaction: Interaction):
        '''Ping-pong with measurable latency.'''
        latency = 1000 * self.bot.latency
        await interaction.send(f"Pong! ({latency:.2f} ms)")

    @app_commands.command()
    async def balthify(self, interaction: Interaction, text: str):
        '''
        Turn text into Balthazar-speak.
        
        Args:
            interaction:
                The interaction object.
            text:
                Text to be converted.
        '''

        # Transform text into uppercase, remove spaces
        # and punctuation and keep numbers
        text = list(text)
        for i, c in enumerate(text):
            if c.isalpha():
                text[i] = c.upper()
            elif not c.isdigit():
                text[i] = ''
        text = ''.join(text)

        # Send message (or placeholder)
        if not text:
            text = '_Message intentionally left blank._'
        
        await interaction.send(text)


async def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    await bot.add_cog(Extra(bot))
