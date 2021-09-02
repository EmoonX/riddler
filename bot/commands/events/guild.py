import logging

from discord.ext import commands
from discord import Role
from discord.utils import get

from util.db import database


class Guild(commands.Cog):
    '''Guild bot events.'''
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before: Role, after: Role):
        '''Update special role names (honors and milestones)
        in DB when changed on guild by admin.'''

        if before.name == after.name:
            return

        # Pick up honor and milestone role names from DB
        query = 'SELECT * FROM riddles ' \
                'INNER JOIN milestones ' \
                    'ON riddles.alias = milestones.riddle ' \
                'WHERE guild_id = :guild_id'
        values = {'guild_id': before.guild.id}
        result = await database.fetch_all(query, values)
        riddle = result[0]

        query = None
        values = {'riddle': riddle['alias'], 'new_name': after.name}

        # Check if an honor role was changed
        honor_roles = ('completed_role', 'mastered_role')
        for role in honor_roles:
            role_name = riddle[role]
            if before.name == role_name:
                query = 'UPDATE riddles ' + \
                        ('SET %s = :new_name ' % role) + \
                        'WHERE alias = :riddle'
        if not query:
            # Otherwise, check if milestone role was changed
            milestones = [row['role'] for row in result]
            if before.name in milestones:
                query = 'UPDATE milestones ' \
                        'SET role = :new_name ' \
                        'WHERE riddle = :riddle AND role = :old_name '
                values['old_name'] = before.name
            else:
                # Change happened on irrelevant role
                return
        
        # Update respective DB table
        await database.execute(query, values)
        logging.info(('\033[1m[%s]\033[0m Role \033[1m@%s\033[0m ' \
                'changed to \033[1m@%s\033[0m')
                % (before.guild.name, before.name, after.name))


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Guild(bot))
