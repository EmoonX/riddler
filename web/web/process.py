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
@process.route('/process-beta', methods=['POST', 'OPTIONS'])
async def process_url():
    '''Process an URL sent by browser extension.'''

    if not await discord.authorized:
        # Unauthorized, return status 401
        response = 'Not logged in'
        status = 401 if request.method == 'POST' else 200
    else:
        # Successful response :)
        response = 'Success!'
        status = 200

        if request.method =='POST':
            # Receive path from request
            path = (await request.data).decode('utf-8')

            # Create path handler object and build player data
            user = await discord.fetch_user()
            ph = _PathHandler()
            ok, invite_code = await ph.build_handler(user, path)
            if not ok and not invite_code:
                response = 'Not a level page'
                status = 404
            elif not ok and invite_code and 'process-beta' in request.url:
                # User is not currently member of riddle's guild :()
                response = invite_code
                status = 401
            else:
                await ph.build_player_riddle_data()

                # Process received path
                ok = await ph.process()
                if ok:
                    print(('\033[1m[%s]\033[0m Received path \033[1m%s\033[0m '
                            'from \033[1m%s\033[0m#\033[1m%s\033[0m')
                            % (ph.riddle_alias, ph.path, ph.username, ph.disc))
    
    # Return response
    return response, status


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

    async def build_handler(self, user: User, url: str):
        '''Get path from raw URL and get user info from DB.
        
        @param user: Discord user object for logged in player
        @param path: raw URL sent by the extension'''

        # Exclude potential "www." from URL
        url = url.replace('www.', '')

        # Retrieve riddle info from database
        query = 'SELECT * FROM riddles ' \
                'WHERE LOCATE(root_path, :url)'
        values = {'url': url}
        riddle = await database.fetch_one(query, values)
        if not riddle:
            # Page outside of levels, like forum and admin ones
            return False, None

        # Check if user is member of riddle guild
        is_member = await bot_request('is-member-of-guild',
                guild_id=riddle['guild_id'],
                username=user.name, disc=user.discriminator)
        ok = True
        invite_code = None
        if is_member == 'False':
            ok = False
            invite_code = riddle['invite_code']

        # Save basic riddle info
        self.riddle_alias = riddle['alias']
        root_path = riddle['root_path']
        self.unlisted = bool(riddle['unlisted'])
        
        # Save basic user info
        self.username = user.username
        self.disc = user.discriminator

        # Get relative path by removing root portion (and "www.", if present)
        self.path = url.replace('www.', '').replace(root_path, '')

        if self.path[-1] == '/':
            # If a folder itself, add "index.htm" to path's end
            self.path += 'index.htm'
        else:
            # If no extension, append explicit ".htm" to the end
            has_dot = self.path.count('.')
            if not has_dot:
                self.path += '.htm'
        
        return ok, invite_code
    
    async def build_player_riddle_data(self):
        '''Build player riddle data from database,
        creating one if not present yet.'''
        
        async def _get_data():
            '''Get player riddle data.'''
            query = 'SELECT * FROM riddle_accounts ' \
                'WHERE riddle = :riddle AND ' \
                    'username = :name AND discriminator = :disc'
            values = {'riddle': self.riddle_alias,
                    'name': self.username, 'disc': self.disc}
            result = await database.fetch_one(query, values)
            return result

        # Check if player's riddle acount already exists
        result = await _get_data()
        if not result:
            # If not, create a brand new one
            query = 'INSERT INTO riddle_accounts ' \
                    '(riddle, username, discriminator) ' \
                    'VALUES (:riddle, :name, :disc)'
            values = {'riddle': self.riddle_alias,
                    'name': self.username, 'disc': self.disc}
            await database.execute(query, values)
            result = await _get_data()
        
        # Build dict from query result
        self.riddle_account = dict(result)

    async def process(self):
        '''Process level path.
        
        @path: a level path in the current riddle domain'''            
        
        # Check if it's not an txt/image/video/etc
        dot_index = self.path.rfind('.')
        extension = self.path[(dot_index + 1):]
        is_page = 'htm' in extension or 'php' in extension

        if is_page:
            await self._update_counters()

        # Get current level info from DB
        current_name = self.riddle_account['current_level']
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': current_name}
        current_level = await database.fetch_one(query, values)

        if current_level and self.path == current_level['answer']:
            # If user entered a correct and new answer, register completion
            lh = _NormalLevelHandler(current_level, self)
            await lh.register_completion()
        
        # Check if path corresponds to a valid page (non 404)
        query = 'SELECT * FROM level_pages ' \
                'WHERE riddle = :riddle AND path = :path'
        values = {'riddle': self.riddle_alias, 'path': self.path}
        page = await database.fetch_one(query, values)
        if not page or not page['level_name']:
            # Page not found!
            return False
        
        # Get requested page's level info from DB
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': page['level_name']}
        page_level = await database.fetch_one(query, values)
                  
        if current_name != '🏅':
            # Find if current level is solved (either beforehand or not)
            query = 'SELECT * FROM user_levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND level_name = :level ' \
                        'AND completion_time IS NOT NULL'
            values = {'riddle': self.riddle_alias, 
                    'name': self.username, 'disc': self.disc,
                    'level': current_name}
            result = await database.fetch_one(query, values)
            current_solved = (result is not None)
            
            if not current_name or current_solved:
                # Get next level name
                index = current_level['index'] + 1 if current_level else 1
                query = 'SELECT * FROM levels ' \
                        'WHERE riddle = :riddle ' \
                            'AND is_secret IS FALSE AND `index` = :index'
                values = {'riddle': self.riddle_alias, 'index': index}
                result = await database.fetch_one(query, values)
                next_name = result['name'] if result else ''
            
                if page_level['name'] == next_name \
                        and self.path == page_level['path']:
                    # If it's the new level's front page, register progress
                    lh = _NormalLevelHandler(page_level, self)
                    await lh.register_finding()
            
        # Check for secret level pages
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                'AND path = :path'
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

        # if not has_access():
        #     # Forbid user from accessing any level further than permitted
        #     abort(403)
        
        # Get new current level info from DB
        current_name = self.riddle_account['current_level']
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': current_name}
        current_level = await database.fetch_one(query, values)

        # Register into database new page access (if applicable)
        if current_name and (current_name == '🏅' \
                or page_level['index'] <= current_level['index'] + 1 \
                or page_level['is_secret']):
            tnow = datetime.utcnow()
            query = 'INSERT IGNORE INTO user_pages ' \
                    'VALUES (:riddle, :username, :disc, ' \
                        ':level_name, :path, :time)'
            values = {'riddle': self.riddle_alias,
                    'username': self.username, 'disc': self.disc,
                    'level_name': page['level_name'],
                    'path': self.path, 'time': tnow}
            await database.execute(query, values)

            # Check and possibly grant an achievement
            await self._process_cheevo()
        
        return True
    
    async def _update_counters(self):
        '''Update player and riddle hit counters.'''

        # If a normal page, increment player's current hit counter
        query = 'UPDATE riddle_accounts ' \
                'SET cur_hit_counter = cur_hit_counter + 1 ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)

        # Also update riddle global hit counter
        query = 'UPDATE riddles ' \
                'SET hit_counter = hit_counter + 1 ' \
                'WHERE alias = :alias '
        await database.execute(query, {'alias': self.riddle_alias})
    
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
            print('Duplicate cheevo!')
            return

        # Also Update user and global scores
        points = cheevo_ranks[cheevo['rank']]['points']
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'points': points, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)
        if not self.unlisted:
            query = 'UPDATE accounts ' \
                    'SET global_score = global_score + :points ' \
                    'WHERE username = :name AND discriminator = :disc'
            values.pop('riddle')
            await database.execute(query, values)

        # Send request to bot to congratulate member
        await bot_request('unlock', method='cheevo_found',
                alias=self.riddle_alias,
                username=self.username, disc=self.disc,
                cheevo=dict(cheevo), points=points)


