import logging

import requests

from discord.ext import commands
from discord import User as DiscordUser
from discord.errors import Forbidden


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
                or before.discriminator != before.discriminator:
            # Username and/or discriminator were changed, so
            # send a request to webserver to update DB tables
            pass


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(User(bot))
