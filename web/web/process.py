import re
import json
from urllib.parse import urlparse
from datetime import datetime
from pymysql.err import IntegrityError

from quart import Blueprint, request, jsonify
from quart_discord.models import User

from auth import discord
from webclient import bot_request
from inject import cheevo_ranks
from util.db import database

# Create app blueprint
process = Blueprint('process', __name__)

# Dict of pairs (level rank -> (points, color))
level_ranks = {
    'D': (50, 'cornflowerblue'),
    'C': (100, 'lawngreen'),
    'B': (200, 'gold'),
    'A': (400, 'crimson'),
    'S': (1000, 'lightcyan')
}
for rank, pair in level_ranks.items():
    level_ranks[rank] = {'points': pair[0], 'color': pair[1]}


@process.route('/process', methods=['POST', 'OPTIONS'])
async def process_url(username=None, disc=None, path=None):
    '''Process an URL sent by browser extension.'''

    # Mark function call as automated or not
    auto = (path is not None)

    if not auto and not await discord.authorized:
        # Not logged in, return status 401
        status = 401 if request.method == 'POST' else 200
        return 'Not logged in', status
    
    message, status_code = 'Success!', 200
    if auto or request.method == 'POST':
        # Receive path from request
        if not auto:
            path = (await request.data).decode('utf-8')
        
        # Get status code from request header (or 200 if not present)
        status_code = request.headers.get('Statuscode', 200)
        if status_code:
            status_code = int(status_code)

        # Create path handler object and build player data
        if not auto:
            user = await discord.get_user()
        else:
            user = lambda: None
            setattr(user, 'name', username)
            setattr(user, 'discriminator', disc)
        ph = _PathHandler()
        ok, invite_code = \
                await ph.build_handler(user, path, status_code, auto)
        if not ok:
            if not invite_code:
                # Page is not inside root path (like forum or admin pages)
                return 'Not part of root path', 403

            # User is not currently member of riddle's guild :()
            return invite_code, 401  
        
        ok, invite_code = await ph.build_player_riddle_data()
        if not ok:
            # Banned player
            return 'Banned player', 403

        # Process received path
        ok = await ph.process()
        if not ok and status_code != 404:
            # Page exists, but it's not a level one
            message, status_code = 'Not a level page', 412

        # Log received path with timestamp
        tnow = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")            
        if status_code == 404:
            print(('\033[1m[%s]\033[0m Received path ' \
                '\033[3m\033[9m%s\033[0m\033[0m ' \
                'from \033[1m%s\033[0m#\033[1m%s\033[0m (%s)')
                 % (ph.riddle_alias, ph.path,
                    ph.username, ph.disc, tnow))
            message, status_code = 'Page not found', 404
        elif status_code != 412:
            print(('\033[1m[%s]\033[0m Received path ' \
                '\033[3m\033[1m%s\033[0m \033[1m(%s)\033[0m ' \
                'from \033[1m%s\033[0m#\033[1m%s\033[0m (%s)')
                % (ph.riddle_alias, ph.path, ph.path_level,
                    ph.username, ph.disc, tnow))
            message, status_code = ph.riddle_alias, 200
        
        if invite_code:
            # If starting a new riddle, return invite code to its guild
            message, status_code = invite_code, 401
    
    # Everything's good
    return message, status_code


