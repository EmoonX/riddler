import json
from urllib.parse import urlparse
from datetime import datetime
from pymysql.err import IntegrityError

from quart import Blueprint, request, jsonify
from quart_discord.models import User

from auth import discord
from ipc import web_ipc
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
async def process_url():
    '''Process an URL sent by browser extension.'''

    response = None
    status = None
    if not await discord.authorized:
        # Unauthorized, return status 401
        response = jsonify({'message': 'Unauthorized'})
        status = 401 if request.method == 'POST' else 200
    else:
        # Receive URLs from request and build list
        s = (await request.data).decode('utf-8')
        url_list = s.split('\n')

        if request.method =='POST':
            # Create paths handler object and build player data
            user = await discord.fetch_user()
            ph = _PathsHandler(user, url_list)
            await ph.build_player_riddle_data()

            # Process all received paths
            for path in ph.paths:
                print(('\033[1m[%s]\033[0m Processing path \033[1m%s\033[0m '
                        'from \033[1m%s\033[0m#\033[1m%s\033[0m')
                        % (ph.riddle_alias, path, ph.username, ph.disc))
                await ph.process(path)
        
        # Successful response :)
        response = jsonify({'message': 'Success!'})
        status = 200
    
    # (Chrome security issues) Allow CORS to be requested from other domains
    if request.referrer:
        ref = request.referrer[:-1]
        response.headers.add('Access-Control-Allow-Origin', ref)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Headers', 'Cookie')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    
    # Return response
    return response, status


class _PathsHandler:
    '''Handler for processing level paths.

    Updates the needed tables on database and request 
    guild changes to be done by bot.'''

    # Alias of riddle hosted on URLs domain
    riddle_alias: str

    # Username and discriminator of logged in player
    username: str
    disc: str

    # Dict containing player's riddle account info from DB
    riddle_account: dict

    # Paths to be processed by handler
    paths: list

    def __init__(self, user: User, url_list: list):
        '''Ṕarse riddle and paths from url list and get user info.
        
        @param url_list: the list of received URLs
        @param user: Discord user object for logged in player'''

        # Set riddle alias based on href domain
        parsed = urlparse(url_list[0])
        domain = parsed.netloc
        self.riddle_alias = 'cipher'
        if 'rnsriddle.com' in domain:
            self.riddle_alias = 'rns'
        elif 'thestringharmony.com' in domain:
            self.riddle_alias = 'string'
        
        # Save basic user info
        self.username = user.username
        self.disc = user.discriminator

        self.paths = []
        for url in url_list:
            # Parse path from url (ignore external pages)
            parsed = urlparse(url)
            path = '/' + parsed.path
            if parsed.netloc != domain or not path:
                continue

            # Remove base folder from path, if any
            if self.riddle_alias == 'cipher':
                path = path.replace('/cipher/', '')
            else:
                path = path.replace('/riddle/', '')
            if not path:
                continue

            if path[-1] == '/':
                # If a folder itself, add "index.htm" to path's end
                path += 'index.htm'
            else:
                # If no extension, force an explicit ".htm" to the end
                has_dot = path.count('.')
                if not has_dot:
                    path += '.htm'
            
            # Add path to list
            self.paths.append(path)
    
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

    async def process(self, path: str):
        '''Process level path.
        
        @path: a level path in the current riddle domain'''            
        
        # Check if it's not an txt/image/video/etc
        dot_index = path.rfind('.')
        extension = path[(dot_index + 1):]
        is_page = 'htm' in extension or 'php' in extension

        if is_page:
            await self._update_counters()

        # Get current level info from DB
        current_name = self.riddle_account['current_level']
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': current_name}
        current_level = await database.fetch_one(query, values)

        if current_level and path == current_level['answer']:
            # If user entered a correct and new answer, register completion
            lh = _NormalLevelHandler(current_level, self)
            await lh.register_completion()
        
        # Check if path corresponds to a valid page (non 404)
        query = 'SELECT * FROM level_pages ' \
                'WHERE riddle = :riddle AND path = :path'
        values = {'riddle': self.riddle_alias, 'path': path}
        page = await database.fetch_one(query, values)
        if not page or not page['level_name']:
            # Page not found!
            return
        
        # Get requested page's level info from DB
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias, 'name': page['level_name']}
        page_level = await database.fetch_one(query, values)
            
        # Get next normal level name (or first)
        if current_name != '🏅':
            index = current_level['index'] + 1 if current_level else 1
            query = 'SELECT * FROM levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND is_secret IS FALSE AND `index` = :index'
            values = {'riddle': self.riddle_alias, 'index': index}
            result = await database.fetch_one(query, values)
            next_name = result['name'] if result else ''
        
            if page_level['name'] == next_name and path == page_level['path']:
                # If it's the new level's front page, register progress
                lh = _NormalLevelHandler(page_level, self)
                await lh.register_finding()
            
        # Check for secret level pages
        query = 'SELECT * FROM levels ' \
                'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                'AND path = :path'
        values = {'riddle': self.riddle_alias, 'path': path}
        secret = await database.fetch_one(query, values)
        if secret:
            # "A secret has been found"
            sh = _SecretLevelHandler(secret, self)
            await sh.register_finding()
        else:
            # Otherwise, check if a secret level was beaten
            query = 'SELECT * FROM levels ' \
                    'WHERE riddle = :riddle AND is_secret IS TRUE ' \
                    'AND answer = :answer'
            values = {'riddle': self.riddle_alias, 'answer': path}
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
                or page_level['index'] <= current_level['index'] \
                or page_level['is_secret']):
            tnow = datetime.utcnow()
            query = 'INSERT IGNORE INTO user_pageaccess ' \
                    'VALUES (:riddle, :username, :disc, ' \
                        ':level_name, :path, :time)'
            values = {'riddle': self.riddle_alias,
                    'username': self.username, 'disc': self.disc,
                    'level_name': page['level_name'],
                    'path': path, 'time': tnow}
            await database.execute(query, values)

            # Check and possibly grant an achievement
            await self._process_cheevo(path)
    
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
        query = 'UPDATE general_info ' \
                'SET hit_counter = hit_counter + 1 ' \
                'WHERE riddle = :riddle '
        await database.execute(query, {'riddle': self.riddle_alias})
    
    async def _process_cheevo(self, path: str):
        '''Grant cheevo and awards if page is an achievement one.'''

        # Check if it's an achievement page
        query = 'SELECT * FROM achievements ' \
                'WHERE riddle = :riddle ' \
                'AND JSON_CONTAINS(paths_json, :path, "$.paths")'
        values = {'riddle': self.riddle_alias, 'path': ('\"%s\"' % path)}
        cheevo = await database.fetch_one(query, values)
        if not cheevo:
            return
        
        paths_json = json.loads(cheevo['paths_json'])
        if 'operator' in paths_json and paths_json['operator'] == 'AND':
            # If an 'AND' operator, all cheevo pages must have been found
            ok = True
            for path in paths_json['paths']:
                query = 'SELECT * FROM user_pageaccess ' \
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

        # Also Update user, country and global scores
        points = cheevo_ranks[cheevo['rank']]['points']
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'points': points, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)
        # cursor.execute("UPDATE countries "
        #         "SET total_score = total_score + %s "
        #         "WHERE alpha_2 = %s",
        #         (points, session['user']['country']))
        query = 'UPDATE accounts ' \
                'SET global_score = global_score + :points ' \
                'WHERE username = :name AND discriminator = :disc'
        values.pop('riddle')
        await database.execute(query, values)

        # Send request to bot to congratulate member
        await web_ipc.request('unlock', method='cheevo_found',
                alias=self.riddle_alias, name=self.username, disc=self.disc,
                cheevo=dict(cheevo), points=points)


