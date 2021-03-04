from discord import Guild, Member
from discord.utils import get


class UnlockHandler:
    '''Handler for processing guild unlocking procedures
    (granting roles, congratulating player, finishing the game, etc).'''

    guild: Guild
    '''Guild where things will be unlocked'''
    
    levels: dict
    '''Dict of normal riddle levels'''

    member: Member
    '''Discord guild member, the one that is unlocking'''

    def __init__(self, guild: Guild, levels: dict, member: Member):
        '''Build handler.'''
        self.guild = guild
        self.levels = levels
        self.member = member

    async def beat(self, level: dict, points: int):
        '''Send congratulations message upon level completion.'''
        print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has beaten level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                   self.member.discriminator, level['name']))
        text = '**[%s]** You solved level **%s** and won **%d** points!\n' \
                % (self.guild.name, level['name'], points)
        await self.member.send(text)

    async def advance(self, level: dict):
        '''Advance to further level when player arrives at a level front page.
        "reached" role is granted to user and thus given access to channel(s).'''

        # Remove old "reached" role from user
        name = level['discord_name']
        if not name:
            name = level['name']
        for role in self.member.roles:
            if 'reached-' in role.name:
                old_level = role.name.replace('reached-', '')
                if old_level in self.levels:
                    await self.member.remove_roles(role)
                    break

        # Add "reached" role to member
        role = get(self.guild.roles, name=('reached-%s' % name))
        await self.member.add_roles(role)

        # Change nickname to current level
        s = '[%s]' % level['name']
        await update_nickname(self.member, s)

    async def secret_found(self, level: dict):
        '''Grant access to secret channel.'''
        
        # Grant "reached" role
        name = level['discord_name']
        if not name:
            name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % name))
        await self.member.add_roles(reached)
        
        # Log reaching secret and send message to member
        print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has found secret level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                    self.member.discriminator, level['name']))
        text = '**[%s]** You found secret level **%s**. Congratulations!' \
                % (self.guild.name, level['name'])
        await self.member.send(text)

    async def secret_solve(self, level: dict, points: int):
        '''Solve secret level and grant special colored role.'''
        
        # Get roles from guild
        name = level['discord_name']
        if not name:
            name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % name))
        solved = get(self.guild.roles, name=('solved-%s' % name))
        
        # Remove old "reached" role and add "solved" role to member
        await self.member.remove_roles(reached)
        await self.member.add_roles(solved)

        # Log solving procedure and send message to member
        print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has completed secret level \033[1m%s\033[0m') 
                % (self.guild.name, self.member.name,
                    self.member.discriminator, level['name']))
        text = ('**[%s]** You successfully solved secret level **%s** '
                'and won **%d** points!\n') \
                % (self.guild.name, level['name'], points)
        await self.member.send(text)    

    async def cheevo_found(self, cheevo: dict, points: int):
        '''Congratulations upon achievement being found.'''
        print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                    'got cheevo \033[1m%s\033[0m!') %
                    (self.guild.name, self.member.name,
                        self.member.discriminator, cheevo['title']))
        text = ('**[%s]** You\'ve found achievement **_%s_** '
                'and won **%d** points!\n') \
                % (self.guild.name, cheevo['title'], points)
        await self.member.send(text)

    async def game_completed(self):
        '''Do the honors upon user completing game.'''

        # Remove last level's "reached" role
        for role in self.member.roles:
            name = role.name.replace('reached-', '')
            if name in self.levels:
                await self.member.remove_roles(role)
                break

        # Add flashy "winners" role
        # winners = get(self.guild.roles, name='winners')
        winners = get(self.guild.roles, name='reached-level-0')
        await self.member.add_roles(winners)

        # Update nickname with winner's badge
        await update_nickname(self.member, '💎')

        # Player has completed the game (for now?)
        print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m ' \
                'has finished the game!') \
                % (self.guild.name,
                    self.member.name, self.member.discriminator))
        text = '**[%s]** You just completed the game! **Congrats!**' \
                % self.guild.name
        await self.member.send(text)


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


def setup(_):
    pass
