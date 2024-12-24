import os

import discord
from discord import app_commands, Intents
from discord.ext import commands


class Bot(commands.Bot):
    '''Extended bot class.'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''

        # Bot building (native discord.py commands won't be used)
        intents = Intents.all()
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.tree.copy_global_to(guild=discord.Object(id=987832530826833920))
        await self.tree.sync()


# Global bot object to be used on other modules
bot: commands.Bot = Bot()

@bot.tree.command(name="ping", description="...")
async def _ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("pong")
