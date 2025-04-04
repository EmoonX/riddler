from datetime import datetime
import logging

import discord
from discord.ext import commands


class Bot(commands.Bot):
    '''Extended bot class.'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''

        # Bot building (native discord.py commands won't be used)
        intents = discord.Intents.default()
        intents.members = intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.tree.copy_global_to(guild=discord.Object(id=987832530826833920))
        await self.tree.sync()


# Global bot object to be used on other modules
bot: commands.Bot = Bot()

@bot.command()
async def sync(ctx):
    '''Prefix command; sync bot slash commands.'''
    if ctx.author.id == 315940379553955844:
        await bot.tree.sync()
        await ctx.send('Command tree synced.')
    else:
        await ctx.send('You must be an admin to use this command!')

async def check(interaction: discord.Interaction) -> bool:
    '''Log user and command name before each slash command run.'''
    username = interaction.user.name
    command = interaction.command.qualified_name
    logging.info(
        f"> \033[1m{username}\033[0m "
        f"used command \033[3;36m/{command}\033[0m "
        f"({datetime.utcnow()})"
    )
    return True  # command should be run

# Override global slash commands checker
bot.tree.interaction_check = check
