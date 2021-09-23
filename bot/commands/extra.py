from discord.ext import commands
from discord_slash import cog_ext, SlashContext


class Extra(commands.Cog):
    '''Extra bot commands.'''
    
    def __init__(self, bot):
        self.bot = bot
   
    @cog_ext.cog_slash(name='ping')
    async def ping(self, ctx: SlashContext):
        '''Ping-pong with measurable latency.'''
        latency = 1000 * self.bot.latency
        await ctx.send('Pong! (%dms)' % latency)

    @cog_ext.cog_slash(name='balthify')
    async def balthify(self, ctx: SlashContext, text: str):
        '''Turn text into Balthazar-speak!'''
        
        # Transform text into uppercase, remove spaces
        # and punctuation and keep numbers
        text = list(text)
        for i in range((len(text))):
            if text[i].isalpha():
                text[i] = text[i].upper()
            elif not text[i].isdigit():
                text[i] = ''
        text = ''.join(text)

        # Send message (or placeholder)
        if not text:
            text = '_This message was intentionally left blank._'
        await ctx.send(text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Extra(bot))
