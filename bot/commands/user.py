import logging

from discord.ext import commands
from discord import User as DiscordUser


class User(commands.Cog):
    '''User bot events.'''
    
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_user_update(self, before: DiscordUser, after: DiscordUser):
        if before.name == after.name \
                and before.discriminator == after.discriminator:
            # Ignore other updates, like avatar ones
            return
        logging.info('Old user was: %s#%s' % (before.name, before.discriminator))
        logging.info('New user is: %s#%s' % (after.name, after.discriminator))
    

def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(User(bot))
