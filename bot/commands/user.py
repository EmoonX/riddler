import logging

from discord.ext import commands
from discord import User as DiscordUser, Member
from discord.errors import Forbidden

from commands.unlock import UnlockHandler
from util.db import database


class User(commands.Cog):
    '''User bot events.'''
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        try:
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
            
            # Grant role to member relative to current reached normal level
            current_level = account['current_level']
            if current_level != '🏅':
                uh = UnlockHandler(alias, member.name, member.discriminator)
                query = 'SELECT * FROM levels ' \
                        'WHERE riddle = :alias AND name = :level_name'
                values = {'alias': alias, 'level_name': current_level}
                level = await database.fetch_one(query, values)
                await uh.advance(level)
            # for row in result:
            #     level_name = row['level_name']
            #     query = 'SELECT * FROM levels ' \
            #             'WHERE riddle = "rns" AND name = :level_name'
            #     values = {'level_name': level_name}
            #     level = await database.fetch_one(query, values)
            #     if level['is_secret'] == 1 and row['completion_time']:
            #         logging.info(name)
            #         logging.info(level_name)
            #         from commands.unlock import UnlockHandler
            #         uh = UnlockHandler('rns', name, member.discriminator)
            #         await uh.secret_solve(level, 0)
        except:
            import traceback
            tb = traceback.format_exc()
            logging.error(tb)

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
                # (just replace first ocurrence to avoid nonsense)
                nick_old = member.nick
                nick_new = nick_old.replace(before.name, after.name, 1)
                try:
                    await member.edit(nick=nick_new)
                    logging.info('[%s] Nickname "%s" changed to "%s"'
                            % (guild.name, nick_old, nick_new))
                except Forbidden:
                    logging.info('[%s] (403) Can\'t change nick of "%s"'
                            % (guild.name, nick_old))
        
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
