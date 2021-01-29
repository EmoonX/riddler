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

    aux = message.content.split(maxsplit=2)[1:]
    text = ''
    if len(aux) in (0, 1):
        # Command usage
        text = '> `!unlock`: unlock level channels (PM ONLY!)\n' \
                '> \n' \
                '> • Usage: `!unlock guild_alias level_id filename`\n' \
                '> `guild_alias`: the alias of the riddle\'s guild/server\n' \
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
        
        if len(aux) == 0:
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
        
        elif len(aux) == 1:
            alias = aux[0]
            if not alias in riddles:
                # Wrong alias
                text = 'Inserted alias doesn\'t match any valid guild!\n'
            else:
                guild = riddles[alias].guild
                member = get(guild.members, id=author.id)
                if not member:
                    # Not a member
                    text = 'You aren\'t currently a member ' \
                            'of the _%s_ guild.\n' % guild.name

            
        await author.send(text)
        return

    # Get command arguments
    guild, level_id, filename = aux

    # Get guild member object from message author and their current level
    guild = bot.guilds[0]
    member = get(guild.members, name=message.author.name)
    current_level = '01'
    for role in member.roles:
        if role.name == 'winners':
            current_level = 'winners'
            break
        elif 'reached-' in role.name:
            aux = role.name.strip('reached-')
            if aux not in secret_levels:
                current_level = aux
                break

    if not id in levels and not id in secret_levels:
        # User entered a wrong level ID
        text = '> Level ID **' + id + '** not found!\n' \
                '> Try `!unlock help` for command usage'
    else:
        channel = get(guild.channels, name=id)
        role = None
        if id in levels:
            name = ('reached-' + current_level) \
                    if current_level != 'winners' else 'winners'
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
            text = '> Channel #**' + id + '** is already unlocked!\n' \
            '> Try `!unlock help` for command usage'

        elif (id in levels and levels[id] != filename) \
                or (id in secret_levels and secret_levels[id] != filename):
            # User entered a wrong filename
            text = '> Wrong filename/answer for ID **' + id + '**!\n' \
            '> Try `!unlock help` for command usage'

    if text:
        # In case of anything wrong, just show message and return
        await message.author.send(text)
        return

    # In case of normal levels, remove old "reached" roles from user
    if id in levels:
        for role in member.roles:
            if 'reached-' in role.name:
                old_level = role.name.strip('reached-')
                if old_level in levels:
                    await member.remove_roles(role)
                    break

    # Add "reached" role to member
    name = 'reached-' + id
    if id == 'winners':
        name = 'winners'
    role = get(guild.roles, name=name)
    await member.add_roles(role)

    # Change nickname to current level
    if id in levels:
        s = '[' + id + ']'
        if id == 'winners':
            s = '🏅'
        await update_nickname(member, s)

    # Send confirmation message
    print('Member ' + member.name +  ' unlocked channel #'  + id)
    text = '> You successfuly unlocked channel #**' + id + '**!'
    if id in levels:
        text += '\n> Your nickname is now **' + member.nick + '**'
    else:
        text += '\n> Your nickname is unchanged'
    await message.author.send(text)

    if id in levels and level_order.index(id) > level_order.index('50'):
        # [CIPHER ONLY] Unlock free-of-the-labyrinth role (and color)
        free_role = get(guild.roles, name='free-from-the-labyrinth')
        await member.add_roles(free_role)

    # Achievement text on first to reach
    # if id != 'winners':
    #     first_to_reach = (len(role.members) == 1)
    #     if first_to_reach:
    #         text = '> **🏅 FIRST TO REACH 🏅**\n'
    #         text += '> **<@!%d> has arrived at level _%s_. ' \
    #                 'Congratulations!**' % (member.id, id)
    #         channel = get(guild.channels, name='achievements')
    #         await channel.send(text)