class _LevelHandler:
    '''Handler base class for processing levels.'''
    
    # Dict containing level DB data
    level: dict
    
    # Points awarded upon level completion
    points: int

    # User table to be accessed on DB
    table: str
    
    def __init__(self, level: dict, ph: _PathsHandler, table: str):
        '''Register level DB data and points,
        as well as parent attributes from PH.
        
        @param level: Level DB table row data
        @param ph: The parent's paths handler'''

        self.level = dict(level)
        self.table = table
        rank = level['rank']
        self.points = level_ranks[rank]['points']
        
        # Set some attributes from parent caller PH for easier access
        for name in ('riddle_alias', 'username', 'disc', 'riddle_account'):
            attr = getattr(ph, name)
            setattr(self, name, attr)
    
    async def _get_user_level_row(self):
        ''':return: User/level registry from DB.'''

        query = ('SELECT * FROM %s ' % self.table) + \
                'WHERE riddle = :riddle AND username = :name ' \
                'AND discriminator = :disc AND level_name = :level_name'
        values = {'riddle': self.riddle_alias, 
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name']}
        row = await database.fetch_one(query, values)
        return row
    
    async def register_finding(self, method: str):
        '''Bot level finding procedures.
        
        :param method: IPC method name; "advance" or "secret_found",
            whether it's a normal or secret level'''
            
        await web_ipc.request('unlock', method=method,
                alias=self.riddle_alias, level=self.level,
                name=self.username, disc=self.disc)
    
    async def register_completion(self) -> bool:
        '''Register level completion and update all needed tables.
        
        :return: If level has been already completed.'''

        # Check if level has been completed
        row = await self._get_user_level_row()
        if row and row['completion_time']:
            return True

        # Update level-related tables
        await self._update_info()
        return False

    async def _update_info(self):
        '''Update level-related tables.'''

        # Update global user completion count
        query = 'UPDATE levels ' \
                'SET completion_count = completion_count + 1 ' \
                'WHERE riddle = :riddle AND name = :name'
        values = {'riddle': self.riddle_alias,
                'name': self.level['name']}
        await database.execute(query, values)

        # Update user, country and global scores
        query = 'UPDATE riddle_accounts ' \
                'SET score = score + :points ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'points': self.points, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)
        # cursor.execute("UPDATE countries "
        #         "SET total_score = total_score + %s "
        #         "WHERE alpha_2 = %s",
        #         (points, session['user']['country']))
        query = 'UPDATE accounts ' \
                'SET global_score = global_score + :points ' \
                'WHERE username = :name AND discriminator = :disc'
        values = {'points': self.points,
                'name': self.username, 'disc': self.disc}
        await database.execute(query, values)


class _NormalLevelHandler(_LevelHandler):
    '''Handler for normal (non secret) levels.'''

    def __init__(self, level: dict, ph: _PathsHandler):
        super().__init__(level, ph, 'user_levelcompletion')
    
    async def register_finding(self):
        '''Increment player level upon reaching level's front page.'''
        
        # Update player's current_level and reset their page count
        query = 'UPDATE riddle_accounts ' \
                'SET current_level = :name_next, cur_hit_counter = 0 ' \
                'WHERE riddle = :riddle AND ' \
                    'username = :name AND discriminator = :disc'
        values = {'name_next': self.level['name'], 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        self.riddle_account['current_level'] = self.level['name']
        await database.execute(query, values)
        
        # Send request to bot for unlocking channel    
        await super().register_finding('advance')

    async def register_completion(self):
        '''Register normal level completion and update all needed tables.'''

        # Do base completion procedures first
        completed = await super().register_completion()
        if completed:
            return
        
        # Check if player was first to solve level
        query = 'SELECT * FROM user_levelcompletion ' \
                'WHERE riddle = :riddle AND level_name = :level_name'
        values = {'riddle': self.riddle_alias,
                'level_name': self.level['name']}
        result = await database.fetch_one(query, values)
        first_to_solve = (result is None)
        
        # Register level completion in designated table
        time = datetime.utcnow()
        count = self.riddle_account['cur_hit_counter']
        query = 'INSERT INTO user_levelcompletion ' \
                '(riddle, username, discriminator, ' \
                    'level_name, completion_time, page_count) ' \
                'VALUES (:riddle, :name, :disc, :level_name, :time, :count)'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name'],
                'time': time, 'count': count}
        await database.execute(query, values)
    
        # Bot level beat procedures
        await web_ipc.request('unlock', method='beat',
                alias=self.riddle_alias,
                level=self.level, points=self.points,
                name=self.username, disc=self.disc,
                first_to_solve=first_to_solve)
    
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
            await web_ipc.request('unlock', method='game_completed',
                    alias=self.riddle_alias,
                    name=self.username, disc=self.disc)

        # Update countries table too
        # cursor.execute("UPDATE countries "
        #         "SET highest_level = GREATEST(highest_level, %s) "
        #         "WHERE alpha_2 = %s",
        #         (current_level, session['user']['country']))
        # if int(current_level) > get_level_count()[0]:
        #     cursor.execute("UPDATE countries "
        #             "SET winners_count = winners_count + 1 "
        #             "WHERE alpha_2 = %s",
        #             (session['user']['country'],))


class _SecretLevelHandler(_LevelHandler):
    '''Handler for secret levels.'''

    def __init__(self, level: dict, ph: _PathsHandler):
        super().__init__(level, ph, 'user_secrets')

    async def register_finding(self):
        '''Register new secret if not yet been found.'''

        # Register on  if not yet been found
        row = await self._get_user_level_row()
        if row:
            return
        
        time = datetime.utcnow()
        query = 'INSERT INTO user_secrets ' \
                '(riddle, username, discriminator, ' \
                    'level_name, find_time) ' \
                'VALUES (:riddle, :name, :disc, ' \
                    ':level_name, :time)'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name'], 'time': time}
        await database.execute(query, values)
        
        # Send request to bot for unlocking channel    
        await super().register_finding('secret_found')
        
    async def register_completion(self):
        '''Register normal level completion and update all needed tables.'''

        # Do base completion procedures first
        completed = await super().register_completion()
        if completed:
            return
        
        # Check if player was first to solve level
        query = 'SELECT * FROM user_secrets ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc'
        values = {'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc}
        result = await database.fetch_one(query, values)
        first_to_solve = (result is None)
        
        # Register level completion in designated table
        time = datetime.utcnow()
        query = 'UPDATE user_secrets ' \
                'SET completion_time = :time ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                    'AND level_name = :level_name'
        values = {'time': time, 'riddle': self.riddle_alias,
                'name': self.username, 'disc': self.disc,
                'level_name': self.level['name']}
        await database.execute(query, values)
        
        # Bot secret solve procedures
        await web_ipc.request('unlock', method='secret_solve',
                alias=self.riddle_alias,
                level=self.level, points=self.points,
                name=self.username, disc=self.disc,
                first_to_solve=first_to_solve)
