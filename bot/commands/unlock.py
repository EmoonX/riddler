import logging

from discord import abc, Guild, Member, File
from discord.utils import get
from discord.errors import Forbidden

from bot import bot
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

    in_riddle_guild: bool
    '''Player is member of the riddle guild per se'''

    def __init__(self, alias: str, username: str, disc: str):
        '''Build handler for guild `alias` and member `username#disc`.'''
        self.alias = alias
        riddle = riddles[alias]
        self.guild = riddle.guild
        self.levels = riddle.levels
        self.member = get(riddle.guild.members,
                name=username, discriminator=disc)
        self.in_riddle_guild = (self.member is not None)
        if not self.in_riddle_guild:
            # Not a member of riddle guild, so use Wonderland instead
            wonderland = get(bot.guilds, name='Riddler\'s Wonderland II')
            self.member = get(wonderland.members,
                    name=username, discriminator=disc)
                        
    
    async def _send(self, text: str,
            channel: abc.Messageable = None, **kwargs):
        '''Try to send a message to member/channel.
        If they/it do(es)n't accept DMs from bot, ignore.'''

         # Check if Riddler DMs are silenced by player 
        query = 'SELECT * FROM accounts ' \
                'WHERE username = :username AND discriminator = :disc'
        values = {'username': self.member.name,
                'disc': self.member.discriminator}
        result = await database.fetch_one(query, values)
        silent = result['silence_notifs']
        if silent:
            return
        
        if channel:
            # If not a member of riddle guild, no guild messages to send
            if not self.in_riddle_guild:
                return
        else:
            # Message is a DM to member
            channel = self.member

        # Try to send message to member (default) or channel
        try:
            await channel.send(text, **kwargs)
        except Forbidden:
            logging.info(('\033[1m[%s]\033[0m ' \
                    'Can\'t send messages  to \033[1m%s#%s\033[0m ')
                    % (self.guild.name, self.member.name,
                        self.member.discriminator))

    async def beat(self, level: dict, points: int,
            first_to_solve: bool, milestone: str):
        '''Procedures upon player having beaten a level.'''

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
        text = ('**[%s]** You have solved level **%s** [%s] ' \
                    'and won **%d** points!\n') \
                % (self.guild.name, name, stars, points)
        await self._send(text)
        
        # Send also to channels if first to solve level
        if first_to_solve and self.in_riddle_guild:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
            text += ('**<@!%d>** has completed level **%s**! ' \
                    'Congratulations!') % (self.member.id, name)
            channel = get(self.guild.channels, name=level['discord_name'])
            await self._send(text, channel)
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await self._send(text, achievements)
        
        if milestone:
            # Congratulatory DM
            text = '**[%s] 🗿 MILESTONE REACHED 🗿**\n' % self.guild.name
            text += 'You have reached milestone **@%s**!' % milestone
            await self._send(text)
            if not self.in_riddle_guild:
                return
            
            # Add special milestone role and congratulate in channel
            role = get(self.guild.roles, name=milestone)
            await self.member.add_roles(role)
            channel = get(self.guild.channels, name=level['discord_name'])
            text = ('**<@!%d>** has beaten level **%s** ' \
                        'and is now part of **@%s**! Congratulations!') \
                    % (self.member.id, name, role.name)
            await self._send(text, channel)

        elif self.alias == 'genius':
            query = 'SELECT * FROM level_sets ' \
                    'WHERE riddle = :riddle AND final_level = :level_name'
            values = {'riddle': self.alias, 'level_name': level['name']}
            completed_set = await database.fetch_one(query, values)
            if completed_set:
                # Congratulatory DM
                role_name = completed_set['completion_role']
                text = '**[%s] 🗿 LEVEL SET BEATEN 🗿**\n' % self.guild.name
                text += 'You have unlocked special title **@%s**!' % role_name
                await self._send(text)
                if not self.in_riddle_guild:
                    return

                # Add special set completion role and remove
                # player's final level's 'reached-' role
                completion_role = get(self.guild.roles, name=role_name)
                await self.member.add_roles(completion_role)
                role_name = 'reached-' + level['discord_name']
                reached_role = get(self.guild.roles, name=role_name)
                await self.member.remove_roles(reached_role)
                
                # Congratulate milestone reached on respective channel
                if self.member == self.guild.owner:
                    return
                channel = get(self.guild.channels, name=level['discord_name'])
                text = ('**<@!%d>** has beaten level **%s** ' \
                            'and is now part of **@%s**! Congratulations!') \
                        % (self.member.id, name, completion_role.name)
                await self._send(text, channel)
                
                # Update multi-nickname
                await multi_update_nickname(self.alias, self.member)


    async def advance(self, level: dict):
        '''Advance to further level when player arrives at a level front page.
        "reached" role is granted to user and thus given access to channel(s).'''

        if not self.in_riddle_guild:
            # All procedures here are guild-related
            return

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

        # Show current level(s) in nickname
        if self.alias == 'genius':
            await multi_update_nickname(self.alias, self.member)
        else:
            s = '[%s]' % level['name']
            await update_nickname(self.member, s)        

    async def secret_found(self, level: dict):
        '''Grant access to secret channel.'''
        
        # Log reaching secret and send message to member
        name = level['name']
        if level['latin_name']:
            name += ' (%s)' % level['latin_name']
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'has found secret level \033[1m%s\033[0m') \
                % (self.guild.name, self.member.name,
                    self.member.discriminator, name))
        text = ('**[%s]** You found secret level **%s**. ' \
                'Congratulations!') \
                % (self.guild.name, name)
        await self._send(text)
        if not self.in_riddle_guild:
            return

        # Grant "reached" role
        discord_name = level['discord_name']
        if not discord_name:
            discord_name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % discord_name))
        await self.member.add_roles(reached)

    async def secret_solve(self, level: dict, points: int,
            first_to_solve=False):
        '''Solve secret level and grant special colored role.'''
        
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
        text = ('**[%s]** You solved secret level **%s** [%s] ' \
                    'and won **%d** points!\n') \
                % (self.guild.name, name, stars, points)
        await self._send(text)
        if not self.in_riddle_guild:
            return

        # Get roles from guild
        discord_name = level['discord_name']
        if not discord_name:
            discord_name = level['name']
        reached = get(self.guild.roles, name=('reached-%s' % discord_name))
        solved = get(self.guild.roles, name=('solved-%s' % discord_name))
        
        # Remove old "reached" role and add "solved" role to member
        await self.member.remove_roles(reached)
        await self.member.add_roles(solved)
        
        # Send congratulations message to channel (and cheevos one?) :)
        if self.member == self.guild.owner:
            return
        channel = get(self.guild.channels, name=discord_name)
        text = ''
        if first_to_solve:
            text = '**🏅 FIRST TO SOLVE 🏅**\n'
        text += ('**<@!%d>** has completed secret level **%s**! ' \
                'Congratulations!') % (self.member.id, name)
        await self._send(text, channel)
        if first_to_solve:
            achievements = get(self.guild.channels, name='achievements')
            if achievements:
                await self._send(text, achievements)

    async def cheevo_found(self, cheevo: dict, points: int, path: str):
        '''Congratulations upon achievement being found.'''
        
        # Log and send congratulatory message
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                'got cheevo \033[1m%s\033[0m!') %
                (self.guild.name, self.member.name,
                    self.member.discriminator, cheevo['title']))
        text = ('**[%s]** You unlocked achievement **_%s_**  '
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
            await self._send(description, file=image)

    async def game_completed(self):
        '''Do the honors upon player completing game.'''

        # Player has completed the game (for now?)
        logging.info(('\033[1m[%s]\033[0m \033[1m%s#%s\033[0m ' \
                'has finished the game!') \
                % (self.guild.name,
                    self.member.name, self.member.discriminator))
        text = '**[%s] 🏅 GAME COMPLETED 🏅**\n' % self.guild.name
        text += 'You just completed the game! **Congratulations!**'
        await self._send(text)
        if not self.in_riddle_guild:
            return

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

        # Get completed role and add it to player
        completed_role = get(self.guild.roles, name=completed_name)
        await self.member.add_roles(completed_role)

        # Update nickname with winner's badge
        await update_nickname(self.member, '🏅')

    async def game_mastered(self, alias: str):
        '''Do the honors upon player mastering game,
        i.e beating all levels and finding all achievements.'''

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
        if not self.in_riddle_guild:
            return

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


async def multi_update_nickname(riddle: str, member: Member):
    '''Update complete nickname
    (for riddles which use the sets system).'''

    # Get level sets from DB
    query = 'SELECT * FROM level_sets ' \
            'WHERE riddle = :riddle '
    values = {'riddle': riddle}
    level_sets = await database.fetch_all(query, values)

    set_progress = {}
    for level_set in level_sets:
        # Check if current set was completed
        set_name = level_set['name']
        query = 'SELECT * FROM level_sets ' \
                'WHERE riddle = :riddle AND name = :set_name ' \
                    'AND final_level IN (' \
                        'SELECT level_name FROM user_levels ' \
                        'WHERE riddle = :riddle ' \
                            'AND username = :username ' \
                            'AND discriminator = :disc ' \
                            'AND completion_time IS NOT NULL)'
        values = {'riddle': riddle, 'set_name': set_name,
                'username': member.name, 'disc': member.discriminator}
        set_completed = await database.fetch_one(query, values)
        if not set_completed:
            # Get current last (found but not completed) level
            query = 'SELECT * FROM user_levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :username ' \
                        'AND discriminator = :disc ' \
                        'AND level_name IN (' \
                            'SELECT name FROM levels ' \
                            'WHERE riddle = :riddle ' \
                                'AND level_set = :set_name) '
            unlocked_levels = await database.fetch_all(query, values)
            if not unlocked_levels:
                # Player haven't played set yet
                continue
            level = unlocked_levels[-1]

            # Replace explicit set name with short name
            short_name = level_set['short_name']
            name = level['level_name'].replace((set_name + ' '), short_name)

            # Replace numerical digits with their
            # smaller Unicode variants
            for digit in '0123456789':
                if digit in name:
                    value = ord(digit) - 0x30 + 0x2080
                    small_digit = chr(value)
                    name = name.replace(digit, small_digit)
        else:
            # Just use an emoji for completed sets :)
            name = level_set['emoji']
        
        index = level_set['index']
        set_progress[index] = name

    # Join list of set progress strings and update nickname
    aux = sorted(set_progress.items())
    set_progress = [progress for _, progress in aux]
    s = '[' + ' '.join(set_progress) + ']'
    await update_nickname(member, s)


def setup(_):
    pass
