import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext


class Decipher(commands.Cog):
    '''Several commands for deciphering codes.'''
    
    def __init__(self, bot):
        self.bot = bot
        
    @cog_ext.cog_slash(name='bintoascii')
    async def bintoascii(self, ctx: SlashContext):
        '''Convert binary string(s) to ASCII character representation.'''
        pass



def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Decipher(bot))
