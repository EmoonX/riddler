from discord.ext import commands
from discord.utils import get

from bot import bot


class Send(commands.Cog):
    '''Admin commands to send messages to members or channels.'''

    @commands.command()
    async def send(self, ctx):
        guild = get(bot.guilds, name='Cipher: Crack the Code')
        member = get(guild.members, name=ctx.author.name)
        role = None
        if not member or not member.guild_permissions.manage_guild:
            # You are not an admin of given guild
            text = '> `!send` - Access denied'
            await member.send(text)
            return

        aux = ctx.message.content.split(maxsplit=3)
        if len(aux) != 4:
            # Command usage
            text = '> `!send` - Send bot text message to member or channel\n' \
                    '> • Usage: `!send member <member> <text>`' \
                    '> • Usage: `!send channel <channel> <text>`'
            await ctx.author.send(text)
            return

        type, name, text = aux[1:4]
        if type == 'member':
            # Send bot message to member
            member = get(guild.members, name=name)
            if not member:
                text = '> `!send` - Member not found :('
                await ctx.author.send(text)
                return
            await member.send(text)

        elif type == 'channel':
            # Send bot message to channel
            channel = get(guild.channels, name=name)
            if not channel:
                text = '> `!send` - Channel not found :('
                await ctx.author.send(text)
                return
            await channel.send(text)

    @commands.command()
    async def broadcast(self, ctx):
        guild = bot.guilds[0]
        member = get(guild.members, name=ctx.author.name)
        if not member or not member.guild_permissions.administrator:
            # You are not an admin of given guild
            text = '> `!broadcast` - Access denied'
            await member.send(text)
            return

        aux = ctx.message.content.split(maxsplit=2)
        if len(aux) < 3:
            # Command usage
            text = '> `!broadcast` - Send bot PM to all role members\n' \
                    '> • Usage: `!broadcast <role> <text>`'
            await ctx.author.send(text)
            return

        # Send message to everyone on given channel
        name, text = aux[1:3]
        role = get(guild.roles, name=name)
        for member in role.members:
            if not member.bot:
                await member.send(text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Send(bot))
