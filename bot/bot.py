import discord
from discord import Intents
from discord.ext import commands


class Bot(commands.Bot):
    '''Extended bot class.'''

    def __init__(self):
        '''Build default bot with "!" prefix and member intents.'''

        # Bot building (native discord.py commands won't be used)
        intents = Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.tree.copy_global_to(guild=discord.Object(id=987832530826833920))
        await self.tree.sync()


# Global bot object to be used on other modules
bot: commands.Bot = Bot()

@bot.command()
async def sync(ctx):
    print("sync command")
    if ctx.author.id == 315940379553955844:
        await bot.tree.sync()
        await ctx.send('Command tree synced.')
    else:
        await ctx.send('You must be the owner to use this command!')
