import logging

from discord.ext import commands
from discord import User as DiscordUser, Member
from discord.utils import get
from discord.errors import Forbidden

from commands.unlock import UnlockHandler, update_nickname
from util.db import database


class User(commands.Cog):
    '''User bot events.'''
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        # Get riddle alias from guild ID
        query = 'SELECT * FROM riddles ' \
                'WHERE guild_id = :id'
        values = {'id': member.guild.id}
        result = await database.fetch_one(query, values)
        alias = result['alias']

        # Get player riddle account
        query = 'SELECT * FROM riddle_accounts ' \
                'WHERE riddle = :alias ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'alias': alias,
                'name': member.name, 'disc': member.discriminator}
        account = await database.fetch_one(query, values)
        if not account:
            # Member still hasn't started riddle, so nothing to do
            return

        # Build UnlockHandler object for unlocking procedures
        uh = UnlockHandler(alias, member.name, member.discriminator)
        
        # Advance member's progress to current reached normal level
        current_level = account['current_level']
        if current_level != '🏅':
            query = 'SELECT * FROM levels ' \
                    'WHERE riddle = :alias AND name = :level_name'
            values = {'alias': alias, 'level_name': current_level}
            level = await database.fetch_one(query, values)
            await uh.advance(level)
        
        # Search for reached/solved secret levels and grant roles to member
        query = 'SELECT * FROM user_levels ' \
                'INNER JOIN levels ' \
                    'ON user_levels.riddle = levels.riddle ' \
                        'AND user_levels.level_name = levels.name ' \
                'WHERE levels.riddle = :alias AND is_secret IS TRUE ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'alias': alias,
                'name': member.name, 'disc': member.discriminator}
        secret_levels = await database.fetch_all(query, values)
        for level in secret_levels:
            role_name = 'reached-' if not level['completion_time'] \
                    else 'solved-'
            role_name += level['discord_name']
            role = get(member.guild.roles, name=role_name)
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_user_update(self, before: DiscordUser, after: DiscordUser):
        '''If username changes, update user\'s Discord guild nicknames;
        if either it or discriminator change, send a request to webserver
        to update user-related DB tables.'''

        if before.name != after.name:
            # Username was changed, so update nicks on every guild user is in
            for guild in self.bot.guilds:
                member = guild.get_member(before.id)
                if not member or not member.nick:
                    continue
                old_nick = member.nick
                idx = old_nick.rfind('[')
                progress_string = old_nick[idx:]
                try:
                    await update_nickname(member, progress_string)
                    logging.info('[%s] Nickname "%s" changed to "%s"'
                            % (guild.name, old_nick, member.nick))
                except Forbidden:
                    logging.info('[%s] (403) Can\'t change nick of "%s"'
                            % (guild.name, member.name))
        
        if before.name != after.name \
                or before.discriminator != after.discriminator:
            # Username and/or discriminator were changed, so update tables
            # (we only need to do it manually in the accounts table, since
            # remaining ones are updated in cascade per foreign keys magic).
            query = 'UPDATE accounts ' \
                    'SET username = :name_new, discriminator = :disc_new ' \
                    'WHERE username = :name_old AND discriminator = :disc_old '
            values = {'name_new': after.name, 'disc_new': after.discriminator,
                    'name_old': before.name, 'disc_old': before.discriminator}
            await database.execute(query, values)
            logging.info('User %s#%s is now known as %s#%s'
                    % (before.name, before.discriminator, 
                        after.name, after.discriminator))


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(User(bot))