class _PathHandler:
    '''Handler for processing level paths.

    Updates the needed tables on database and request
    guild changes to be done by bot.'''

    riddle_alias: str
    '''Alias of riddle hosted on URL domain'''

    unlisted: bool
    '''If riddle is currently unlisted'''

    username: str
    disc: str
    '''Username and discriminator of logged in player'''

    riddle_account: dict
    '''Dict containing player's riddle account info from DB'''

    path: str
    '''Path to be processed by handler'''

    path_level: str
    '''The level path corresponds to, or `None` if not part of any'''

    status_code: int
    '''Real status code of requested page (either 200 or 404)'''

    async def build_handler(self, user: User,
            url: str, status_code: str, auto: bool):
        '''Get path from raw URL and get user info from DB.
        
        @param user: Discord user object for logged in player
        @param url: raw URL sent by the extension
        @param status_code: status code of the user-accessed page
        #param auto: if `process_url` have been called automatically'''

        # Exclude protocol from URL
        base_url = url.replace('https://', 'http://').replace('http://', '')

        # Retrieve riddle info from database
        # (https root_path is searched first, and then http)
        riddle = None
        for protocol in ('https://', 'http://'):
            url = protocol + base_url
            url_without_www = url.replace('//www.', '//')
            query = 'SELECT * FROM riddles ' \
                    'WHERE LOCATE(root_path, :url) ' \
                        'OR LOCATE(root_path, :url_without_www)'
            values = {'url': url, 'url_without_www': url_without_www}
            riddle = await database.fetch_one(query, values)
            if riddle:
                break
            
        if not riddle:
            # Page outside of levels, like forum and admin ones
            return False, None
        
        # Remove potential "www." from URL, if not required
        if not '//www.' in riddle['root_path']:
            url = url.replace('//www.', '//')

        # Check if user is member of riddle guild
        ok, invite_code = True, None
        if not auto:
            is_member = await bot_request('is-member-of-guild',
                    guild_id=859797827554770955,
                    username=user.name, disc=user.discriminator)
            if is_member == 'False':
                ok, invite_code = False, 'ktaPPtnPSn'

        # Save basic riddle info
        self.riddle_alias = riddle['alias']
        root_path = riddle['root_path']
        self.unlisted = bool(riddle['unlisted'])
        
        # Save basic user info
        self.username = user.name
        self.disc = user.discriminator

        # Get relative path by removing root portion
        self.path = url.removeprefix(root_path)

        # Ignore occurrences of consecutive slashes and trailing #
        self.path = re.sub('/{2,}', '/', self.path)
        if self.path[-1] == '#':
            self.path = self.path[:-1]

        if self.path[-1] == '/':
            # If a folder itself, add "index.htm[l]" to path's end
            self.path += 'index.' + riddle['html_extension']
        else:
            # If no extension, append explicit ".htm" to the end
            has_dot = self.path.count('.')
            if not has_dot:
                self.path += '.htm'
        
        # Save requesting status code too
        self.status_code = status_code
        
        return ok, invite_code
    
    async def build_player_riddle_data(self) -> (bool, str):
        '''Build player riddle data from database,
        creating one if not present yet.'''

        # Ignore progress for banned players :)
        query = '''SELECT * FROM accounts
            WHERE username = :username
                AND discriminator = :disc'''
        values = {'username': self.username, 'disc': self.disc}
        player = await database.fetch_one(query, values)
        if player['banned']:
            return False, None
        
        async def _get_data():
            '''Get player riddle data.'''
            query = '''SELECT * FROM riddle_accounts
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc'''
            result = await database.fetch_one(query, values)
            return result

        # Check if player's riddle acount already exists
        values['riddle'] = self.riddle_alias
        riddle_account = await _get_data()
        invite_code = None
        if not riddle_account:
            # If not, create a brand new one
            query = '''INSERT INTO riddle_accounts
                    (riddle, username, discriminator)
                VALUES (:riddle, :username, :disc)'''
            await database.execute(query, values)
            riddle_account = await _get_data()
            
            # If player isn't a guild member,
            # send an invite code to be opened on a new tab
            query = '''SELECT * FROM riddles
                WHERE alias = :riddle'''
            riddle = await database.fetch_one(query,
                {'riddle': self.riddle_alias})
            is_member = await bot_request('is-member-of-guild',
                guild_id=riddle['guild_id'],
                username=self.username, disc=self.disc)
            if is_member == 'False':
                invite_code = riddle['invite_code']
        
        # Update current riddle being played
        query = '''UPDATE accounts
            SET current_riddle = :riddle
            WHERE username = :username AND discriminator = :disc'''
        await database.execute(query, values)
        
        # Build dict from query result
        self.riddle_account = dict(riddle_account)
        return True, invite_code

    async def process(self):
        '''Process level path.
        
        @path: a level path in the current riddle domain'''

        # Search for unlocked and unbeaten levels on DB
        current_name = self.riddle_account['current_level']
        query = 'SELECT is_secret, `index`, name, latin_name, ' \
                    'answer, `rank`, discord_name FROM user_levels ' \
                'INNER JOIN levels ' \
                    'ON levels.riddle = user_levels.riddle ' \
                        'AND levels.name = user_levels.level_name ' \
                        'AND is_secret IS FALSE ' \
                'WHERE user_levels.riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND completion_time IS NULL'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        current_levels = await database.fetch_all(query, values)

        # Check if path is answer to any of the found levels
        current_level = None
        for level in current_levels:
            if self.path == level['answer']:
                # If user entered the correct answer, register completion
                lh = _NormalLevelHandler(level, self)
                await lh.register_completion()
                current_level = level
                break

        # Check if page is a normal one (i.e not txt/image/video/etc)
        dot_index = self.path.rfind('.')
        extension = self.path[(dot_index + 1):]
        is_normal_page = 'htm' in extension or 'php' in extension
        
        # Check if path corresponds to a valid page (non 404)
        query = 'SELECT * FROM level_pages ' \
                'WHERE riddle = :riddle AND path = :path'
        values = {'riddle': self.riddle_alias, 'path': self.path}
        page = await database.fetch_one(query, values)
        if not page or not page['level_name']:
            if self.status_code == 404 and is_normal_page:
                # If page comes from a real 404 (and not a non level page),
                # then it should still increment all hit counters.
                await self._update_hit_counters()
            
            # Nothing more to do if not part of a level
            return False
        
        # Get requested page's level info from DB
        self.path_level = page['level_name']
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': self.path_level}
        page_level = await database.fetch_one(query, values)
        
        current_solved = False
        if current_name != '🏅':
            # Search for some level which have the current path as front
            query = '''SELECT * FROM levels
                WHERE riddle = :riddle AND is_secret IS FALSE
                    AND (`path` = :path OR `path` LIKE "%\":path\"%")'''
            values = {'riddle': self.riddle_alias, 'path': self.path}
            level = await database.fetch_one(query, values)
            if level:
                # Check if level has already been unlocked beforehand
                query = 'SELECT * FROM user_levels ' \
                        'WHERE riddle = :riddle ' \
                            'AND username = :name AND discriminator = :disc ' \
                            'AND level_name = :level_name'
                values = {'riddle': self.riddle_alias,
                        'name': self.username, 'disc': self.disc,
                        'level_name': level['name']}
                already_unlocked = await database.fetch_one(query, values)
                if not already_unlocked:
                    # Check if all required levels are already beaten
                    query = 'SELECT * FROM level_requirements ' \
                            'WHERE riddle = :riddle AND level_name = :name'
                    other_values = {'riddle': self.riddle_alias,
                            'name': level['name']}
                    result = await database.fetch_all(query, other_values)
                    level_requirements = [row['requires'] for row in result]
                    can_unlock = True
                    for req in level_requirements:
                        query = 'SELECT * FROM user_levels ' \
                            'WHERE riddle = :riddle ' \
                                'AND username = :name ' \
                                'AND discriminator = :disc ' \
                                'AND level_name = :level_name ' \
                                'AND completion_time IS NOT NULL'
                        values['level_name'] = req
                        req_satisfied = \
                                await database.fetch_one(query, values)
                        if not req_satisfied:
                            can_unlock = False
                            break
                    
                    if can_unlock:
                        # A new level has been found!
                        lh = _NormalLevelHandler(page_level, self)
                        await lh.register_finding()
            
        # Check for secret level pages
        # (also check for phony JSON of multi-front levels)
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                    'AND (`path` = :path OR `path` LIKE "%\":path\"%")'
        values = {'riddle': self.riddle_alias, 'path': self.path}
        secret = await database.fetch_one(query, values)
        if secret:
            # "A secret has been found"
            sh = _SecretLevelHandler(secret, self)
            await sh.register_finding()
        
        # Check if a secret level was beaten
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                    'AND answer = :answer'
        values = {'riddle': self.riddle_alias, 'answer': self.path}
        secret = await database.fetch_one(query, values)
        if secret:
            sh = _SecretLevelHandler(secret, self)
            await sh.register_completion()
    
        # If the currently level being visited was not unlocked
        # yet, ignore it for access counting purposes.
        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :username AND discriminator = :disc ' \
                    'AND level_name = :level_name '
        values = {'riddle': self.riddle_alias,
                'username': self.username, 'disc': self.disc,
                'level_name': self.path_level}
        is_unlocked = await database.fetch_one(query, values)
        if not is_unlocked:
            values['level_name'] = None

        # Mark level currently being visited in `last_visited_level` field
        query = 'UPDATE riddle_accounts ' \
                'SET last_visited_level = :level_name ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :username AND discriminator = :disc '
        await database.execute(query, values)

        # If a normal page, update all hit counters
        if is_normal_page:
            await self._update_hit_counters()

        # if not has_access():
        #     # Forbid user from accessing any level further than permitted
        #     abort(403)
        
        # Get new current level info from DB
        current_name = self.riddle_account['current_level']
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :level_name'
        values = {'riddle': self.riddle_alias, 'level_name': current_name}
        current_level = await database.fetch_one(query, values)

        # Register into database new page access (if applicable)
        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :username AND discriminator = :disc ' \
                    'AND level_name = :level_name AND find_time IS NOT NULL'
        values = {'riddle': self.riddle_alias,
                'username': self.username, 'disc': self.disc,
                'level_name': page_level['name']}
        cond = await database.fetch_one(query, values)
        if not cond:
            query = 'SELECT COUNT(*) AS count FROM user_levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :username AND discriminator = :disc ' \
                        'AND level_name IN (' \
                            'SELECT requires FROM level_requirements ' \
                            'WHERE riddle = :riddle ' \
                                'AND level_name = :level_name) ' \
                        'AND completion_time IS NOT NULL'
            result = await database.fetch_one(query, values)
            count_user = result['count'] if result else 0
            query = 'SELECT COUNT(*) AS count FROM level_requirements ' \
                    'WHERE riddle = :riddle AND level_name = :level_name ' \
                    'GROUP BY level_name'
            values = {'riddle': self.riddle_alias,
                    'level_name': page_level['name']}
            result = await database.fetch_one(query, values)
            count_req = result['count'] if result else 0
            cond = (count_user == count_req)          

        if cond:
            # Check if page wasn't been found yet
            query = 'SELECT * FROM user_pages ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :username AND discriminator = :disc ' \
                        'AND path = :path'
            base_values = {'riddle': self.riddle_alias,
                    'username': self.username, 'disc': self.disc}
            values = base_values | {'path': self.path}
            already_found = await database.fetch_one(query, values)
            if not already_found:
                # Insert new page in `user_pages `
                tnow = datetime.utcnow()
                query = 'INSERT INTO user_pages ' \
                        'VALUES (:riddle, :username, :disc, ' \
                            ':level_name, :path, :time)'
                values = values | \
                        {'level_name': self.path_level, 'time': tnow}
                await database.execute(query, values)

                # Increment player's riddle page count
                query = 'UPDATE riddle_accounts ' \
                        'SET page_count = page_count + 1 ' \
                        'WHERE riddle = :riddle ' \
                            'AND username = :username AND discriminator = :disc'
                await database.execute(query, base_values)

            # Check and possibly grant an achievement
            await self._process_cheevo()
        
        return True
    
    async def _update_hit_counters(self):
        '''Update player's, riddle's and level's hit counters.'''

        # Update player/riddle hit counters
        query = 'UPDATE riddle_accounts ' \
                'SET hit_counter = hit_counter + 1 ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)
        query = 'UPDATE riddles ' \
                'SET hit_counter = hit_counter + 1 ' \
                'WHERE alias = :alias '
        await database.execute(query, {'alias': self.riddle_alias})

        # Check last level visited by player (which can be the current).
        # All subsequent 404 pages are counted as part of such level,
        # until player visits a new valid level page.
        query = 'SELECT * FROM riddle_accounts ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        result = await database.fetch_one(query, values)
        last_visited_level = result['last_visited_level']
        if last_visited_level:
            # Increment completion access count for unbeaten levels.
            # Notice that nothing happens if leavel was already completed.
            query = 'UPDATE user_levels ' \
                    'SET completion_hit_counter = ' \
                        'completion_hit_counter + 1 ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND level_name = :level_name ' \
                        'AND completion_time IS NULL '
            values['level_name'] = last_visited_level
            await database.execute(query, values)
    
    async def update_score(self, points: int):
        '''Record player score increase, by given points, in DB.'''

        # Increase player's riddle score
        query = '''UPDATE riddle_accounts
            SET score = score + :points,
                recent_score = recent_score + :points
            WHERE riddle = :riddle
                AND username = :name AND discriminator = :disc'''
        values = {'points': points, 'riddle': self.riddle_alias,
            'name': self.username, 'disc': self.disc}
        await database.execute(query, values)

        # Increase global score (unless riddle is unlisted)
        if not self.unlisted:
            query = '''UPDATE accounts
                SET global_score = global_score + :points,
                    recent_score = recent_score + :points
                WHERE username = :name AND discriminator = :disc'''
            values.pop('riddle')
            await database.execute(query, values)
    
    async def _process_cheevo(self):
        '''Grant cheevo and awards if page is an achievement one.'''

        # Check if it's an achievement page
        query = 'SELECT * FROM achievements ' \
                'WHERE riddle = :riddle ' \
                    'AND JSON_CONTAINS(paths_json, :path, "$.paths")'
        values = {'riddle': self.riddle_alias,
                'path': ('\"%s\"' % self.path)}
        cheevo = await database.fetch_one(query, values)
        if not cheevo:
            return
        
        paths_json = json.loads(cheevo['paths_json'])
        if 'operator' in paths_json and paths_json['operator'] == 'AND':
            # If an 'AND' operator, all cheevo pages must have been found
            ok = True
            for path in paths_json['paths']:
                query = 'SELECT * FROM user_pages ' \
                        'WHERE riddle = :riddle AND username = :name ' \
                        'AND discriminator = :disc AND path = :path'
                values = {'riddle': self.riddle_alias, 'name': self.username,
                        'disc': self.disc, 'path': path}
                result = await database.fetch_one(query, values)
                if not result:
                    ok = False
                    break
            if not ok:
                return
            
        # If positive, add it to user's collection
        time = datetime.utcnow()
        query = 'INSERT INTO user_achievements ' \
                'VALUES (:riddle, :name, :disc, :title, :time)'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'title': cheevo['title'], 'time': time}
        try:
            await database.execute(query, values)
            print(('> \033[1m[%s]\033[0m \033[1m%s#%s\033[0m '
                    'got cheevo \033[1m%s\033[0m!') %
                    (self.riddle_alias, self.username,
                        self.disc, cheevo['title']))
        except IntegrityError:
            return

        # Also Update user and global scores
        points = cheevo_ranks[cheevo['rank']]['points']
        await self.update_score(points)

        # Send request to bot to congratulate member
        await bot_request('unlock', method='cheevo_found',
                alias=self.riddle_alias,
                username=self.username, disc=self.disc,
                cheevo=dict(cheevo), points=points, page=self.path)


