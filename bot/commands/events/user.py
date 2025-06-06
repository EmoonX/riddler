import logging

from discord import User as DiscordUser, Member
from discord.ext import commands
from discord.utils import get
from discord.errors import Forbidden

from commands.unlock import update_nickname, multi_update_nickname
from util.db import database


class User(commands.Cog):
    '''User bot events.'''

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        '''Procedures upon players joining riddle guilds.'''

        # Get riddle alias from guild ID
        guild = member.guild
        query = '''
            SELECT * FROM riddles
            WHERE guild_id = :id
        '''
        values = {'id': guild.id}
        riddle = await database.fetch_one(query, values)
        if not riddle:
            # Nothing to do (e.g Wonderland)
            return
        alias = riddle['alias']

        # Grant completed set roles
        query = '''
            SELECT * FROM level_sets AS ls
            INNER JOIN user_levels AS ul
                ON ls.riddle = ul.riddle AND ls.final_level = ul.level_name
            WHERE ls.riddle = :riddle
                AND ul.username = :username
                AND ul.completion_time IS NOT NULL
        '''
        values = {'riddle': alias, 'username': member.name}
        level_sets = await database.fetch_all(query, values)
        for level_set in level_sets:
            role_name = level_set['completion_role']
            if role_name:
                set_role = get(guild.roles, name=role_name)
                await member.add_roles(set_role)

        # Grant current reached level role(s)
        query = '''
            SELECT * FROM user_levels AS ul
            INNER JOIN levels AS lv
                ON ul.riddle = lv.riddle AND ul.level_name = lv.name
            WHERE ul.riddle = :riddle
                AND ul.username = :username
                AND lv.is_secret IS NOT TRUE
                AND ul.completion_time IS NULL
        '''
        current_levels = await database.fetch_all(query, values)
        for level in current_levels:
            role_name = f"reached-{level['discord_name']}"
            level_role = get(guild.roles, name=role_name)
            await member.add_roles(level_role)

        # Grant reached/solved roles for secret levels
        query = '''
            SELECT * FROM user_levels AS ul
            INNER JOIN levels AS lv
                ON ul.riddle = lv.riddle AND ul.level_name = lv.name
            WHERE ul.riddle = :riddle
                AND ul.username = :username
                AND lv.is_secret IS TRUE
        '''
        secret_levels = await database.fetch_all(query, values)
        for level in secret_levels:
            role_name = 'solved' if level['completion_time'] else 'reached'
            role_name += f"-{level['discord_name']}"
            role = get(member.guild.roles, name=role_name)
            await member.add_roles(role)

        # Update nickname
        await multi_update_nickname(alias, member)

        # Check if player finished all levels (main and secret)
        query = '''
            SELECT * FROM levels AS lv
            WHERE riddle = :riddle AND `name` NOT IN (
                SELECT level_name FROM user_levels AS ul
                WHERE riddle = :riddle
                    AND username = :username
                    AND completion_time IS NOT NULL
            )
        '''
        has_remaining_level = await database.fetch_one(query, values)
        if not has_remaining_level:
            # Check if player has gotten all achievements
            query = '''
                SELECT * FROM achievements
                WHERE riddle = :riddle AND `title` NOT IN (
                    SELECT `title` FROM user_achievements
                    WHERE riddle = :riddle AND username = :username
                )
            '''
            values.pop('final_name')
            has_locked_cheevo = await database.fetch_one(query, values)
            if not has_locked_cheevo:
                # Grant mastered honor and 💎 on nick
                mastered_role = get(guild.roles, name=riddle['mastered_role'])
                await member.add_roles(mastered_role)
                await update_nickname(member, '💎')

    @commands.Cog.listener()
    async def on_user_update(self, before: DiscordUser, after: DiscordUser):
        '''
        If username and/or global name change,
        update user\'s guild nicknames and user-related DB tables.
        '''

        async def _update_database(field: str):
            '''Update database for either username or global name changes.'''
            query = f""" 
                UPDATE accounts
                SET {field} = :name_new
                WHERE discord_id = :discord_id
            """
            values = {
                'name_new': (
                    after.name if field == 'username'
                    else after.global_name
                ),
                'discord_id': after.id
            }
            await database.execute(query, values)

        if before.name != after.name:
            # Username has changed
            # Update nicks for every guild user is in
            for guild in self.bot.guilds:
                member = guild.get_member(before.id)
                if not member or not member.nick:
                    continue
                old_nick = member.nick
                idx = len(before.name) + 1
                s = old_nick[idx:]
                try:
                    await update_nickname(member, s)
                    logging.info(
                        '[%s] Nickname "%s" changed to "%s"',
                        guild.name, old_nick, member.nick
                    )
                except Forbidden:
                    logging.info(
                        '[%s] (403) Can\'t change nick of "%s"',
                        guild.name, member.name
                    )
            
            await _update_database('username')
            logging.info(f"Username update: {before.name} -> {after.name}")
            
        if before.global_name != after.global_name:
            # Global name has changed
            await _update_database('display_name')
            logging.info(
                "Display name update: "
                f"{before.global_name} -> {after.global_name}"
            )


async def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    await bot.add_cog(User(bot))
