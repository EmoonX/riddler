import logging

from discord import Role
from discord.ext import commands

from util.db import database


class Guild(commands.Cog):
    '''Guild bot events.'''

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: Role, after: Role):
        '''Update special role names (honors and set completion ones)
        in DB when changed on guild by admin.'''

        if before.guild.name == "Riddler's Wonderland II":
            return
        if before.name == after.name:
            return

        # Pick up honor and milestone role names from DB
        query = '''
            SELECT * FROM riddles
            WHERE guild_id = :guild_id
        '''
        values = {'guild_id': before.guild.id}
        riddle = await database.fetch_one(query, values)

        query = None
        values = {'riddle': riddle['alias'], 'new_name': after.name}

        # Check if an honor role was changed
        honor_roles = ('completed_role', 'mastered_role')
        honor_changed = False
        for role in honor_roles:
            role_name = riddle[role]
            if before.name == role_name:
                query = f"""
                    UPDATE riddles SET {role} = :new_name
                    WHERE alias = :riddle
                """
                await database.execute(query, values)
                honor_changed = True
                break

        # Otherwise, check if milestone role was changed
        query = '''
            SELECT * FROM level_sets
            WHERE riddle = :riddle
        '''
        result = await database.fetch_all(query, {'riddle': riddle['alias']})
        set_completions = set(row['completion_role'] for row in result)
        if before.name in set_completions:
            query = '''
                UPDATE level_sets
                SET completion_role = :new_name
                WHERE riddle = :riddle AND completion_role = :old_name
            '''
            values['old_name'] = before.name
            await database.execute(query, values)
        elif not honor_changed:
            # Change happened on irrelevant role
            return

        # Log role name change
        logging.info(
            ('\033[1m[%s]\033[0m Role \033[1m@%s\033[0m '
                'changed to \033[1m@%s\033[0m'),
            before.guild.name, before.name, after.name
        )


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Guild(bot))
