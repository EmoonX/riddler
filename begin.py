from discord.utils import get
from discord.ext import commands

from bot import bot


# --------------------------------------------------------------------------- #


@bot.command()
async def begin(ctx):
    if ctx.message.guild:
        # Purge all traces of wrong message >:)
        author = ctx.message.author
        await ctx.message.delete()
        text = '> `!begin` must be sent by DM to me!'
        await author.send(text)
        return
    
    text = 'Hello! We\'re going to begin building an online riddle game guild.'
    await ctx.message.author.send(text)

    # Build list of guilds of which caller is admin
    user = ctx.message.author
    guilds = []
    for guild in bot.guilds:
        member = get(guild.members, id=user.id)
        if member.guild_permissions.administrator:
            guilds.append(guild)

    text = 'These are the available guilds of which you are the admin:\n```'
    for i, guild in enumerate(guilds):
        text += '%d) %s\n' % (i, guild.name)
    text += '```'
    await ctx.message.author.send(text)
