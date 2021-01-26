from discord.utils import get
from discord.ext import commands

from bot import bot


@bot.command()
async def begin(ctx):
    if ctx.message.guild:
        # Purge all traces of wrong message >:)
        author = ctx.message.author
        await ctx.message.delete()
        text = '> `!begin` must be sent by DM to me!'
        await author.send(text)
        return
    
    text = 'Hello! We\'re going to begin setting up an online riddle guild.\n\n'
    # Build list of guilds of which caller is admin
    user = ctx.message.author
    guilds = []
    for guild in bot.guilds:
        member = get(guild.members, id=user.id)
        if member.guild_permissions.administrator:
            guilds.append(guild)

    text += 'These are the available guilds of which you are the admin ' \
                '(not sure which ones are related to riddles, though!):\n```'
    for i, guild in enumerate(guilds):
        text += '%d) %s\n' % (i, guild.name)
    text += '```\n'

    text += 'First of all, you need a guild account to access the ' \
            'administration web interface, exclusive to you.\n'
    text += 'Send me the following formatted command:\n'
    text += '```!begin guild_number guild_alias password```'
    text += 'Where:\n' \
            '    **guild_number**: the guild number in the list just above\n' \
            '    **guild_alias**: the new short alias of your guild\n' \
            '    **password**: a strong password to log in the web interface\n\n'
    
    text += 'Once you\'re really sure about the info, send me! I\'ll be waiting.'
    await ctx.message.author.send(text)