class _LevelHandler:
    '''Handler base class for processing levels.'''
    
    # Dict containing level DB data
    level: dict
    
    # Points awarded upon level completion
    points: int
    
    def __init__(self, level: dict, ph: _PathHandler):
        '''Register level DB data and points,
        as well as parent attributes from PH.
        
        @param level: Level DB table row data
        @param ph: The parent's paths handler'''

        self.level = dict(level)
        rank = level['rank']
        self.points = level_ranks[rank]['points']
        
        # Set some attributes from parent caller PH for easier access
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
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'points': self.points, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)
        if not self.unlisted:
            query = 'UPDATE accounts ' \
                    'SET global_score = global_score + :points ' \
                    'WHERE username = :name AND discriminator = :disc'
            values = {'points': self.points,
                    'name': self.username, 'disc': self.disc}
            await database.execute(query, values)


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
                'SET current_level = :name_next, cur_hit_counter = 0 ' \
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
        
        # Check if beating level corresponds to a milestone
        query = 'SELECT * FROM milestones ' \
                'WHERE riddle = :riddle AND level_name = :level_name'
        result = await database.fetch_one(query, values)
        milestone = result['role'] if result else None
        
        # Register level completion in designated table
        time = datetime.utcnow()
        count = self.riddle_account['cur_hit_counter']
        query = 'UPDATE user_levels ' \
                'SET completion_time = :time, page_count = :count ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :level'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level': self.level['name'], 'time': time, 'count': count}
        await database.execute(query, values)
    
        # Bot level beat procedures
        await bot_request('unlock', method='beat',
                alias=self.riddle_alias,
                level=self.level, points=self.points,
                username=self.username, disc=self.disc,
                first_to_solve=first_to_solve, milestone=milestone)
    
        # Get next level (if any)
        index = self.level['index'] + 1
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle ' \
                    'AND is_secret IS FALSE AND `index` = :index'
        values = {'riddle': self.riddle_alias, 'index': index}
        next_level = await database.fetch_one(query, values)
        
        if not next_level:
            # Player has just completed the game :)
            query = 'UPDATE riddle_accounts ' \
                'SET current_level = "🏅" ' \
                'WHERE riddle = :riddle AND ' \
                    'username = :name AND discriminator = :disc'
            values = {'riddle': self.riddle_alias,
                    'name': self.username, 'disc': self.disc}
            await database.execute(query, values)
            
            # Bot game finish procedures
            query = 'SELECT * FROM riddles WHERE alias = :alias'
            values = {'alias': self.riddle_alias}
            result = await database.fetch_one(query, values)
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
