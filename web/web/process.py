from datetime import datetime
import json
import re
from pymysql.err import IntegrityError

from quart import Blueprint, request, jsonify
from quart_discord.models import User

from auth import discord
from riddle import level_ranks, cheevo_ranks
from webclient import bot_request
from util.db import database

# Create app blueprint
process = Blueprint('process', __name__)


@process.route('/process', methods=['POST', 'OPTIONS'])
async def process_url(username=None, disc=None, url=None):
    '''Process an URL sent by browser extension.'''

    # Flag function call as automated or not
    auto = (url is not None)

    if not auto and not await discord.authorized:
        # Not logged in
        status = 401 if request.method == 'POST' else 200
        return 'Not logged in', status

    if auto or request.method == 'POST':
        # Receive url and status code from request
        if not auto:
            url = (await request.data).decode('utf-8')
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
        ph = await _PathHandler.build(user, url, status_code)
        if not ph:
            # Not inside root path (e.g forum or admin pages)
            return 'Not part of root path', 403
        ok = await ph.build_player_riddle_data()
        if not ok:
            return 'Banned player', 403

        # Process received path
        ok = await ph.process()
        if not ok and status_code != 404:
            # Page exists, but not (yet?) a level one
            message, status_code = 'Not a level page', 412
            await ph.check_and_register_missing_page()

        # Log received path with timestamp
        tnow = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if status_code == 404:
            # Page not found
            print(
                f"\033[1m[{ph.riddle_alias}]\033[0m "
                f"Received path \033[3m\033[9m{ph.path}\033[0m\033[0m from "
                    f"\033[1m{ph.username}\033[0m#\033[1m{ph.disc}\033[0m "
                    f"({tnow})"
            )
            message, status_code = 'Page not found', 404
        elif status_code != 412:
            # Valid level page
            print(
                f"\033[1m[{ph.riddle_alias}]\033[0m "
                f"Received path \033[3m\033[1m{ph.path}\033[0m\033[0m "
                    f"\033[1m({ph.path_level})\033[0m from "
                    f"\033[1m{ph.username}\033[0m#\033[1m{ph.disc}\033[0m "
                    f"({tnow})"
            )
            response = jsonify(
                riddle=ph.riddle_alias, levelName=ph.path_level, path=ph.path
            )
            return response

    # All clear
    return message, status_code