class _LevelHandler:
    '''Handler base class for processing levels.'''
    
    level: dict
    '''Dict containing level DB data'''
    
    points: int
    '''Points awarded upon level completion'''

    ph: _PathHandler
    '''Reference to parent caller PH'''
    
    def __init__(self, level: dict, ph: _PathHandler):
        '''Register level DB data and points,
        as well as parent attributes from PH.
        
        @param level: Level DB table row data
        @param ph: The parent's paths handler'''

        self.level = dict(level)
        rank = level['rank']
        self.points = level_ranks[rank]['points']
        
        # Set some attributes from parent caller PH for easier access
        self.ph = ph
        for name in ('riddle_alias', 'unlisted',
                'username', 'disc', 'riddle_account'):
            attr = getattr(ph, name)
            setattr(self, name, attr)
    
    async def _get_user_level_row(self):
        ''':return: User/level registry from DB.'''

        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle AND username = :name ' \
                'AND discriminator = :disc AND level_name = :level_name'
        values = {'riddle': self.riddle_alias, 
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name']}
        row = await database.fetch_one(query, values)
        return row
    
    async def register_finding(self, method: str) -> bool:
        '''Base level finding procedures.
        
        :param method: bot request path; "advance" or "secret_found",
            whether it's a normal or secret level
        :return: If a new level was indeed been found'''
        
        # Check if level was not yet been found
        row = await self._get_user_level_row()
        if row:
            return False
        
        # Register it on user table with current find time
        time = datetime.utcnow()
        query = 'INSERT INTO user_levels ' \
                '(riddle, username, discriminator, ' \
                    'level_name, find_time) ' \
                'VALUES (:riddle, :name, :disc, ' \
                    ':level_name, :time)'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name'], 'time': time}
        await database.execute(query, values)
        
        # Call bot unlocking procedure
        await bot_request('unlock', method=method,
                alias=self.riddle_alias, level=self.level,
                username=self.username, disc=self.disc)
        
        return True
    
    async def register_completion(self) -> bool:
        '''Register level completion and update all needed tables.
        
        :return: If level is unlocked AND yet to be completed.'''

        # Check if level is unlocked AND unbeaten
        row = await self._get_user_level_row()
        if not row or row['completion_time']:
            return False

        # Update level-related tables
        await self._update_info()
        
        return True

    async def _update_info(self):
        '''Update level-related tables.'''

        # Update global user completion count
        query = 'UPDATE levels ' \
                'SET completion_count = completion_count + 1 ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias,
                'name': self.level['name']}
        await database.execute(query, values)

        # Update user and global scores
        await self.ph.update_score(self.points)


