import logging

from discord import Guild, Member, File
from discord.utils import get
from discord.errors import Forbidden

from riddle import riddles, get_ancestor_levels
from util.db import database


class UnlockHandler:
    '''Handler for processing guild unlocking procedures
    (granting roles, congratulating player, finishing the game, etc).'''

    alias: str
    '''Unique identifier for riddle'''

    guild: Guild
    '''Guild where things will be unlocked'''
    
    levels: dict
    '''Dict of normal riddle levels'''

    member: Member
    '''Discord guild member, the one to unlock things for'''

    def __init__(self, alias: str, username: str, disc: str):
        '''Build handler for guild `alias` and member `username#disc`.'''
        self.alias = alias
        riddle = riddles[alias]
        self.guild = riddle.guild
        self.levels = riddle.levels
        self.member = get(riddle.guild.members,
                name=username, discriminator=disc)
    
    async def _send(self, text: str):
        '''Try to send a message to member.
        If they don't accept DMs from bot, ignore.'''
        try:
            await self.member.send(text)
        except Forbidden:
            logging.info(('\033[1m[%s]\033[0m ' \
                    'Can\'t send messages  to \033[1m%s#%s\033[0m ')
                    % (self.guild.name, self.member.name,
                        self.member.discriminator))

    async def beat(self, level: dict, points: int,
            first_to_solve: bool, milestone: str):
        '''Procedures upon player having beaten a level.'''
        
        # Check if Riddler DMs are silenced by player 
        query = 'SELECT * FROM accounts ' \
                'WHERE username = :username AND discriminator = :disc'
        values = {'username': self.member.name,
                'disc': self.member.discriminator}
        result = await database.fetch_one(query, values)
        silent = result['silence_notifs']

        # Send congratulatory message
        n = 'DCBAS'.find(level['rank']) + 1
        stars = '★' * n
        name = level['name']
        if level['latin_name']:
            name += ' (%s)' % level['latin_name']
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has beaten level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                    self.member.discriminator, name))
        if not silent:
            text = ('**[%s]** You have solved level **%s** [%s] ' \
                        'and won **%d** points!\n') \
                    % (self.guild.name, name, stars, points)
            await self._send(text)
        
        # Send also to channels if first to solve level
        if first_to_solve and not silent:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
            text += ('**<@!%d>** has completed level **%s**! ' \
                    'Congratulations!') % (self.member.id, name)
            channel = get(self.guild.channels, name=level['discord_name'])
            await channel.send(text)
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await achievements.send(text)
        
        # Add special milestone role if one was reached
        if milestone:
            role = get(self.guild.roles, name=milestone)
            await self.member.add_roles(role)
            if not silent:
                text = '**[%s] 🗿 MILESTONE REACHED 🗿**\n' % self.guild.name
                text += 'You have unlocked special role **@%s**!' % milestone
                await self._send(text)
            
            # Congratulate milestone reached on respective channel
            channel = get(self.guild.channels, name=level['discord_name'])
            text = ('**<@!%d>** has beaten level **%s** ' \
                        'and is now part of **@%s**! Congratulations!') \
                    % (self.member.id, name, role.name)
            await channel.send(text)

    async def advance(self, level: dict, silent=False):
        '''Advance to further level when player arrives at a level front page.
        "reached" role is granted to user and thus given access to channel(s).'''

        # Remove ancestors' "reached" role from user
        if self.alias == 'genius':
            ancestor_levels = await get_ancestor_levels(self.alias, level)
            for level_name in ancestor_levels:
                role_name = 'reached-' + level_name
                role = get(self.member.roles, name=role_name)
                if role:
                    await self.member.remove_roles(role)
        else:
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

        if self.alias == 'genius':
            # Create a temporary reusable table for easing queries
            query = 'DROP TABLE IF EXISTS lv; ' \
                    'CREATE TEMPORARY TABLE IF NOT EXISTS lv AS ( ' \
                        'SELECT lv.* FROM user_levels AS ulv ' \
                        'INNER JOIN levels AS lv ' \
                            'ON ulv.riddle = lv.riddle ' \
                                'AND ulv.level_name = lv.`name` ' \
                        'WHERE lv.riddle = :riddle ' \
                            'AND ulv.username = :username ' \
                    ')'
            values = {'riddle': self.alias,
                    'username': self.member.name}
            await database.execute(query, values)

            # Get list of farthest reached unlocked levels
            query = 'SELECT l1.* FROM lv AS l1 ' \
                    'LEFT JOIN lv AS l2 ' \
                        'ON l1.riddle = l2.riddle ' \
                            'AND l1.level_set = l2.level_set ' \
                            'AND l1.`index` < l2.`index` ' \
                    'WHERE l2.`index` IS NULL'
            current_levels = await database.fetch_all(query)

            # Get dict of level sets
            query = 'SELECT * FROM level_sets ' \
                    'WHERE riddle = :riddle '
            values = {'riddle': self.alias}
            result = await database.fetch_all(query, values)
            level_sets = {
                row['set_name']: row for row in result
            }
            # Replace explicit set name in level
            # names with short emoji form
            set_progress = {}
            for level in current_levels:
                set_name = level['level_set']
                if not set_name in level_sets:
                    continue
                level_set = level_sets[set_name]
                query =  \
                    'SELECT l1.* FROM levels AS l1 ' \
                    'LEFT JOIN levels as l2 ' \
                        'ON l1.level_set = l2.level_set ' \
                            'AND l1.`index` < l2.`index` ' \
                    'WHERE l1.level_set = :set_name ' \
                        'AND l1.name IN ( ' \
                            'SELECT level_name AS name FROM user_levels ' \
                            'WHERE riddle = :riddle ' \
                                'AND username = :name ' \
                                'AND discriminator = :disc ' \
                                'AND completion_time IS NOT NULL ' \
                        ') ' \
                    'AND l2.`index` IS NULL'
                values = {'riddle': self.alias, 'set_name': set_name,
                        'name': self.member.name,
                        'disc': self.member.discriminator}
                set_completed = await database.fetch_one(query, values)
                if not set_completed:
                    short_name = level_set['short_name']
                    name = level['name'].replace((set_name + ' '), short_name)

                    # Replace numerical digits with their
                    # smaller Unicode variants
                    for digit in '0123456789':
                        if digit in name:
                            value = ord(digit) - 0x30 + 0x2080
                            small_digit = chr(value)
                            name = name.replace(digit, small_digit)
                else:
                    name = level_set['emoji']
                
                index = level_set['index']
                set_progress[index] = name

            aux = sorted(set_progress.items())
            set_progress = [progress for _, progress in aux]
            s = '[' + ' '.join(set_progress) + ']'

        else:
            s = '[%s]' % level['name']
        
        # Show current level(s) in nickname
        await update_nickname(self.member, s)

    async def secret_found(self, level: dict):
        '''Grant access to secret channel.'''
        
        # Grant "reached" role
        discord_name = level['discord_name']
        if not discord_name:
            discord_name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % discord_name))
        await self.member.add_roles(reached)
        
        # Log reaching secret and send message to member
        name = level['name']
        if level['latin_name']:
            name += ' (%s)' % level['latin_name']
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has found secret level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                    self.member.discriminator, name))
        text = '**[%s]** You have found secret level **%s**. Congratulations!' \
                % (self.guild.name, name)
        await self._send(text)

    async def secret_solve(self, level: dict, points: int,
            first_to_solve=False):
        '''Solve secret level and grant special colored role.'''
        
        # Get roles from guild
        discord_name = level['discord_name']
        if not discord_name:
            discord_name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % discord_name))
        solved = get(self.guild.roles, name=('solved-%s' % discord_name))
        
        # Remove old "reached" role and add "solved" role to member
        await self.member.remove_roles(reached)
        await self.member.add_roles(solved)

        # Log solving procedure and send message to member
        n = 'DCBAS'.find(level['rank']) + 1
        stars = '★' * n
        name = level['name']
        if level['latin_name']:
            name += ' (%s)' % level['latin_name']
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has completed secret level \033[1m%s\033[0m') 
                % (self.guild.name, self.member.name,
                    self.member.discriminator, name))
        text = ('**[%s]** You have solved secret level **%s** [%s] ' \
                    'and won **%d** points!\n') \
                % (self.guild.name, name, stars, points)
        await self._send(text)
        
        # Send congratulations message to channel (and cheevos one) :)
        channel = get(self.guild.channels, name=discord_name)
        text = ''
        if first_to_solve:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
        text += ('**<@!%d>** has completed secret level **%s**! ' \
                'Congratulations!') % (self.member.id, name)
        await channel.send(text)
        if first_to_solve:
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await achievements.send(text)

    async def cheevo_found(self, cheevo: dict, points: int, path: str):
        '''Congratulations upon achievement being found.'''
        
        # Log and send congratulatory message
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'got cheevo \033[1m%s\033[0m!') %
                (self.guild.name, self.member.name,
                    self.member.discriminator, cheevo['title']))
        text = ('**[%s]** You have found achievement **_%s_**  '
                'in page `%s` and won **%d** points!\n') \
                % (self.guild.name, cheevo['title'], path, points)
        await self._send(text)
        
        # Get cheevo thumb image from path
        image_path = '../web/static/cheevos/%s/%s' \
                % (cheevo['riddle'], cheevo['image'])
        with open(image_path, 'rb') as fp:
            # Create image object
            image = File(fp, cheevo['image'])
            
            # send flavor message with description and image
            description = '_"%s"_' % cheevo['description']
            await self.member.send(description, file=image)

    async def game_completed(self):
        '''Do the honors upon user completing game.'''

        # Get completed role name from DB    
        query = 'SELECT * FROM riddles ' \
                'WHERE alias = :alias'
        values = {'alias': self.alias}
        result = await database.fetch_one(query, values)
        completed_name = result['completed_role']

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

        # Get completed role and add it to player
        completed_role = get(self.guild.roles, name=completed_name)
        await self.member.add_roles(completed_role)

        # Update nickname with winner's badge
        await update_nickname(self.member, '🏅')

        # Player has completed the game (for now?)
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m ' \
                'has finished the game!') \
                % (self.guild.name,
                    self.member.name, self.member.discriminator))
        text = '**[%s] 🏅 GAME COMPLETED 🏅**\n' % self.guild.name
        text += 'You just completed the game! **Congratulations!**'
        await self._send(text)
    
    async def game_mastered(self, alias: str):
        '''Do the honors upon user mastering game,
        i.e beating all levels and finding all achievements.'''

        # Get mastered role name from DB    
        query = 'SELECT * FROM riddles ' \
                'WHERE alias = :alias'
        values = {'alias': self.alias}
        result = await database.fetch_one(query, values)
        mastered_name = result['mastered_role']

        # Get guild role and grant it to player
        mastered_role = get(self.guild.roles, name=mastered_name)
        await self.member.add_roles(mastered_role)

        # Update nickname with shiny 💎
        await update_nickname(self.member, '💎')

        # Player has mastered the game (for now?)
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m ' \
                'has mastered the game!') \
                % (self.guild.name,
                    self.member.name, self.member.discriminator))
        text = '**[%s] 💎 GAME MASTERED 💎**\n' % self.guild.name
        text += 'You have beaten all levels, found all achievements ' \
                'and scored every single possible point in the game! ' \
                '**Outstanding!**'
        await self._send(text)


async def update_nickname(member: Member, s: str):
    '''Update user's nickname to reflect current level.
    In case it exceeds 32 characters, shorten the member's name to fit.'''
    name = member.name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:-(excess + 5)] + '(...)'
    nick = name + ' ' + s
    try:
        await member.edit(nick=nick)
    except:
        pass


def setup(_):
    pass
