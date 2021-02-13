from discord import Guild, Member
from discord.utils import get

from bot import bot


class UnlockHandler:
    '''Handler for processing guild unlocking procedures
    (granting roles, congratulating player, finishing the game, etc).'''

    guild: Guild
    '''Guild where things will be unlocked'''

    member: Member
    '''Discord guild member, the one that is unlocking'''


    def __init__(self, guild: Guild, member: Member):
        '''Build handler with guild and member.'''
        self.guild = guild
        self.member = member

    async def beat(self, level: dict, points: int):
        '''Send congratulations message upon level completion.'''
        print(('> \033[1m[%s]\033[0m \033[1m[%s#%s]\033[0m '
                'has beaten level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                   self.member.discriminator, level['name']))
        text = '**[%s]** You solved level **%s** and won **%d** points!\n' \
                % (self.guild.name, level['name'], points)
        await self.member.send(text)


async def _advance(riddle: str, member: Member,
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


async def _secret_found(riddle: str, member: Member, level: dict):
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


async def _secret_solve(riddle: str, member: Member,
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
            break

    # Add flashy "winners" role
    winners = get(guild.roles, name='winners')
    await member.add_roles(winners)

    # Update nickname with winner's badge
    await update_nickname(member, '🏅')

    # Player has completed the game (for now?)
    print(('> \033[1m[%s]\033[0m \033[1m%s\033[0m#%\033[1m%s\033[0m ' \
            'has finished the game!') \
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
