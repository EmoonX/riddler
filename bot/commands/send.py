from discord.ext import commands
from discord.utils import get


class Send(commands.Cog):
    '''Admin commands to send messages to members or channels.'''

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def send(self, ctx):
        '''Send messages to member or channel.'''

        wonderland = get(self.bot.guilds, id=859797827554770955)
        guild = get(self.bot.guilds, id=987832530826833920)
        member = get(guild.members, name=ctx.author.name)
        if not member or not member.guild_permissions.manage_guild:
            # You are not an admin of given guild
            if member:
                text = '> `!send` - Access denied'
                await member.send(text)
            return

        aux = ctx.message.content.split(maxsplit=3)
        if len(aux) != 4:
            # Command usage
            text = (
                '> `!send` - Send bot text message to member or channel\n'
                '> • Usage: `!send member <member> <text>`\n'
                '> • Usage: `!send channel <channel> <text>`'
            )
            await ctx.author.send(text)
            return

        type, name, text = aux[1:4]
        if type == 'member':
            # Send bot message to member
            member = (
                get(wonderland.members, name=name) or
                get(guild.members, name=name)
            )
            if not member:
                text = '> `!send` - Member not found :('
                await ctx.author.send(text)
                return
            await member.send(text)

        elif type == 'channel':
            # Send bot message to channel
            channel = (
                get(wonderland.channels, name=name) or
                get(guild.channels, name=name)
            )
            if not channel:
                text = '> `!send` - Channel not found :('
                await ctx.author.send(text)
                return
            await channel.send(text)

    @commands.command()
    async def broadcast(self, ctx):
        '''Send messages to all given role members.'''

        guild = self.bot.guilds[0]
        member = get(guild.members, name=ctx.author.name)
        if not member or not member.guild_permissions.administrator:
            # You are not an admin of given guild
            text = '> `!broadcast` - Access denied'
            await member.send(text)
            return

        aux = ctx.message.content.split(maxsplit=2)
        if len(aux) < 3:
            # Command usage
            text = (
                '> `!broadcast` - Send bot PM to all role members\n'
                '> • Usage: `!broadcast <role> <text>`'
            )
            await ctx.author.send(text)
            return

        # Send message to everyone on given channel
        name, text = aux[1:3]
        role = get(guild.roles, name=name)
        for member in role.members:
            if not member.bot:
                await member.send(text)


async def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    await bot.add_cog(Send(bot))
