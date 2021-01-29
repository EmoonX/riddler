from discord import Member
from discord.utils import get

from bot import bot
from riddle import riddles


@bot.command()
async def unlock(ctx):
    '''Unlock level by means of correct input corresponding to level filename.
    "reached" role is granted to user and thus given access to channel(s).'''

    # Only allow unlocking by PM to bot
    message = ctx.message
    author = message.author
    if message.guild:
        # Purge all traces of wrong message >:)
        await message.delete()
        text = '> `!unlock` must be sent by PM to me!'
        await author.send(text)
        return

    aux = message.content.split()[1:]
    text = ''
    if len(aux) != 3:
        # Command usage
        text = '> `!unlock`: unlock level channels (PM ONLY!)\n' \
                '> \n' \
                '> • Usage: `!unlock guild_alias level_id filename`\n' \
                '> `guild_alias`: the alias of riddle\'s guild/server\n' \
                '> `level_id`: an identifier representing current level\n' \
                '> `filename`: the last part of the URL of the level' \
                    ' frontpage, minus extensions (like .htm) or slashes' \
                    ' (exception goes for the #winners channel, which needs' \
                    ' instead the final level\'s answer as the word)\n' \
                '> \n' \
                '> • In case of normal levels, choosing a further level' \
                    ' will unlock all sequential channels before it.' \
                    ' In addition, your nickname will also be changed to the' \
                    ' form _username [XY]_, where XY is the level ID\n' \
                '> \n'
        
    if len(aux) not in (1, 3):
        # Display guild list (aliases and names)
        text += '> • Certified riddle guild aliases ' \
                '(**bold** indicates guilds you are in):\n'
        for (alias, riddle) in riddles.items():
            guild = riddle.guild
            member = get(guild.members, id=author.id)
            if member:
                text += '> **%s** (_%s_)\n' % (alias, guild.name)
            else:
                text += '> ~~%s~~ (_%s_)\n' % (alias, guild.name)
        text += '> \n'
        text += '> (to see a specific guild\'s level list, ' \
                'try just `!unlock guild_alias`)'
        await author.send(text)
        return
    
    alias = aux[0]
    if len(aux) == 1 and not alias in riddles:
        # Invalid alias
        text = 'Inserted alias doesn\'t match any valid guild!\n'
        await author.send(text)
        return

    riddle = riddles[alias]
    guild = riddle.guild
    member = get(guild.members, id=author.id)
    if len(aux) == 1:
        if not member:
            # Not currently a member
            text = 'You aren\'t currently a member ' \
                    'of the _%s_ guild.\n' % guild.name
        else:
            text += '> • Valid level IDs for %s: **' % guild.name \
                    + ' '.join(level for level in riddle.levels) + '**\n'
            # text += '> • Secret level IDs: **' \
            #         + ' '.join(id for id in secret_levels.keys())
            text += '\n'
        await author.send(text)
        return

    # Get remaining command arguments
    id, filename = aux[1:]

    # Get guild member object from message author and their current level
    current_level = '01'
    for role in member.roles:
        if 'reached-' in role.name:
            aux = role.name.strip('reached-')
            if aux not in riddle.secret_levels:
                current_level = aux
                break

    if not (id in riddle.levels or id in riddle.secret_levels):
        # User entered a wrong level ID
        text = 'Level ID **%s** not found!' % id
    else:
        channel = get(guild.channels, name=id)
        role = None
        if id in riddle.levels:
            name = 'reached-' + current_level
            role = get(channel.changed_roles, name=name)
        else:
            name = 'reached-' + id
            role = get(member.roles, name=name)
            if not role:
                # For secret ones
                name = 'solved-' + id
                role = get(member.roles, name=name)
        if role:
            # User already unlocked that channel
            text = 'Channel #**%s** is already unlocked!' % id
        elif (id in riddle.levels \
                    and filename != riddle.levels[id]) \
                or (id in riddle.secret_levels \
                    and filename != riddle.secret_levels[id]):
            # User entered a wrong filename
            text = 'Wrong filename/answer for ID **%s**!' % id

    if text:
        # In case of anything wrong, just show message and return
        await author.send(text)
        return

    # In case of normal levels, remove old "reached" roles from user
    if id in riddle.levels:
        for role in member.roles:
            if 'reached-' in role.name:
                old_level = role.name.strip('reached-')
                if old_level in riddle.levels:
                    await member.remove_roles(role)
                    break

    # Add "reached" role to member
    name = 'reached-' + id
    role = get(guild.roles, name=name)
    await member.add_roles(role)

    # Change nickname to current level
    if id in riddle.levels:
        s = '[' + id + ']'
        await update_nickname(member, s)

    # Send confirmation message
    print('> [%s] Member %s#%s unlocked channel #%s' \
            % (guild.name, member.name, member.discriminator, id))
    text = 'You successfuly unlocked channel #**%s**!' % id
    if id in riddle.levels:
        text += '\nYour nickname is now **%s**' % member.nick
    await message.author.send(text)

    # Achievement text on first to reach
    # if id != 'winners':
    #     first_to_reach = (len(role.members) == 1)
    #     if first_to_reach:
    #         text = '> **🏅 FIRST TO REACH 🏅**\n'
    #         text += '> **<@!%d> has arrived at level _%s_. ' \
    #                 'Congratulations!**' % (member.id, id)
    #         channel = get(guild.channels, name='achievements')
    #         await channel.send(text)


@bot.command()
async def finish(ctx):
    # Only allow finishing by PM to bot
    message = ctx.message
    author = message.author
    if message.guild:
        # Purge all traces of wrong message >:)
        await message.delete()
        text = '> `!finish` must be sent by PM to me!'
        await author.send(text)
        return

    aux = message.content.split()[1:]
    text = ''
    if len(aux) != 2:
        # Command usage
        text = '> `!finish`: Finish game ||(for now?)|| (PM ONLY!)\n' \
                '> \n' \
                '> • Usage: `!finish guild_alias final_answer`\n' \
                '> `guild_alias`: the alias of riddle\'s guild/server\n' \
                '> `final_answer`: the final level\'s answer\n'
    else:
        alias, answer = aux
        if not alias in riddles:
            # Invalid alias
            text = 'Inserted alias doesn\'t match any valid guild!\n'
        else:
            riddle = riddles[alias]
            guild = riddle.guild
            member = get(guild.members, id=author.id)
            if not member:
                # Not currently a member
                text = 'You aren\'t currently a member ' \
                        'of the _%s_ guild.\n' % guild.name
            else :
                if answer == 'rasputin':
                    # Player completed the game (for now?)
                    text = 'Congrats!'
                else:
                    # Player got answer wrong
                    text = 'Please, go back and finish the final level...'
    
    await author.send(text)


async def update_nickname(member: Member, s: str):
    '''Update user's nickname to reflect current level.
    In case it exceeds 32 characters, shorten the member's name to fit.'''
    name = member.name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:-(excess + 5)] + '(...)'
    nick = name + ' ' + s
    await member.edit(nick=nick)
