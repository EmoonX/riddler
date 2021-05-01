import logging

import requests
from aiohttp import web

from discord.ext import commands
from discord import User as DiscordUser
from discord.errors import Forbidden
from util.db import database


class User(commands.Cog):
    '''User bot events.'''
    
    def __init__(self, bot):
        self.bot = bot

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
