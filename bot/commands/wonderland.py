from discord.ext import commands
from discord import Member
from discord.utils import get

from bot import bot
from util.db import database


class Wonderland(commands.Cog):
    '''Wonderland guild bot events.'''
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        '''Grant (global) score-based role upon player joining Wonderland.'''
        guild = member.guild
        if guild.name == 'Riddler\'s Wonderland II':
            await update_score_role(member)        


async def update_score_role(member: Member):
    '''Pick up and grant role based on minimum global score achieved.'''

    # Get Wonderland's member object from received Member
    wonderland = get(bot.guilds, name='Riddler\'s Wonderland II')
    member = get(wonderland.members, id=member.id)
    if not member:
        # Not a member of Wonderland
        return

    # Get player global score from DB
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :username AND discriminator = :disc'
    values = {'username': member.name, 'disc': member.discriminator}
    result = await database.fetch_one(query, values)
    global_score = result['global_score']

    # Find old score role of user, if any
    roles = ('Master Riddlers', 'Expert Riddlers',
        'Seasoned Riddlers', 'Beginner Riddlers')
    old_role = None
    for role_name in roles:
        role = get(member.roles, name=role_name)
        if role:
            old_role = role
            break

    # Check role based on global score
    if global_score >= 100000:
        role = get(wonderland.roles, name='Master Riddlers')
    elif global_score >= 50000:
        role = get(wonderland.roles, name='Expert Riddlers')
    elif global_score >= 10000:
        role = get(wonderland.roles, name='Seasoned Riddlers')
    else:
        role = get(wonderland.roles, name='Beginner Riddlers')
    
    # Do role swap, but only if a role change indeed occurred
    if role and role != old_role:
        await member.add_roles(role)
        if old_role:
            await member.remove_roles(old_role)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Wonderland(bot))