class _PathHandler:
    '''Handler for processing level paths.'''

    riddle_alias: str
    '''Alias of riddle hosted on URL domain.'''

    unlisted: bool
    '''If riddle is currently unlisted.'''

    username: str
    '''Username of logged in player.'''

    disc: str
    '''Discriminator of logged in player.'''

    riddle_account: dict
    '''Dict containing player's riddle account info from DB.'''

    path: str
    '''Path to be processed by handler.'''

    path_level: str
    '''Level to which path corresponds to, or `None` if N/A.'''

    status_code: int
    '''Real status code of requested page (either 200 or 404).'''

    @classmethod
    async def build(cls, user: User, url: str, status_code: str) -> object:
        '''Build handler from DB's user info and URL info.'''

        # Get riddle and path info from URL
        riddle, path = await cls._get_riddle_and_path(url)

        # Save basic riddle + user info
        self = cls()
        self.riddle_alias = riddle['alias']
        self.unlisted = bool(riddle['unlisted'])
        self.username = user.name
        self.disc = user.discriminator

        # Save relative path and status code
        self.path = path
        self.status_code = status_code

        # Ignore content (GET variables) after '?'
        self.path = self.path.split('?', 1)[0]

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

        return self

    @staticmethod
    async def _get_riddle_and_path(url: str) -> dict:
        '''Retrieve riddle and path from given URL.'''

        # Domain and path for URL
        aux = url.split('/', 3)[2:]
        url_domain = aux[0].replace('www.', '')
        url_path = '/' + aux[1]

        query = 'SELECT * FROM riddles'
        riddles = await database.fetch_all(query)
        for riddle in riddles:
            # Riddle domain and root path
            aux = (riddle['root_path'] + '/').split('/', 3)[2:]
            riddle_domain = aux[0].replace('www.', '')
            riddle_path = '/' + aux[1]
            if riddle_domain == url_domain:
                # Build relative path from root
                url_path = (
                    '/' + url_path[len(riddle_path):]
                        if url_path.startswith(riddle_path)
                    else ('../' * (riddle_path.count('/') - 1)) + url_path
                )
                return riddle, url_path

    async def build_player_riddle_data(self) -> bool:
        '''Build player riddle data from DB, creating it if nonexistent.'''

        # Ignore progress for banned players :)
        query = '''
            SELECT * FROM accounts
            WHERE username = :username AND discriminator = :disc
        '''
        values = {'username': self.username, 'disc': self.disc}
        banned = await database.fetch_val(query, values, 'banned')
        if banned:
            return False

        async def _get_data():
            '''Get player riddle data.'''
            query = '''
                SELECT * FROM riddle_accounts
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc
            '''
            result = await database.fetch_one(query, values)
            return result

        # Check if player's riddle acount already exists
        values['riddle'] = self.riddle_alias
        riddle_account = await _get_data()
        if not riddle_account:
            # If negative, create a brand new one
            query = '''
                INSERT IGNORE INTO riddle_accounts
                    (riddle, username, discriminator)
                VALUES (:riddle, :username, :disc)
            '''
            await database.execute(query, values)
            riddle_account = await _get_data()

        # Update current riddle being played
        query = '''
            UPDATE accounts SET current_riddle = :riddle
            WHERE username = :username AND discriminator = :disc
        '''
        await database.execute(query, values)

        # Build dict from query result
        self.riddle_account = dict(riddle_account)
        return True

    async def process(self):
        '''Process level path.'''

        # Search for unlocked and unbeaten levels on DB
        query = '''
            SELECT is_secret, `index`, name, latin_name,
                answer, `rank`, discord_name
            FROM user_levels INNER JOIN levels
            ON levels.riddle = user_levels.riddle
                AND levels.name = user_levels.level_name
            WHERE user_levels.riddle = :riddle
                AND username = :username AND discriminator = :disc
                AND completion_time IS NULL
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.username, 'disc': self.disc
        }
        current_levels = await database.fetch_all(query, values)

        # Register completion if path is answer to any of the found levels
        for level in current_levels:
            if (
                # Single + multi-answer support
                self.path == level['answer'] or
                f'"{self.path}"' in level['answer']
            ):
                lh = _LevelHandler(level, self)
                await lh.register_completion()
                break

        # Check if page is a normal one (i.e not txt/image/video/etc)
        dot_index = self.path.rfind('.')
        extension = self.path[(dot_index + 1):]
        is_normal_page = extension in ('htm', 'html', 'php')

        # Check if path corresponds to a valid level page (non 404)
        query = '''
            SELECT * FROM level_pages
            WHERE riddle = :riddle AND path = :path
        '''
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
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle AND name = :level_name
        '''
        values = {'riddle': self.riddle_alias, 'level_name': self.path_level}
        level = await database.fetch_one(query, values)

        # Search for a level which has the current path as front
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle
                AND (`path` = :path OR `path` LIKE "%\":path\"%")
        '''
        values = {'riddle': self.riddle_alias, 'path': self.path}
        result = await database.fetch_one(query, values)
        if result:
            await self._check_and_unlock(level)

        # If the currently being visited level has not
        # been unlocked yet, ignore it for access counting purposes
        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle AND level_name = :level_name
                AND username = :username AND discriminator = :disc
        '''
        values = {
            'riddle': self.riddle_alias, 'level_name': self.path_level,
            'username': self.username, 'disc': self.disc,
        }
        is_unlocked = await database.fetch_one(query, values)
        if is_unlocked:
            # Mark level currently being visited in `last_visited_level` field
            query = '''
                UPDATE riddle_accounts SET last_visited_level = :level_name
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc
            '''
            await database.execute(query, values)

        # If a normal page, update all hit counters
        if is_normal_page:
            await self._update_hit_counters()

        # Register new page access in database (if applicable)
        await self._process_page()

        return True

    async def _check_and_unlock(self, level: dict):
        '''Check if a level hasn't been AND can be unlocked.
        If positive, proceeds with unlocking procedures.'''

        # Check if level has already been unlocked beforehand
        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle AND level_name = :level_name
                AND username = :username AND discriminator = :disc
        '''
        values = {
            'riddle': self.riddle_alias, 'level_name': level['name'],
            'username': self.username, 'disc': self.disc,
        }
        already_unlocked = await database.fetch_one(query, values)
        if already_unlocked:
            return

        # Check if all required levels are already beaten
        query = '''
            SELECT * FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        other_values = {
            'riddle': self.riddle_alias, 'level_name': level['name']
        }
        level_requirements = await database.fetch_all(query, other_values)
        for req in level_requirements:
            completion_cond = (
                '' if req['finding_is_enough']
                else 'AND completion_time IS NOT NULL'
            )
            query = f"""
                SELECT * FROM user_levels
                WHERE riddle = :riddle AND level_name = :level_name
                    AND username = :username AND discriminator = :disc
                    {completion_cond}
            """
            values['level_name'] = req['requires']
            req_satisfied = await database.fetch_one(query, values)
            if not req_satisfied:
                return

        # A new level has been found!
        lh = _LevelHandler(level, self)
        await lh.register_finding()

    async def _update_hit_counters(self):
        '''Update player, riddle and level hit counters.'''

        # Update player/riddle hit counters
        query = '''
            UPDATE riddle_accounts SET hit_counter = hit_counter + 1
            WHERE riddle = :riddle
                AND username = :username AND discriminator = :disc
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.username, 'disc': self.disc
        }
        await database.execute(query, values)
        query = '''
            UPDATE riddles SET hit_counter = hit_counter + 1
            WHERE alias = :alias
        '''
        await database.execute(query, {'alias': self.riddle_alias})

        # Check last level visited by player (which can be the current).
        # All subsequent 404 pages are counted as part of given level,
        # until player visits a new valid level page.
        query = '''
            SELECT * FROM riddle_accounts
            WHERE riddle = :riddle
                AND username = :username AND discriminator = :disc
        '''
        last_visited_level = await database.fetch_val(
            query, values, 'last_visited_level'
        )
        if last_visited_level:
            # Increment completion access count for unbeaten levels
            # (if level has already been completed, nothing happens).
            query = '''
                UPDATE user_levels
                SET completion_hit_counter = completion_hit_counter + 1
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc
                    AND level_name = :level_name AND completion_time IS NULL
            '''
            values['level_name'] = last_visited_level
            await database.execute(query, values)

    async def update_score(self, points: int):
        '''Record player score increase, by given points, in DB.'''

        # Increase player's riddle score
        query = '''
            UPDATE riddle_accounts
            SET score = score + :points,
                recent_score = recent_score + :points
            WHERE riddle = :riddle
                AND username = :username AND discriminator = :disc
        '''
        values = {
            'points': points, 'riddle': self.riddle_alias,
            'username': self.username, 'disc': self.disc
        }
        await database.execute(query, values)

        # Increase global score (unless riddle is unlisted)
        if not self.unlisted:
            query = '''
                UPDATE accounts
                SET global_score = global_score + :points,
                    recent_score = recent_score + :points
                WHERE username = :username AND discriminator = :disc
            '''
            values.pop('riddle')
            await database.execute(query, values)

    async def _process_page(self):
        # Check if all required levels have been found
        query = '''
            SELECT * FROM level_requirements req
            WHERE riddle = :riddle AND level_name = :level_name
                AND requires NOT IN (
                    SELECT level_name FROM user_levels ul
                    WHERE req.riddle = ul.riddle
                        AND username = :username AND discriminator = :disc
                )
        '''
        base_values = {
            'riddle': self.riddle_alias,
            'username': self.username, 'disc': self.disc,
        }
        values = base_values | {'level_name': self.path_level}
        result = await database.fetch_one(query, values)
        has_all_requirements = result is None
        if not has_all_requirements:
            return

        # Try to insert new page in `user_pages`
        tnow = datetime.utcnow()
        query = '''
            INSERT INTO user_pages VALUES (
                :riddle, :username, :disc, :level_name, :path, :time
            )
        '''
        values = values | {'path': self.path, 'time': tnow}
        try:
            await database.execute(query, values)

            # Increment player's riddle page count and find time
            query = '''
                UPDATE riddle_accounts
                SET page_count = page_count + 1, last_page_time = :time
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc
            '''
            values = base_values | {'time': tnow}
            await database.execute(query, values)

        except IntegrityError:
            # Page's already there, so no increments
            pass

        # Check and possibly grant an achievement
        await self._process_cheevo()

    async def _process_cheevo(self):
        '''Grant cheevo and awards if page is an achievement one.'''

        # Check if it's an achievement page
        query = '''
            SELECT * FROM achievements
            WHERE riddle = :riddle
                AND JSON_CONTAINS(paths_json, :path, "$.paths")
        '''
        values = {'riddle': self.riddle_alias, 'path': (f"\"{self.path}\"")}
        cheevo = await database.fetch_one(query, values)
        if not cheevo:
            return

        paths_json = json.loads(cheevo['paths_json'])
        if 'operator' in paths_json and paths_json['operator'] == 'AND':
            # If an 'AND' operator, all cheevo pages must have been found
            ok = True
            for path in paths_json['paths']:
                query = '''
                    SELECT * FROM user_pages
                    WHERE riddle = :riddle
                        AND username = :username AND discriminator = :disc
                        AND path = :path
                '''
                values = {
                    'riddle': self.riddle_alias,
                    'username': self.username, 'disc': self.disc, 'path': path
                }
                page_found = await database.fetch_one(query, values)
                if not page_found:
                    ok = False
                    break
            if not ok:
                return

        # If positive, add it to user's collection
        time = datetime.utcnow()
        query = '''
            INSERT INTO user_achievements
            VALUES (:riddle, :username, :disc, :title, :time)
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.username, 'disc': self.disc,
            'title': cheevo['title'], 'time': time
        }
        try:
            await database.execute(query, values)
            print(
                f"> \033[1m[{self.riddle_alias}]\033[0m "
                f"\033[1m{self.username}#{self.disc}\033[0m "
                    f"got cheevo \033[1m{cheevo['title']}\033[0m!"
            )
        except IntegrityError:
            return

        # Also update user and global scores
        points = cheevo_ranks[cheevo['rank']]['points']
        await self.update_score(points)

        # Request bot to congratulate member
        await bot_request(
            'unlock', method='cheevo_found',
            alias=self.riddle_alias, username=self.username, disc=self.disc,
            cheevo=dict(cheevo), points=points, page=self.path
        )

    async def check_and_register_missing_page(self):
        '''Check and possibly register non-level-associated
        page (which necessarily came from a valid request).'''

        # Record found page and respective user
        tnow = datetime.utcnow()
        query = '''
            INSERT INTO found_pages
                (riddle, `path`, username, discriminator, access_time)
            VALUES (:riddle, :path, :username, :disc, :time)
        '''
        values = {
            'riddle': self.riddle_alias, 'path': self.path,
            'username': self.username, 'disc': self.disc, 'time': tnow,
        }
        try:
            await database.execute(query, values)
            print(
                f"> \033[1m[{self.riddle_alias}]\033[0m "
                f"Found new page \033[1m{self.path}\033[0m "
                    f"by \033[1m{self.username}#{self.disc}\033[0m "
                    f"({tnow})"
            )
            # Register page as a new one (with NULL level)
            query = '''
                INSERT INTO level_pages (riddle, `path`)
                VALUES (:riddle, :path)
            '''
            values = {'riddle': self.riddle_alias, 'path': self.path}
            await database.execute(query, values)

        except IntegrityError:
            pass


