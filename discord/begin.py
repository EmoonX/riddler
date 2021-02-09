from discord.utils import get
import bcrypt

from bot import bot
from util.db import database


@bot.command()
async def begin(ctx):
    if ctx.message.guild:
        # Purge all traces of wrong message >:)
        author = ctx.message.author
        await ctx.message.delete()
        text = '> `!begin` must be sent by DM to me!'
        await author.send(text)
        return
    
    # Build list of guilds of which caller is admin
    user = ctx.message.author
    guilds = []
    for guild in bot.guilds:
        member = get(guild.members, id=user.id)
        if member and member.guild_permissions.administrator:
            guilds.append(guild)
    
    aux = ctx.message.content.split()
    text = ''
    if len(aux) == 1:
        text += 'Hello! We\'re going to begin setting up an online riddle guild.\n\n'

        text += 'These are the available guilds of which you are the admin ' \
                    '(not sure which ones are related to riddles, though!):\n```'
        for i, guild in enumerate(guilds):
            text += '%d) %s\n' % (i, guild.name)
        text += '```\n'

        text += 'First of all, you need a guild account to access the ' \
                'administration web interface, exclusive to admins.\n'
        text += 'Send me the following formatted command:\n'
        text += '```!begin guild_index guild_alias password```'
        text += 'Where:\n' \
                '    **guild_index**: the guild number in the list just above\n' \
                '    **guild_alias**: the new short alias of your guild\n' \
                '    **password**: a strong password to log in the web interface\n\n'
        
        text += 'Once you\'re really sure about the info, send me! I\'ll be waiting.'
    
    elif len(aux) == 4:
        # Get arguments from command message
        index, alias, password = aux[1:]
        guild = guilds[int(index)]

        # Generate hash (with salt) from plain text password
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        # Create guild account and register it on database
        query = 'INSERT INTO guilds VALUES (:alias, :password_hash, :id, "", "")'
        values = {'alias': alias, 'password_hash': pw_hash, 'id': guild.id}
        await database.execute(query, values)

        # Create entry on general_info table
        query = 'INSERT INTO general_info (riddle) VALUES (:riddle)'
        await database.execute(query, {'riddle': alias})

        text += 'Guild successfully registered!'

    await ctx.message.author.send(text)
