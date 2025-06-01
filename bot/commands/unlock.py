import logging
from typing import Optional

import discord
from discord.abc import Messageable
from discord.errors import Forbidden
from discord.utils import get

from bot import bot
from riddle import riddles
from util.db import database
from util.levels import get_ancestor_levels


class UnlockHandler:
    '''Handler for processing guild unlocking procedures
    (granting roles, congratulating player, finishing the riddle, etc).'''

    alias: str
    '''Unique identifier for riddle.'''

    full_name: str
    '''Riddle's full name.'''

    guild: discord.Guild
    '''Guild where things will be unlocked.'''

    levels: dict
    '''Dict of normal riddle levels.'''

    member: discord.Member
    '''Discord guild member, the one to unlock things for.'''

    in_riddle_guild: bool
    '''If player is member of the riddle guild per se.'''

    def __init__(self, alias: str, username: str):
        '''Build handler for guild `alias` and member `username`.'''

        self.alias = alias
        riddle = riddles[alias]
        self.full_name, self.guild, self.levels = (
            riddle.full_name, riddle.guild, riddle.levels
        )

        # Check player guild membership
        self.in_riddle_guild = False
        if riddle.guild:
            self.member = get(riddle.guild.members, name=username)
            self.in_riddle_guild = (self.member is not None)

        # Use Wonderland membership as replacement
        if not self.in_riddle_guild:
            # Not a member of specific riddle guild, so use another one
            members = bot.get_all_members()
            self.member = get(members, name=username)

    async def _send(
        self,
        text: str,
        channel: Optional[Messageable] = None,
        **kwargs,
    ):
        '''Try to send a message to member/channel.
        If they/it do(es)n't accept DMs from bot, ignore.'''

        if not channel and not self.member:
            # Unreachable player
            return

         # Check if Riddler DMs are silenced by player
        query = '''
            SELECT * FROM accounts
            WHERE username = :username
        '''
        values = {'username': self.member.name}
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
            logging.info(
                ('\033[1m[%s]\033[0m '
                    'Can\'t send messages to \033[1m%s\033[0m '),
                self.full_name, self.member.name
            )

    async def advance(self, level: dict):
        '''
        Advance to designated level.
        "reached-" role is granted to user and thus access to channel(s).
        '''

        if level['is_secret']:
            # Send message to player upon finding secret level
            name = level['name']
            if level['latin_name']:
                name += f" ({level['latin_name']})"
            text = (
                f"**[{self.full_name}]** "
                f"You have found secret level **{name}**. Congratulations!"
            )
            await self._send(text)

        if not self.in_riddle_guild:
            return

        if not level['is_secret']:
            # Remove ancestors' "reached" role from user
            ancestor_levels = await get_ancestor_levels(self.alias, level)
            for level_name in ancestor_levels:
                role_name = 'reached-' + level_name
                role = get(self.member.roles, name=role_name)
                if role:
                    await self.member.remove_roles(role)

        # Add "reached" role to member
        discord_name = level['discord_name']
        role = get(self.guild.roles, name=f"reached-{discord_name}")
        await self.member.add_roles(role)

        # Show current level(s) in nickname
        await multi_update_nickname(self.alias, self.member)

    async def beat(self, level: dict, points: int):
        '''Procedures to be done when level is beaten.'''

        # Log solving procedure and send message to member
        n = 'FDCBAS'.find(level['rank'])
        stars = f"[{'★' * n}]" if n > 0 else ''
        name = level['name']
        if level['latin_name']:
            name += f" ({level['latin_name']})"
        level_type = 'level' if not level['is_secret'] else 'secret level'
        text = (
            f"**[{self.full_name}]** "
            f"You have solved {level_type} **{name}** {stars} "
            f"and won **{points}** points."
        )
        await self._send(text)

        if not self.in_riddle_guild:
            return

        # Check for set completion
        query = '''
            SELECT * FROM level_sets
            WHERE riddle = :riddle AND final_level = :level_name
        '''
        values = {'riddle': self.alias, 'level_name': level['name']}
        completed_set = await database.fetch_one(query, values)
        if completed_set:
            # Congratulatory DM
            role_name = completed_set['completion_role']
            text = (
                f"**[{self.full_name}] "
                    f"🗿 SET {completed_set['name']} COMPLETED 🗿**\n"
                f"You have unlocked special title **@{role_name}**!"
            )
            await self._send(text)

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
            text = (
                f"**<@!{self.member.id}>** has beaten level **{name}** "
                    f"and is now part of **@{completion_role.name}**! "
                    'Congratulations!'
            )
            await self._send(text, channel)

            # Update multi-nickname
            await multi_update_nickname(self.alias, self.member)

        if level['is_secret'] and self.in_riddle_guild:
            # Get roles from guild
            discord_name = level['discord_name']
            if not discord_name:
                discord_name = level['name']
            reached = get(self.guild.roles, name=f"reached-{discord_name}")
            solved = get(self.guild.roles, name=f"solved-{discord_name}")

            # Remove old "reached" role and add "solved" role to member
            await self.member.remove_roles(reached)
            await self.member.add_roles(solved)

    async def cheevo_found(self, cheevo: dict, points: int, path: str):
        '''Congratulations upon achievement being found.'''

        # Send congratulatory message
        text = (
            f"**[{self.full_name}]** "
            f"You have unlocked achievement **_{cheevo['title']}_** "
            f"on page `{path}` and won **{points}** points.\n"
        )
        await self._send(text)

        # Get cheevo thumb image from path
        image_path = (
            f"../../web/static/cheevos/{cheevo['riddle']}/{cheevo['image']}"
        )
        with open(image_path, 'rb') as fp:
            # Create image object
            image = discord.File(fp, cheevo['image'])

            # send flavor message with description and image
            description = f"_\"{cheevo['description']}\"_"
            await self._send(description, file=image)

    async def game_completed(self):
        '''Do the honors upon player completing game.'''

        # Player has finished the riddle (for now?)
        text = (
            f"**[{self.full_name}] 🏅 COMPLETED**\n"
            f"You have just finished _{self.full_name}_. Congratulations!"
        )
        await self._send(text)
        if not self.in_riddle_guild:
            return

        # Get completed role name from DB
        query = '''
            SELECT * FROM riddles
            WHERE alias = :alias
        '''
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

    async def game_mastered(self):
        '''Do the honors upon player mastering game,
        i.e beating all levels and finding all achievements.'''

        # Player has mastered the riddle (for now?)
        text = (
            f"**[{self.full_name}] 💎 MASTERED**\n"
            'You have beaten all the levels, found all the achievements '
            f"and scored every single possible point in _{self.full_name}_. "
            'Outstanding!'
        )
        await self._send(text)
        if not self.in_riddle_guild:
            return

        # Get mastered role name from DB
        query = '''
            SELECT * FROM riddles
            WHERE alias = :alias
        '''
        values = {'alias': self.alias}
        result = await database.fetch_one(query, values)
        mastered_name = result['mastered_role']

        # Get guild role and grant it to player
        mastered_role = get(self.guild.roles, name=mastered_name)
        await self.member.add_roles(mastered_role)

        # Update nickname with shiny 💎
        await update_nickname(self.member, '💎')


