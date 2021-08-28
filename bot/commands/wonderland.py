from discord.ext import commands
from discord import Member
from discord.utils import get

from util.db import database


class Wonderland(commands.Cog):
    '''Wonderland guild bot events.'''
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        '''Grant (global) score-based role upon player joining Wonderland.'''

        guild = member.guild
        if guild.name != 'Riddler\'s Wonderland II':
            return

        # Build dict of (non zero) player's global scores
        query = 'SELECT * FROM accounts ' \
                'WHERE global_score > 0'
        result = await database.fetch_all(query)
        global_scores = {}
        for row in result:
            handle = '%s#%s' % (row['username'], row['discriminator'])
            global_scores[handle] = row['global_score']
        
        # Get player's handle (ignoring non player members)
        handle = '%s#%s' % (member.name, member.discriminator)
        if not handle in global_scores:
            return

        # Pick up and grant role based on minimum global score achieved
        if global_scores[handle] >= 100000:
            role = get(guild.roles, name='Master Riddlers')
        elif global_scores[handle] >= 50000:
            role = get(guild.roles, name='Expert Riddlers')
        elif global_scores[handle] >= 10000:
            role = get(guild.roles, name='Seasoned Riddlers')
        else:
            role = get(guild.roles, name='Beginner Riddlers')
        await member.add_roles(role)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Wonderland(bot))
