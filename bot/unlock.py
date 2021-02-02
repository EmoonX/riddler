from discord import Member
from discord.utils import get
import bcrypt

from bot import bot
from riddle import riddles


@bot.ipc.route()
async def unlock(data):
    '''Unlock level when extension user arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''
    
    # Get guild and member object from player's id
    riddle = riddles[data.alias]
    guild = riddle.guild
    member = get(guild.members, id=data.player_id)
    if not member:
        # Not currently a member
        return

    # Get guild member object from player and their current level
    current_level = ''
    for role in member.roles:
        if 'reached-' in role.name:
            aux = role.name.strip('reached-')
            if aux not in riddle.secret_levels:
                current_level = aux
                break
    
    # Find if the path corresponds to a level front page
    id = ''
    for level_id, level_path in \
            {**riddle.levels, **riddle.secret_levels}.items():
        if level_path == data.path:
            id = level_id
            break
    if not id:
        # Not a level front page
        return

    # Get channel and roles corresponding to level
    channel = get(guild.channels, name=id)
    role = None
    if id in riddle.levels:
        name = 'reached-' + current_level
        role = get(channel.changed_roles, name=name)
    else:
        name = 'reached-' + id
        role = get(member.roles, name=name)
        if not role:
            # For secret levels
            name = 'solved-' + id
            role = get(member.roles, name=name)
    if role:
        # User already unlocked that channel
        return

    # If a normal level, remove old "reached" roles from user
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

    # If a normal level, change nickname to current level
    if id in riddle.levels:
        s = '[' + id + ']'
        await update_nickname(member, s)

    # Log unlocking procedure
    print('> [%s] Member %s#%s unlocked channel #%s' \
            % (guild.name, member.name, member.discriminator, id))


@bot.command()
async def finish(ctx):
    # Only allow finishing by PM to bot
    message = ctx.message
    author = message.author
    if message.guild and not message.channel.name == 'command-test':
        # Purge all traces of wrong message >:)
        await message.delete()
        text = '`!finish` must be sent by PM to me!'
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
                # Check if player unlocked final level before trying to finish
                final_level = next(reversed(riddle.levels))
                name = 'reached-%s' % final_level
                final_role = get(member.roles, name=name)
                if not final_role:
                    text = 'You need to `!unlock` the final level first. :)'
                else:
                    # Check if inputted answer matches correct one (by hash)
                    match = bcrypt.checkpw(answer.encode('utf-8'),
                            riddle.final_answer_hash) 

                    if match:
                        # Player completed the game (for now?)
                        text = 'Congrats!'

                        # Swap last level's "reached" role for "winners" role
                        await member.remove_roles(final_role)
                        winners = get(guild.roles, name='winners')
                        await member.add_roles(winners)

                        # Update nickname with winner's badge
                        s = riddle.winner_suffix
                        await update_nickname(member, s)

                    else:
                        # Player got answer "wrong"
                        text = 'Please, go back and finish the final level...'
    
    await message.channel.send(text)


def hash_match(input: str, answer_hash: bytes):
    '''Return if input's hash matches answer's one.'''
    match = bcrypt.checkpw(
            input.encode('utf-8'), answer_hash)
    return match


async def update_nickname(member: Member, s: str):
    '''Update user's nickname to reflect current level.
    In case it exceeds 32 characters, shorten the member's name to fit.'''
    name = member.name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:(-(excess + 5))] + '(...)'
    nick = name + ' ' + s
    await member.edit(nick=nick)