async def update_nickname(member: discord.Member, s: str):
    '''Update user's nickname to reflect current level.
    In case it exceeds 32 characters, shorten the member's name to fit.'''

    name = member.global_name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:-(excess + 5)] + '(...)'
    nick = name + ' ' + s
    try:
        await member.edit(nick=nick)
    except Forbidden:
        pass


async def multi_update_nickname(riddle: str, member: discord.Member):
    '''Update complete nickname.'''

    # Get level sets from DB
    query = '''
        SELECT * FROM level_sets
        WHERE riddle = :riddle
    '''
    values = {'riddle': riddle}
    level_sets = await database.fetch_all(query, values)

    set_progress = {}
    for level_set in level_sets:
        # Check if current set was completed
        set_name = level_set['name']
        query = '''
            SELECT * FROM level_sets
            WHERE riddle = :riddle AND name = :set_name
                AND final_level IN (
                    SELECT level_name FROM user_levels
                    WHERE riddle = :riddle
                        AND username = :username
                        AND completion_time IS NOT NULL
                )
        '''
        values = {
            'riddle': riddle,
            'set_name': set_name,
            'username': member.name
        }
        set_completed = await database.fetch_one(query, values)
        if not set_completed:
            # Get current last (found but not completed) level
            query = '''
                SELECT * FROM levels AS lv
                WHERE riddle = :riddle
                    AND level_set = :set_name
                    AND name IN (
                        SELECT level_name FROM user_levels AS ul
                        WHERE riddle = :riddle
                            AND username = :username
                            AND completion_time IS NULL
                    )
                ORDER BY `index` DESC
            '''
            level = await database.fetch_one(query, values)
            if not level:
                # Player haven't played set yet
                continue

            name = level['name']
            short_name = level_set['short_name']
            if short_name:
                # Replace explicit set name with short name, if any
                name = name.replace((set_name + ' '), short_name)

                # Replace numerical digits with their
                # smaller Unicode variants
                for digit in '0123456789':
                    if digit in name:
                        value = ord(digit) - 0x30 + 0x2080
                        small_digit = chr(value)
                        name = name.replace(digit, small_digit)
        else:
            # Ignore completed set if player progressed further than it
            final_level = level_set['final_level']
            query = '''
                SELECT * FROM level_requirements AS reqs
                WHERE requires = :level_name AND level_name IN (
                    SELECT level_name FROM user_levels AS ul
                    WHERE riddle = :riddle
                        AND username = :username
                        AND reqs.level_name = ul.level_name
                )
            '''
            values.pop('set_name')
            values['level_name'] = final_level
            reached_further_level = await database.fetch_one(query, values)
            if reached_further_level:
                continue

            # Otherwise, just use an emoji for it :)
            name = level_set['emoji']

        index = level_set['index']
        set_progress[index] = name

    # Join list of set progress strings and update nickname
    s = ''
    aux = sorted(set_progress.items())
    set_progress = [progress
        for _, progress in aux if progress]
    if set_progress:
        sep = ', ' if len(set_progress) <= 2 else ' '
        s = sep.join(set_progress)
        if s != '🏅':
            s = f"⁅{s}⁆"
    await update_nickname(member, s)


async def setup(_):
    pass
