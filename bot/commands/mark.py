from discord.ext import commands
from discord_slash import cog_ext, SlashContext

from bot import bot


class Mark(commands.Cog):
    '''Admin commands to send messages to members or channels.'''

    @cog_ext.cog_slash(name='mark')
    async def mark(self, ctx: SlashContext):
        text = ctx.message.content
        await ctx.send(text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Mark(bot))
