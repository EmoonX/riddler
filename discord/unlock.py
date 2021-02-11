from discord import Member
from discord.utils import get
import bcrypt

from bot import bot
from riddle import Riddle, riddles
from util.db import database


@bot.ipc.route()
async def unlock(data):
    '''Unlock channels and/or roles in case path corresponds
    to a level front page or secret answer.'''

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
    
    # Iterate "normal" levels
    for level in riddle.levels.values():
        if level['is_secret']:
            continue
        if data.points and level['answer'] == data.path:
            # If path corresponds to a level answer, level is beaten
            await _beat(riddle, member, level, current_level, data.points)
            current_level = level['name']
        elif level['path'] == data.path:
            # If path corresponds to a level front page, advance to next one
            await _advance(riddle, member, level, current_level)

    # Iterate secret levels
    for level in riddle.secret_levels.values():
        if not level['is_secret']:
            continue
        if level['path'] == data.path:
            await _secret_found(riddle, member, level)
            return
        elif level['answer'] == data.path:
            await _secret_solve(riddle, member, level)


async def _beat(riddle: Riddle, member: Member,
        level: dict, current_level: str, points: int):
    '''Send congratulations message upon level completion.'''
    
    # Avoid backtracking if level has already been beaten
    ok = False
    for level in riddle.levels:
        if level == current_level:
            ok = True
        elif level == level['name']:
            if not ok:
                return
            else:
                break
    
    # Log beating and send message to member
    guild = riddle.guild
    id = level['discord_name']
    print('> [%s] %s#%s has beaten level #%s' \
            % (guild.name, member.name, member.discriminator, id))
    text = ('**[%s]** You solved level **%s** ' % (guild.name, id)) \
            + ('and won **%d** points!\n' % points)
    await member.send(text)


async def _advance(riddle: Riddle, member: Member,
        level: dict, current_level: str):
    '''Advance to further level when player arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''

    # Avoid backtracking if level has already been unlocked
    if current_level != '':
        ok = False
        for level in riddle.levels:
            if level == current_level:
                ok = True
            elif level == level['name']:
                if not ok:
                    return
                else:
                    break

    # Get channel and roles corresponding to level
    guild = riddle.guild
    id = level['discord_name']
    channel = get(guild.channels, name=id)
    name = 'reached-' + current_level
    role = get(channel.changed_roles, name=name)
    if role:
        # User already unlocked that channel
        return

    # Remove old "reached" roles from user
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
    if level['name'] in riddle.levels:
        s = '[%s]' % level['name']
        await update_nickname(member, s)


async def _secret_found(riddle: Riddle, member: Member, level: dict):
    '''Send congratulations message upon secret found.'''
    
    # Do nothing if secret has already been found or beaten
    guild = riddle.guild
    id = level['discord_name']
    print(id)
    reached = get(guild.roles, name=('reached-%s' % id))
    solved = get(guild.roles, name=('solved-%s' % id))
    if reached in member.roles or solved in member.roles:
        return
    
    # Grant "reached" role
    await member.add_roles(reached)
    
    # Log reaching secret and send message to member
    print('> [%s] %s#%s has found secret level #%s' \
            % (guild.name, member.name, member.discriminator, level['name']))
    text = '**[%s]** You found secret level **%s**. Congratulations!' \
            % (guild.name, level['name'])
    await member.send(text)


async def _secret_solve(riddle: Riddle, member: Member, level: dict):
    '''Advance to further level when player arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''
    print('OOPS')
    return

    # Get channel and roles corresponding to level
    guild = riddle.guild
    id = level['discord_name']
    channel = get(guild.channels, name=id)
    role = None
    if id in riddle.levels:
        name = 'reached-' + current_level
        role = get(channel.changed_roles, name=name)
    elif id in riddle.secret_levels:
        name = 'reached-' + id
        role = get(member.roles, name=name)
        if not role:
            # For secret levels, solved implies reached too
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


async def solve(riddle: Riddle, member: Member, level: dict):
    '''Grant "solved" role upon completion of a level (like a secret one).'''

    # Check if member already solved level
    guild = riddle.guild
    id = level['level_id']
    name = 'solved-' + id
    solved = get(guild.roles, name=name)
    if solved in member.roles:
        return

    # Deny solve if member didn't arrive at the level proper yet
    name = 'reached-' + id
    reached = get(member.roles, name=name)
    if not reached:
        print('> [%s] [WARNING] %s#%s tried to solve ' \
                'secret level "%s" without reaching it' \
                % (guild.name, member.name, member.discriminator, id))
        return
    
    # Remove old "reached" role and add "solved" role to member
    await member.remove_roles(reached)
    await member.add_roles(solved)

    # Log solving procedure and send message to member
    print('> [%s] %s#%s completed secret level "%s"' \
            % (guild.name, member.name, member.discriminator, id))
    text = '**[%s]** You successfully solved secret level **%s**!\n' \
            % (guild.name, id)
    await member.send(text)


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