class _NormalLevelHandler(_LevelHandler):
    '''Handler for normal (non secret) levels.'''

    def __init__(self, level: dict, ph: _PathHandler):
        super().__init__(level, ph)
    
    async def register_finding(self):
        '''Increment player level upon reaching level's front page.'''
        
        # Send request to bot for unlocking channel    
        is_new = await super().register_finding('advance')
        if not is_new:
            return
        
        # Update player's current_level and reset their page count
        query = 'UPDATE riddle_accounts ' \
                'SET current_level = :name_next ' \
                'WHERE riddle = :riddle AND ' \
                    'username = :name AND discriminator = :disc'
        values = {'name_next': self.level['name'], 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        self.riddle_account['current_level'] = self.level['name']
        await database.execute(query, values)

    async def register_completion(self):
        '''Register normal level completion and update all needed tables.'''

        # Do base completion procedures first
        ok = await super().register_completion()
        if not ok:
            return
        
        # Check if player was first to solve level
        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle AND level_name = :level_name'
        values = {'riddle': self.riddle_alias,
                'level_name': self.level['name']}
        result = await database.fetch_one(query, values)
        first_to_solve = (result is None)
        
        # Register level completion in designated table
        time = datetime.utcnow()
        query = 'UPDATE user_levels ' \
                'SET completion_time = :time ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :level'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level': self.level['name'], 'time': time}
        await database.execute(query, values)
    
        # Bot level beat procedures
        await bot_request('unlock', method='beat',
                alias=self.riddle_alias,
                level=self.level, points=self.points,
                username=self.username, disc=self.disc,
                first_to_solve=first_to_solve)
    
        # Check if level just completed in the final one
        query = '''SELECT * FROM riddles
            WHERE alias = :riddle'''
        values = {'riddle': self.riddle_alias}
        final_level = await database.fetch_val(query, values, 'final_level')
        if self.level['name'] == final_level:
            # Player has just completed the game :)
            await bot_request('unlock', method='game_completed',
                    alias=self.riddle_alias,
                    username=self.username, disc=self.disc)


class _SecretLevelHandler(_LevelHandler):
    '''Handler for secret levels.'''

    def __init__(self, level: dict, ph: _PathHandler):
        super().__init__(level, ph)

    async def register_finding(self):
        '''Register new secret if not yet been found.'''
        await super().register_finding('secret_found')
        
    async def register_completion(self):
        '''Register normal level completion and update all needed tables.'''

        # Do base completion procedures first
        ok = await super().register_completion()
        if not ok:
            return
        
        # Check if player was first to solve level
        query = 'SELECT * FROM user_levels ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        result = await database.fetch_one(query, values)
        first_to_solve = (result is None)
        
        # Register level completion in designated table
        time = datetime.utcnow()
        query = 'UPDATE user_levels ' \
                'SET completion_time = :time ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :level_name'
        values = {'time': time, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name']}
        await database.execute(query, values)
        
        # Bot secret solve procedures
        await bot_request('unlock', method='secret_solve',
                alias=self.riddle_alias,
                level=self.level, points=self.points,
                username=self.username, disc=self.disc,
                first_to_solve=first_to_solve)
