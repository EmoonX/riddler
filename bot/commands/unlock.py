import logging

from discord import Guild, Member, File
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

    async def beat(self, level: dict, points: int,
            first_to_solve: bool, milestone: str):
        '''Procedures upon player having beaten a level.'''
        
        # Send congratulatory message
        n = 'DCBAS'.find(level['rank']) + 1
        stars = '★' * n
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has beaten level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                self.member.discriminator, level['name']))
        text = ('**[%s]** You have solved level **%s** (%s) ' \
                    'and won **%d** points!\n') \
                % (self.guild.name, level['name'], stars, points)
        await self.member.send(text)
        
        # Send also to channels if first to solve level
        if first_to_solve:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
            text += ('**<@!%d>** has completed level **%s**! ' \
                    'Congratulations!') % (self.member.id, level['name'])
            channel = get(self.guild.channels, name=level['discord_name'])
            await channel.send(text)
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await achievements.send(text)
        
        # Add special milestone role if one was reached
        if milestone:
            role = get(self.guild.roles, name=milestone)
            await self.member.add_roles(role)
            text = '**[%s] 🗿 MILESTONE REACHED 🗿**\n' % self.guild.name
            text += 'You have unlocked special role **@%s**!' % milestone
            await self.member.send(text)
            
            # Congratulate milestone reached on respective channel
            channel = get(self.guild.channels, name=level['discord_name'])
            text = ('**<@!%d>** has beaten level **%s** ' \
                        'and is now part of **@%s**! Congratulations!') \
                    % (self.member.id, level['name'], role.name)
            await channel.send(text)

    async def advance(self, level: dict):
        '''Advance to further level when player arrives at a level front page.
        "reached" role is granted to user and thus given access to channel(s).'''

        # Remove old "reached" role from user
        for role in self.member.roles:
            if not 'reached-' in role.name:
                continue
            old_name = role.name.replace('reached-', '')
            old_level = None
            for other in self.levels.values():
                if other['discord_name'] == old_name:
                    old_level = other
                    break
            if old_level:
                await self.member.remove_roles(role)

        # Add "reached" role to member
        name = level['discord_name']
        if not name:
            name = level['name']
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
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has found secret level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                    self.member.discriminator, level['name']))
        text = '**[%s]** You have found secret level **%s**. Congratulations!' \
                % (self.guild.name, level['name'])
        await self.member.send(text)

    async def secret_solve(self, level: dict, points: int,
            first_to_solve=False):
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
        n = 'DCBAS'.find(level['rank']) + 1
        stars = '★' * n
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has completed secret level \033[1m%s\033[0m') 
                % (self.guild.name, self.member.name,
                    self.member.discriminator, level['name']))
        text = ('**[%s]** You have solved secret level **%s** (%s) ' \
                    'and won **%d** points!\n') \
                % (self.guild.name, level['name'], stars, points)
        await self.member.send(text)
        
        # Send congratulations message to channel (and cheevos one) :)
        channel = get(self.guild.channels, name=name)
        text = ''
        if first_to_solve:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
        text += ('**<@!%d>** has completed secret level **%s**! ' \
                'Congratulations!') % (self.member.id, level['name'])
        await channel.send(text)
        if first_to_solve:
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await achievements.send(text)

    async def cheevo_found(self, cheevo: dict, points: int):
        '''Congratulations upon achievement being found.'''
        
        # Log and send congratulatory message
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'got cheevo \033[1m%s\033[0m!') %
                (self.guild.name, self.member.name,
                    self.member.discriminator, cheevo['title']))
        text = ('**[%s]** You have found achievement **_%s_** '
                'and won **%d** points!\n') \
                % (self.guild.name, cheevo['title'], points)
        await self.member.send(text)
        
        # Get cheevo thumb image from path
        image_path = '../web/static/cheevos/%s/%s' \
                % (cheevo['riddle'], cheevo['image'])
        with open(image_path, 'rb') as fp:
            # Create image object
            image = File(fp, cheevo['image'])
            
            # send flavor message with description and image
            description = '_"%s"_' % cheevo['description']
            await self.member.send(description, file=image)

    async def game_completed(self, winners_role: str):
        '''Do the honors upon user completing game.'''

        # Remove last level's "reached" role
        for role in self.member.roles:
            if not 'reached-' in role.name:
                continue
            old_name = role.name.replace('reached-', '')
            old_level = None
            for level in self.levels.values():
                if level['discord_name'] == old_name:
                    old_level = level
                    break
            if old_level:
                await self.member.remove_roles(role)
                break

        # Add flashy "winners" role
        winners = get(self.guild.roles, name=winners_role)
        await self.member.add_roles(winners)

        # Update nickname with winner's badge
        await update_nickname(self.member, '💎')

        # Player has completed the game (for now?)
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m ' \
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
    try:
        await member.edit(nick=nick)
    except:
        pass


def setup(_):
    pass