class _LevelHandler:
    '''Handler class for processing levels.'''

    level: dict
    '''Level DB data.'''

    points: int
    '''Points awarded upon level completion.'''

    ph: _PathHandler
    '''Reference to parent caller PH.'''

    def __init__(self, level: dict, ph: _PathHandler):
        '''Register level DB data and points,
        as well as parent attributes from PH.'''
        rank = level['rank']
        self.level = dict(level)
        self.points = level_ranks[rank]['points']
        self.ph = ph

    async def register_finding(self):
        '''Increment player level upon reaching level's front page.'''

        # Record it on user table with current time
        tnow = datetime.utcnow()
        query = '''
            INSERT INTO user_levels
                (riddle, username, discriminator, level_name, find_time)
            VALUES (:riddle, :username, :disc, :level_name, :time)
        '''
        values = {
            'riddle': self.ph.riddle_alias,
            'username': self.ph.username, 'disc': self.ph.disc,
            'level_name': self.level['name'], 'time': tnow
        }
        await database.execute(query, values)

        # Call bot unlocking procedure
        await bot_request(
            'unlock', method='advance',
            alias=self.ph.riddle_alias, level=self.level,
            username=self.ph.username, disc=self.ph.disc
        )
        if (
            not self.level['is_secret']
            and self.ph.riddle_account['current_level'] != '🏅'
        ):
            # Update player's current_level
            # (only if riddle hasn't been finished yet)
            query = '''
                UPDATE riddle_accounts SET current_level = :name_next
                WHERE riddle = :riddle AND
                    username = :username AND discriminator = :disc
            '''
            values = {
                'riddle': self.ph.riddle_alias,
                'username': self.ph.username, 'disc': self.ph.disc,
                'name_next': self.level['name'],
            }
            await database.execute(query, values)
            self.ph.riddle_account['current_level'] = self.level['name']

    async def register_completion(self) -> bool:
        '''Register level completion and update all needed tables.
        Return `true` if level is unlocked AND yet to be completed.'''

        # Check if level is unlocked AND unbeaten
        row = await self._get_user_level_row()
        if not row or row['completion_time']:
            return False

        # Register level completion in designated table
        tnow = datetime.utcnow()
        query = '''
            UPDATE user_levels SET completion_time = :time
            WHERE riddle = :riddle
                AND username = :username AND discriminator = :disc
                AND level_name = :level
        '''
        values = {
            'riddle': self.ph.riddle_alias,
            'username': self.ph.username, 'disc': self.ph.disc,
            'level': self.level['name'], 'time': tnow,
        }
        await database.execute(query, values)

        # Bot level beat procedures
        await bot_request(
            'unlock', method='beat',
            alias=self.ph.riddle_alias, level=self.level,
            username=self.ph.username, disc=self.ph.disc,
            points=self.points, first_to_solve=False
        )
        # Check if level just completed is the _final_ one
        query = 'SELECT * FROM riddles WHERE alias = :riddle'
        values = {'riddle': self.ph.riddle_alias}
        final_name = await database.fetch_val(query, values, 'final_level')
        if self.level['name'] == final_name:
            # Player has just completed the game :)
            query = '''
                UPDATE riddle_accounts SET current_level = "🏅"
                WHERE riddle = :riddle
                    AND username = :username AND discriminator = :disc
            '''
            values |= {'username': self.ph.username, 'disc': self.ph.disc}
            await database.execute(query, values)
            await bot_request(
                'unlock', method='game_completed',
                alias=self.ph.riddle_alias,
                username=self.ph.username, disc=self.ph.disc
            )
        # Update level-related tables
        await self._update_info()

        return True

    async def _get_user_level_row(self):
        '''Return user/level record from DB.'''

        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle AND level_name = :level_name
                AND username = :username AND discriminator = :disc
        '''
        values = {
            'riddle': self.ph.riddle_alias, 'level_name': self.level['name'],
            'username': self.ph.username, 'disc': self.ph.disc,
        }
        row = await database.fetch_one(query, values)
        return row

    async def _update_info(self):
        '''Update level-related tables.'''

        # Update global user completion count
        query = '''
            UPDATE levels SET completion_count = completion_count + 1
            WHERE riddle = :riddle AND name = :level_name
        '''
        values = {
            'riddle': self.ph.riddle_alias, 'level_name': self.level['name']
        }
        await database.execute(query, values)

        # Update user and global scores
        await self.ph.update_score(self.points)
