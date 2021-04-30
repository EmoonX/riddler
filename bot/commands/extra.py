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
        await ctx.respond()
        await ctx.send('Pong! (%dms)' % latency)

    @commands.command()
    async def balthify(self, ctx):
        '''Turn text into Balthazar-speak!'''
        
        text = ctx.message.content.split()
        if len(text) == 1:
            # Command usage
            text = '> `!balthify` - Turn text into Balthazar-speak\n' \
                    '> • Usage: `!balthify <text>`'
        else:
            # Transform text into uppercase, remove spaces
            # and punctuation and keep numbers
            text = list(''.join(text[1:]))
            for i in range((len(text))):
                if text[i].isalpha():
                    text[i] = text[i].upper()
                elif not text[i].isdigit():
                    text[i] = ''
            text = ''.join(text)

        # Send message
        if text:
            if not ctx.guild:
                await ctx.author.send(text)
            else:
                await ctx.channel.send(text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Extra(bot))
