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
            aux = role.name.replace('reached-', '')
            if aux in riddle.levels:
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
            await _secret_solve(riddle, member, level, data.points)


async def _beat(riddle: Riddle, member: Member,
        level: dict, current_level: str, points: int):
    '''Send congratulations message upon level completion.'''
    
    # Avoid backtracking if level has already been beaten
    ok = False
    for lev in riddle.levels:
        if lev == current_level:
            ok = True
        elif lev == level['name']:
            if not ok:
                return
            else:
                break
    
    # Log beating and send message to member
    guild = riddle.guild
    print('> \033[1m[%s]\033[0m %s#%s has beaten level \033[1m%s\033[0m' \
            % (guild.name, member.name, member.discriminator, level['name']))
    text = ('**[%s]** You solved level **%s** ' % (guild.name, level['name'])) \
            + ('and won **%d** points!\n' % points)
    await member.send(text)


async def _advance(riddle: Riddle, member: Member,
        level: dict, current_level: str):
    '''Advance to further level when player arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''

    # Avoid backtracking if level has already been unlocked
    if current_level != '':
        ok = False
        for lev in riddle.levels:
            if lev == current_level:
                ok = True
            elif lev == level['name']:
                if not ok:
                    return
                else:
                    break

    # Get channel and roles corresponding to level
    guild = riddle.guild
    id = level['name']
    channel = get(guild.channels, name=id)
    name = 'reached-' + id
    role = get(member.roles, name=name)
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
    reached = get(guild.roles, name=('reached-%s' % id))
    solved = get(guild.roles, name=('solved-%s' % id))
    if reached in member.roles or solved in member.roles:
        return
    
    # Grant "reached" role
    await member.add_roles(reached)
    
    # Log reaching secret and send message to member
    print('> \033[1m[%s]\033[0m %s#%s has found secret level \033[1m%s\033[0m' \
            % (guild.name, member.name, member.discriminator, level['name']))
    text = '**[%s]** You found secret level **%s**. Congratulations!' \
            % (guild.name, level['name'])
    await member.send(text)


async def _secret_solve(riddle: Riddle, member: Member,
        level: dict, points: int):
    '''Advance to further level when player arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''
    
    # Check if user has already solved secret
    guild = riddle.guild
    id = level['discord_name']
    solved = get(guild.roles, name=('solved-%s' % id))
    if solved in member.roles:
        return

    # Deny solve if member didn't arrive at the level proper yet
    name = 'reached-' + id
    reached = get(member.roles, name=name)
    if not reached:
        print('> [%s] [WARNING] %s#%s tried to solve ' \
                'secret level <%s> without reaching it' \
                % (guild.name, member.name, member.discriminator,
                    level['name']))
        return
    
    # Remove old "reached" role and add "solved" role to member
    await member.remove_roles(reached)
    await member.add_roles(solved)

    # Log solving procedure and send message to member
    print('> \033[1m[%s]\033[0m %s#%s has completed secret level \033[1m%s\033[0m' \
            % (guild.name, member.name, member.discriminator, level['name']))
    text = ('**[%s]** You successfully solved secret level ' % guild.name) + \
            ('**%s** and won **%d** points!\n' % (level['name'], points))
    await member.send(text)    


@bot.ipc.route()
async def cheevo_found(data):
    '''Congratulating procedures upon achievement being found.'''

    # Get data from request
    riddle = riddles[data.alias]
    guild = riddle.guild
    member = get(guild.members,
            name=data.name, discriminator=data.disc)
    title = data.cheevo['title']
    points = data.cheevo['points']

    print('> \033[1m[%s]\033[0m %s#%s has found achievement \033[1m%s\033[0m' \
            % (guild.name, member.name, member.discriminator, title))
    text = '**[%s]** You found **_%s_** achievement ' % (guild.name, title) + \
            'and won **%d** points!\n' % (points)
    await member.send(text)


@bot.ipc.route()
async def game_completed(data):
    '''Congratulating and guild procedures upon game being completed.'''

    # Get member object
    riddle = riddles[data.alias]
    guild = riddle.guild
    member = get(guild.members,
            name=data.name, discriminator=data.disc)

    # Remove last level's "reached" role
    for role in member.roles:
        name = role.name.replace('reached-', '')
        if name in riddle.levels:
            await member.remove_roles(role)
            return

    # Add flashy "winners" role
    winners = get(guild.roles, name='winners')
    await member.add_roles(winners)

    # Update nickname with winner's badge
    await update_nickname(member, '🏅')

    # Player has completed the game (for now?)
    print('> \033[1m[%s]\033[0m %s#%s has finished the game!' \
            % (guild.name, member.name, member.discriminator))
    text = '**[%s]** You just completed the game! **Congrats!**' % guild.name
    await member.send(text)


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
