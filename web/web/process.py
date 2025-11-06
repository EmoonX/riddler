from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Self
from urllib.parse import SplitResult, parse_qsl, urljoin, urlsplit, urlunsplit

from quart import Blueprint, request, jsonify
from quartcord.models import User
import requests

from auth import discord
from credentials import (
    get_path_credentials,
    has_unlocked_path_credentials,
    process_credentials,
)
from get import get_user_riddle_data
from inject import get_riddle, get_riddles
from levels import get_pages
from players.account import is_user_incognito
from riddles import level_ranks, cheevo_ranks
from util.db import database
from util.riddle import has_player_mastered_riddle
from webclient import bot_request

# Create app blueprint
process = Blueprint('process', __name__)


@process.post('/process')
async def process_url(
    username: str | None = None,
    url: str | None = None,
    admin: bool = False,
    status_code: int | None = None,
):
    '''Process URL (usually) sent by the browser extension.'''

    # Time 
    tnow = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Flag function call as automated or not
    auto = url is not None

    if not auto and not await discord.authorized:
        # Not logged in
        status_code = 401 if request.method == 'POST' else 200
        return 'Not logged in', status_code

    # Retrieve url, headers and status code from request
    if not auto:
        user = await discord.get_user()
        url = (await request.data).decode('utf-8')
        if content_location := request.headers.get('Content-Location'):
            print(content_location)
            url = urljoin(url, content_location)
    else:
        user = lambda: None
        setattr(user, 'name', username)
    location = request.headers.get('Location')
    request_type = request.headers.get('Type')
    if not status_code:
        status_code = int(request.headers.get('Statuscode', 200))

    # Create path handler object and build player data
    ph = await _PathHandler.build(
        user, url, status_code, request_type, location
    )
    if admin:
        return (ph.riddle_alias, ph.path) if ph else (None, None)
    if not ph:
        # TODO
        # Not inside root path (e.g forum or admin pages)
        print(f"??? {url} ???")
        if admin:
            return url
        return 'Not part of root path', 412

    # Create/fetch riddle account data
    await ph.build_player_riddle_data()

    # Process received credentials (possibly none)
    riddle = await get_riddle(ph.riddle_alias)
    ok = await process_credentials(riddle, ph.path, ph.credentials, status_code)
    path_credentials = await get_path_credentials(ph.riddle_alias, ph.path)
    if not ok:
        return jsonify({
            'message': 'Wrong or missing user credentials',
            'riddle': ph.riddle_alias,
            'credentialsPath': path_credentials['path'],
            'realm': path_credentials['realm'],
        }), 403
    if ph.short_run:
        return jsonify({
            'message':
                f"Trivial auto-redirect ({status_code}); "
                'skipping path processing',
            'riddle': ph.riddle_alias
        }), 202

    # Process received path
    response_code = await ph.process()
    formatted_path = ph.path
    if ph.removed:
        formatted_path = f"\033[9m{formatted_path}\033[0m"
    if ph.path_alias_for:
        # Just an alias; if valid/accessible, process canonical path up next
        formatted_path += f"\033[0m (alias for \033[3m{ph.path_alias_for})"
        if response_code not in [403, 410]:
            ph.path = ph.path_alias_for
            ph.path_alias_for = None
            if await ph.process() == 201:
                # Signal 201 if either of the paths is new for the user
                response_code = 201

    tnow = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    match response_code:
        case 403:
            # Page exists, but user doesn't have the requirements for it yet
            print(
                f"\033[1m[{ph.riddle_alias}]\033[0m "
                f"Received locked path \033[3m{formatted_path}\033[0m "
                f"({ph.path_level}) "
                f"from \033[1m{ph.user.name}\033[0m "
                f"({tnow})"
            )
            return jsonify({
                'message': 'Locked level page',
                'riddle': ph.riddle_alias
            }), 403
        case 404:
            # Plain folder without index (403), or page not found (300/404)
            print(
                f"\033[1m[{ph.riddle_alias}]\033[0m "
                f"Received path \033[3m\033[9m{formatted_path}\033[0m\033[0m "
                f"from \033[1m{ph.user.name}\033[0m "
                f"({tnow})"
            )
            return jsonify({
                'message': 'Page not found',
                'riddle': ph.riddle_alias
            }), 404
        case 410:
            # Faulty 404s (e.g missing `/favicon.ico`); avoid polluting logs
            return jsonify({
                'message': 'Page intentionally discarded',
                'riddle': ph.riddle_alias
            }), 410
        case 412:
            # Page exists, but not a level one (yet?)
            return jsonify({
                'message': 'Not a level page',
                'riddle': ph.riddle_alias
            }), 412

    # Valid reachable level page
    # (201 if first access from user, 200 otherwise)
    print(
        f"\033[1m[{ph.riddle_alias}]\033[0m "
        f"Received {'removed ' if ph.removed else ''}path "
        f"\033[3m\033[1m{formatted_path}\033[0m\033[0m "
        f"\033[1m({ph.path_level or '\033[0;3mspecial\033[1m'})\033[0m "
        f"from \033[1m{ph.user.name}\033[0m "
        f"({tnow})"
    )
    data = {
        'riddle': ph.riddle_alias,
        'setName': ph.path_level_set,
        'levelName': ph.path_level,
        'path': ph.path,
        'riddleData': await get_user_riddle_data(ph.riddle_alias, as_json=False),
        'pagesData': await get_pages(ph.riddle_alias, as_json=False),
    }
    if await has_unlocked_path_credentials(
        ph.riddle_alias, user, path_credentials['path']
    ):
        data |= {'unlockedCredentials': path_credentials}

    return jsonify(data), response_code


class _PathHandler:
    '''Handler for processing level paths.'''

    riddle_alias: str
    '''Alias of riddle hosted on URL domain.'''

    unlisted: bool
    '''Whether riddle is currently unlisted or not.'''

    user: User
    '''Discord `User` object of logged in player.'''

    riddle_account: dict
    '''Dict containing player's riddle account info from DB.'''

    path: str
    '''Path to be processed by handler.'''

    path_level: str | None
    '''Level containing the visited path, or `None` if N/A.'''

    path_level_set: str | None
    '''Level set containing the path's level, or `None` if N/A.'''

    path_alias_for: str | None
    '''Canonical path for the visited one, when the latter is just an alias.'''

    credentials: tuple[str, str]
    '''HTTP basic auth URL-embedded credentials.'''

    status_code: int
    '''Real status code of requested page (either 200 or 404).'''

    @classmethod
    async def build(
        cls,
        user: User,
        url: str,
        status_code: int,
        request_type: str | None = None,
        location: str | None = None,
    ) -> Self | None:
        '''Build handler from DB's user info and URL info.'''

        # Parse and save basic data + status code
        self = cls()
        await self._parse_riddle_data_from_url(url)
        if not self.riddle:
            return None
        self.user = user
        self.path = self.raw_path
        self.status_code = status_code

        # Always ignore occurrences of consecutive slashes
        self.path = re.sub('/{2,}', '/', self.path)

        self.short_run = False
        if status_code in [301, 302, 303, 307, 308]:
            # Handle sufficiently trivial redirects (regardless of 30x semantics)
            full_location = urljoin(url, location)
            ph_to = await cls.build(self.user, full_location, 418)
            if ph_to and ph_to.riddle_alias == self.riddle_alias:
                self.short_run = is_trivial_redirect(self.path, ph_to.path)

        if 200 <= status_code < 400 and not self.short_run:
            # Valid non-trivial path; format it in accordance to the guidelines
            await self._format_and_sanitize_path()

        # Mark whether page came from actual top-level navigation
        self.navigated = request_type == 'main_frame'

        # If applicable, retrieve path alias info
        query = '''
            SELECT alias_for FROM level_pages
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': self.riddle_alias, 'path': self.path}
        self.path_alias_for = await database.fetch_val(query, values)

        return self

    async def _parse_riddle_data_from_url(self, url: str):
        '''Retrieve riddle, path and (possibly) credentials info from URL.'''

        # Parse URL into its significant parts
        parsed_url = urlsplit(
            url.replace('://www.', '://').replace('@www.', '@')
        )

        def _get_relative_path(parsed_root: SplitResult) -> str:
            '''Build relative path from root (with "../"s if needed).''' 
            root_segments = parsed_root.path.split('/')
            if root_segments[-1] == '*':
                root_segments.pop()
            url_segments = parsed_url.path.split('/')
            smallest_len = idx = min(len(root_segments), len(url_segments))
            for i in range(smallest_len):
                if root_segments[i] != url_segments[i]:
                    idx = i
                    break
            suffix_tokens = url_segments[idx:] if any(url_segments) else []
            parent_count = len(root_segments[idx:])
            path = f"/{'/'.join((['..'] * parent_count) + suffix_tokens)}"
            return path

        def _url_matches_root(parsed_root: SplitResult) -> bool:
            if '*' in urlunsplit(parsed_root):
                # Wildcard root path; ignore host pages outside given pattern
                pattern = (
                    f"{parsed_root.hostname}{parsed_root.path}"
                    .replace('.', r'\.').replace('*', r'.*')
                )
                host_and_path = f"{parsed_url.hostname}{parsed_url.path}"
                return re.fullmatch(pattern, host_and_path)

            # Single root path
            return parsed_root.hostname == parsed_url.hostname

        # Build dict of {root_path: riddle}
        riddles = await get_riddles(unlisted=True)
        root_paths = {}
        for riddle in riddles:
            try:
                for root_path in json.loads(riddle['root_path']):
                    root_paths |= {root_path: riddle}
            except json.decoder.JSONDecodeError:
                root_paths |= {riddle['root_path']: riddle}

        # Search for riddle with matching root path (if any)
        for root_path, riddle in reversed(root_paths.items()):
            parsed_root = urlsplit(root_path.replace('://www.', '://'))
            if _url_matches_root(parsed_root):
                break
        else:
            self.riddle = None
            return

        # Save riddle and parsed URL data
        self.riddle = riddle | {'root_path': root_path}
        self.riddle_alias = riddle['alias']
        self.unlisted = bool(riddle['unlisted'])
        self.parsed_query = dict(parse_qsl(parsed_url.query))
        self.credentials = (
            parsed_url.username or self.parsed_query.get('username') or '',
            parsed_url.password or self.parsed_query.get('password') or '',
        )
        self.raw_query = f"?{parsed_url.query}" if '?' in url else ''
        self.raw_path = _get_relative_path(parsed_root) + self.raw_query

    async def _format_and_sanitize_path(self):
        '''Format and sanitize a valid path to its canonical form.'''

        async def _format(base_path: str):
            '''Format path if suitable (i.e indeed not unique).'''

            async def _request_page(path: str) -> requests.Response:
                '''Build suitable request, send it, and return its response.'''
                url = f"{self.riddle['root_path']}{path}"
                credentials = await get_path_credentials(self.riddle_alias, path)
                if credentials['username'] and credentials['password']:
                    auth = f"{credentials['username']}:{credentials['password']}"
                    url = url.replace('://', f"://{auth}@")
                url = re.sub(r'^([^?]+)[?]$', r'\1?_=', url)  # handle empty query
                cookies = {'s': 'eGNIqq1R'}
                return requests.get(url, cookies=cookies, timeout=5)

            query = '''
                SELECT 1 FROM level_pages
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': self.riddle_alias, 'path': self.path}
            if await database.fetch_val(query, values):
                # Given path is unique and has been recorded before
                return

            # Retrieve given page's hash directly from the website
            res = await _request_page(self.path)
            if not res.ok:
                return
            content_hash = hashlib.md5(res.content).hexdigest()

            query = '''
                SELECT content_hash
                FROM _page_hashes ph
                WHERE riddle = :riddle
                    AND path = COALESCE((
                        SELECT alias_for FROM level_pages lp
                        WHERE ph.riddle = lp.riddle AND path = :path
                    ), :path)
                ORDER BY retrieval_time DESC
                LIMIT 1
            '''
            values = {'riddle': self.riddle_alias, 'path': base_path}
            current_hash = await database.fetch_val(query, values)
            if not current_hash:
                # Base path hasn't been recorded, retrieve it if available
                res = await _request_page(base_path)
                if res.ok:
                    current_hash = hashlib.md5(res.content).hexdigest()

            # Replace path iff both pages are available and the content matches
            if content_hash == current_hash:
                self.path = base_path

        async def _get_base_query_page(main_path: str) -> dict | None:
            '''Find most specific recorded query path from given one, if any.'''

            def _matches(param: str, value: str) -> bool:
                '''Check whether param is present AND matches value (or `*`).'''
                return (
                    param in self.parsed_query and
                    value in [self.parsed_query[param], '*']
                )

            query = """
                SELECT * FROM level_pages
                WHERE riddle = :riddle AND path LIKE :path                
            """
            values = {'riddle': self.riddle_alias, 'path': f"{main_path}?%"}
            query_pages = await database.fetch_all(query, values)
            for query_page in reversed(query_pages):
                query_string = query_page['path'].partition('?')[-1]
                parsed_query = parse_qsl(query_string)                
                if all(_matches(*item) for item in parsed_query):
                    return query_page

            return None

        self.path = self.path.partition('?')[0]
        if self.riddle['html_extension']:
            if self.path.endswith(('/', '/..')):
                # If a folder itself, add trailing "index.htm[l]" etc
                index = f"index.{self.riddle['html_extension']}"
                self.path += index if self.path.endswith('/') else f"/{index}"
            else:
                # If missing the extension, append explicit ".htm[l]" etc
                if not Path(self.path).suffix:
                    self.path += f".{self.riddle['html_extension']}"
        else:
            # Omit superflous slash from extension-less hosts
            self.path = self.path.removesuffix('/') or '/'

        if self.raw_query:
            # '?' in received path; search for fitting base queries
            main_path = self.path
            self.path += self.raw_query
            if base_page := await _get_base_query_page(main_path):
                base_path = base_page['path']
                if base_page['special']:
                    self.path = base_path
                else:
                    await _format(base_path)
            else:
                await _format(f"{main_path}?")
                await _format(main_path)

        # Riddle-specific path formatting
        if self.riddle_alias == 'decifra':
            if not re.search(r'^/[.][.]/', self.path):
                # Sanitize dynamic paths within the `/enigma` directory proper
                await _format(re.sub(r' |(%20)|-|_', '', self.path).lower())
            if match := re.search(r'^/[.][.]/(.*?[.]php)/', self.path):
                await _format(f"/../{match[1]}")
        elif self.riddle_alias == 'hakari':
            # Treat non-static pages as case insensitive, omit trailing '/'
            sub_path = self.path.lower()
            if self.path.endswith('/'):
                sub_path = sub_path[:-1]
            await _format(sub_path)

    async def build_player_riddle_data(self):
        '''Build player riddle data from DB, creating it if nonexistent.'''

        # Possibly create brand new riddle account
        query = '''
            INSERT IGNORE INTO riddle_accounts (riddle, username)
            VALUES (:riddle, :username)
        '''
        values = {'riddle': self.riddle_alias, 'username': self.user.name}
        await database.execute(query, values)
        if await is_user_incognito():
            # Possibly likewise create incognito accounts
            query = '''
                INSERT IGNORE INTO _incognito_riddle_accounts (riddle, username)
                VALUES (:riddle, :username)
            '''
            await database.execute(query, values)
            query = '''
                INSERT IGNORE INTO _incognito_accounts (username)
                VALUES (:username)
            '''
            await database.execute(query, {'username': self.user.name})

        # Fetch player riddle data
        query = '''
            SELECT * FROM riddle_accounts
            WHERE riddle = :riddle AND username = :username
        '''
        self.riddle_account = dict(await database.fetch_one(query, values))
        query = '''
            SELECT current_level FROM _incognito_riddle_accounts
            WHERE riddle = :riddle AND username = :username
        '''
        if await database.fetch_val(query, values) == '🏅':
            # TODO, temp fix
            self.riddle_account['current_level'] = '🏅'

        # Update current riddle being played
        query = '''
            UPDATE accounts SET current_riddle = :riddle
            WHERE username = :username
        '''
        await database.execute(query, values)

    async def process(self) -> bool:
        '''Process level path.'''

        # Fetch page data (if existing)
        query = '''
            SELECT * FROM level_pages
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': self.riddle_alias, 'path': self.path}
        page = dict(await database.fetch_one(query, values) or {})
        self.hidden = bool(page.get('hidden'))
        self.removed = bool(page.get('removed'))
        self.special = bool(page.get('special'))

        if answer_level := await self._find_level_being_solved():
            # Path is a (non removed) answer for an unsolved level
            lh = _LevelHandler(answer_level, self)
            await lh.register_completion()

        if not page:
            if self.status_code in [300, 403, 404]:
                # 404-like (and not e.g unlisted page);
                # should still increment all hit counters
                await self._update_hit_counters()

                return 404

            # Actual new unlisted page; register it
            await self._register_new_unlisted_page()

        if not page.get('level_name'):
            if not self.special:
                if self.removed:
                    return 410
                return 412
        
            # Look out for "special" achievements that aren't part of any level
            await self._process_achievement()

        # Get requested page's level info from DB
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle AND name = :level_name
        '''
        values = {'riddle': self.riddle_alias, 'level_name': page['level_name']}
        level = await database.fetch_one(query, values)
        self.path_level = level and level['name']
        self.path_level_set = level and level['level_set']
        if level and level['path']:
            if self.path == level['path'] or f'"{self.path}"' in level['path']:
                # Path points to the level's front page(s), possibly unlock it
                await self._check_and_unlock(level)

        # Check if level has been unlocked (right now or beforehand)
        query = '''
            SELECT 1 FROM user_levels
            WHERE riddle = :riddle
                AND level_name = :level_name
                AND username = :username
        '''
        values = {
            'riddle': self.riddle_alias,
            'level_name': self.path_level,
            'username': self.user.name,
        }
        if await database.fetch_val(query, values):
            if self.navigated:
                # Mark level/page currently being visited
                query = '''
                    UPDATE riddle_accounts
                    SET last_visited_level = :level_name,
                        last_visited_page = :path
                    WHERE riddle = :riddle AND username = :username
                '''
                values |= {'path': self.path}
                await database.execute(query, values)
        elif not await self._are_level_requirements_satisfied(self.path_level):
            # Level not unlocked and can't access yet pages from it
            return 403

        if self.navigated and not self.path_alias_for:
            # Update all hit counters on actual navigation
            await self._update_hit_counters()

        # Register new page access in database (if applicable)
        is_new_page = await self._process_page()

        # Check and possibly grant an achievement
        await self._process_achievement()

        return 201 if is_new_page else 200

    async def _find_level_being_solved(self) -> dict | None:
        '''Find unsolved level given path is an answer for, if any,'''

        if self.removed:
            # Ignore old/removed answers
            return None

        # Search for unlocked but unsolved levels
        query = '''
            SELECT is_secret, `index`, name, latin_name,
                answer, `rank`, discord_name
            FROM user_levels INNER JOIN levels
            ON levels.riddle = user_levels.riddle
                AND levels.name = user_levels.level_name
            WHERE user_levels.riddle = :riddle
                AND username = :username
                AND completion_time IS NULL
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.user.name
        }
        current_levels = await database.fetch_all(query, values)

        # Register completion if path is answer to any of the
        # unlocked levels (bar removed page cases)
        for level in current_levels:
            try:
                is_answer = self.path in json.loads(level['answer'] or '')
            except json.decoder.JSONDecodeError:
                is_answer = self.path == level['answer']
            if is_answer:
                return level

        return None

    async def _are_level_requirements_satisfied(self, level_name: str) -> bool:
        '''
        Check if all required levels are already beaten
        (or, if `finding_is_enough` flag is on, at least found).
        '''

        if self.removed:
            # Always record removed pages
            return True

        query = '''
            SELECT * FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        values = {'riddle': self.riddle_alias, 'level_name': level_name}
        level_requirements = await database.fetch_all(query, values)
        for req in level_requirements:
            completion_cond = (
                '' if req['finding_is_enough']
                else 'AND completion_time IS NOT NULL'
            )
            query = f"""
                SELECT 1 FROM user_levels
                WHERE riddle = :riddle
                    AND level_name = :level_name
                    AND username = :username
                    {completion_cond}
            """
            values = {
                'riddle': self.riddle_alias,
                'level_name': req['requires'],
                'username': self.user.name,
            }
            req_satisfied = await database.fetch_val(query, values)
            if not req_satisfied:
                return False

        return True

    async def _check_and_unlock(self, level: dict):
        '''Check if a level hasn't been AND can be unlocked.
        If positive, proceeds with unlocking procedures.'''

        if self.removed:
            # Ignore removed front pages
            return

        # Check if level has already been unlocked beforehand
        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle
                AND level_name = :level_name
                AND username = :username
        '''
        values = {
            'riddle': self.riddle_alias,
            'level_name': level['name'],
            'username': self.user.name,
        }
        already_unlocked = await database.fetch_one(query, values)
        if already_unlocked:
            return

        # A new level has been found!
        lh = _LevelHandler(level, self)
        await lh.register_finding()

    async def _update_hit_counters(self):
        '''Update player, riddle and level hit counters.'''

        # Update riddle/account hit counters
        query = '''
            UPDATE riddles SET hit_counter = hit_counter + 1
            WHERE alias = :alias
        '''
        await database.execute(query, {'alias': self.riddle_alias})
        query = '''
            UPDATE accounts SET global_hit_counter = global_hit_counter + 1
            WHERE username = :username
        '''
        await database.execute(query, {'username': self.user.name})
        query = '''
            UPDATE riddle_accounts SET hit_counter = hit_counter + 1
            WHERE riddle = :riddle AND username = :username
        '''
        values = {'riddle': self.riddle_alias, 'username': self.user.name}        
        await database.execute(query, values)

        # Check last level visited by player (which can be the current).
        # All subsequent 404 pages are counted as part of given level,
        # until player visits a new valid level page.
        query = '''
            SELECT * FROM riddle_accounts
            WHERE riddle = :riddle AND username = :username
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
                    AND username = :username
                    AND level_name = :level_name
                    AND completion_time IS NULL
            '''
            values['level_name'] = last_visited_level
            await database.execute(query, values)

    async def update_score(self, points: int):
        '''Record player score increase, by given points, in DB.'''

        # Increase player's riddle score
        incognito = await is_user_incognito()
        query = f"""
            UPDATE {
                '_incognito_riddle_accounts' if incognito else 'riddle_accounts'
            }
            SET score = score + :points,
                recent_score = recent_score + :points
            WHERE riddle = :riddle AND username = :username
        """
        values = {
            'points': points,
            'riddle': self.riddle_alias,
            'username': self.user.name,
        }
        await database.execute(query, values)

        # Increase global score (unless riddle is unlisted)
        if not self.unlisted:
            query = f"""
                UPDATE {
                    '_incognito_accounts' if incognito else 'accounts'
                }
                SET global_score = global_score + :points,
                    recent_score = recent_score + :points
                WHERE username = :username
            """
            values.pop('riddle')
            await database.execute(query, values)

    async def _process_page(self) -> bool:
        '''
        Process a valid level page.
        Returns:
            bool: Whether a new user page record was created.
        '''

        tnow = datetime.utcnow()
        query = '''
            INSERT IGNORE INTO user_pages
                (riddle, username, level_name, `path`, access_time, incognito)
            VALUES (:riddle, :username, :level_name, :path, :time, :incognito)
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.user.name,
            'level_name': self.path_level,
            'path': self.path,
            'time': tnow,
            'incognito': await is_user_incognito(),
        }
        if not await database.execute(query, values):
            # Page's already there, so just update it
            # (account for NULL level records granted a priori)
            query = '''
                UPDATE user_pages
                SET level_name = :level_name,
                    last_access_time = :time,
                    incognito_last = :incognito
                WHERE riddle = :riddle
                    AND username = :username
                    AND path = :path
            '''
            await database.execute(query, values)

            return False

        # New page; unless hidden, update player's riddle data
        if not self.hidden:
            query = f"""
                UPDATE {
                    '_incognito_riddle_accounts' if await is_user_incognito()
                    else 'riddle_accounts'
                }
                SET page_count = page_count + 1, last_page_time = :time
                WHERE riddle = :riddle AND username = :username
            """
            del values['level_name']
            del values['path']
            del values['incognito']
            await database.execute(query, values)

        return True

    async def _process_achievement(self):
        '''Grant cheevo and awards if page is an achievement one.'''

        # Check if it's an achievement page
        query = '''
            SELECT * FROM achievements
            WHERE riddle = :riddle
                AND JSON_CONTAINS(paths_json, :path, "$.paths")
        '''
        values = {'riddle': self.riddle_alias, 'path': (f"\"{self.path}\"")}
        achievement = await database.fetch_one(query, values)
        if not achievement:
            return

        paths_json = json.loads(achievement['paths_json'])
        if 'operator' in paths_json and paths_json['operator'] == 'AND':
            # If an 'AND' operator, all cheevo pages must have been found
            for path in paths_json['paths']:
                query = '''
                    SELECT 1 FROM user_pages
                    WHERE riddle = :riddle
                        AND username = :username
                        AND path = :path
                '''
                values = {
                    'riddle': self.riddle_alias,
                    'username': self.user.name,
                    'path': path,
                }
                if not await database.fetch_val(query, values):
                    return

        # If positive, add it to the player's collection
        query = '''
            INSERT IGNORE INTO user_achievements
                (riddle, username, title, unlock_time, incognito)
            VALUES (:riddle, :username, :title, :time, :incognito)
        '''
        values = {
            'riddle': self.riddle_alias,
            'username': self.user.name,
            'title': achievement['title'],
            'time': datetime.utcnow(),
            'incognito': await is_user_incognito(),
        }
        if not await database.execute(query, values):
            return

        # Also update user and global scores
        points = cheevo_ranks[achievement['rank']]['points']
        await self.update_score(points)

        # Call bot achievement unlock procedures
        await bot_request(
            'unlock',
            method='cheevo_found',
            alias=self.riddle_alias,
            username=self.user.name,
            cheevo=dict(achievement),
            points=points,
            page=self.path,
        )

        # Log achievement unlock
        print(
            f"> \033[1m[{self.riddle_alias}]\033[0m "
            f"\033[1m{self.user.name}\033[0m unlocked achievement "
            f"\033[1m\033[3m{achievement['title']}\033[0m\033[0m"
        )
        if await has_player_mastered_riddle(self.riddle_alias, self.user.name):
            await self.grant_mastery()

    async def grant_mastery(self):
        '''Log and message player mastering the riddle (i.e 100% score).'''
        print(
            f"> \033[1m[{self.riddle_alias}]\033[0m "
            f"\033[1m{self.user.name}\033[0m has mastered the game 💎"
        )
        await bot_request(
            'unlock',
            method='game_mastered',
            alias=self.riddle_alias,
            username=self.user.name,
        )

    async def _register_new_unlisted_page(self):
        '''Register new valid unlisted page.'''

        # Record page as a new one (w/ respective level being NULL)
        query = '''
            INSERT IGNORE INTO level_pages (riddle, path, level_name)
            VALUES (:riddle, :path, NULL)
        '''
        values = {'riddle': self.riddle_alias, 'path': self.path}
        await database.execute(query, values)

        # Grant individual page record to user
        # (as a personal "reward" if eventually a listed level page)
        query = '''
            INSERT IGNORE INTO user_pages 
                (riddle, username, level_name, path, access_time, incognito)
            VALUES (:riddle, :username, NULL, :path, :access_time, :incognito)
        '''
        values |= {
            'username': self.user.name,
            'access_time': datetime.utcnow(),
            'incognito': await is_user_incognito(),
        }
        await database.execute(query, values)

        # Record found page and the user who did it
        query = '''
            INSERT IGNORE INTO _found_pages 
                (riddle, path, username, access_time)
            VALUES (:riddle, :path, :username, :access_time)
        '''
        del values['incognito']
        if await database.execute(query, values):
            print(
                f"> \033[1m[{self.riddle_alias}]\033[0m "
                f"Found new page \033[1m{self.path}\033[0m "
                f"by \033[1m{self.user.name}\033[0m "
                f"({values['access_time']})"
            )


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
        query = '''
            INSERT INTO user_levels
                (riddle, username, level_name, find_time, incognito_unlock)
            VALUES (:riddle, :username, :level_name, :time, :incognito_unlock)
        '''
        values = {
            'riddle': self.ph.riddle_alias,
            'username': self.ph.user.name,
            'level_name': self.level['name'],
            'time': datetime.utcnow(),
            'incognito_unlock': await is_user_incognito(),
        }
        await database.execute(query, values)

        # Call bot unlocking procedure
        await bot_request(
            'unlock', method='advance',
            alias=self.ph.riddle_alias,
            level=self.level,
            username=self.ph.user.name,
        )

        if self.level['is_secret']:
            # Log secret level finding
            print(
                f"> \033[1m[{self.ph.riddle_alias}]\033[0m "
                f"\033[1m{self.ph.user.name}\033[0m found "
                f"secret level \033[1m{self.level['name']}\033[0m",
            )
        elif self.ph.riddle_account['current_level'] != '🏅':
            # Update player's `current_level`
            # (given that riddle hasn't been completed yet)
            query = f"""
                UPDATE {
                    '_incognito_riddle_accounts' if await is_user_incognito()
                    else 'riddle_accounts'
                }
                SET current_level = :name_next
                WHERE riddle = :riddle AND username = :username
            """
            values = {
                'riddle': self.ph.riddle_alias,
                'username': self.ph.user.name,
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

        # Register level completion on designated table
        alias, username = self.ph.riddle_alias, self.ph.user.name
        query = '''
            UPDATE user_levels
            SET completion_time = :time, incognito_solve = :incognito_solve
            WHERE riddle = :riddle
                AND username = :username
                AND level_name = :level
        '''
        values = {
            'riddle': alias,
            'username': username,
            'level': self.level['name'],
            'time': datetime.utcnow(),
            'incognito_solve': await is_user_incognito(),
        }
        await database.execute(query, values)

        # Call bot level beat procedures
        await bot_request(
            'unlock',
            method='beat',
            alias=alias,
            level=self.level,
            username=username,
            points=self.points,
            first_to_solve=False
        )

        # Log level completion
        level_type = 'secret level' if self.level['is_secret'] else 'level'
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"\033[1m{username}\033[0m "
            f"solved {level_type} \033[1m{self.level['name']}\033[0m "
        )

        # Check if level just completed is the _final_ one
        query = 'SELECT * FROM riddles WHERE alias = :riddle'
        values = {'riddle': self.ph.riddle_alias}
        final_name = await database.fetch_val(query, values, 'final_level')
        if self.level['name'] == final_name:
            # Player has just completed the riddle :)
            query = f"""
                UPDATE {
                    '_incognito_riddle_accounts' if await is_user_incognito()
                    else 'riddle_accounts'
                }
                SET current_level = "🏅"
                WHERE riddle = :riddle AND username = :username
            """
            values |= {'username': username}
            await database.execute(query, values)

            # Call bot completion procedures
            await bot_request(
                'unlock',
                method='game_completed',
                alias=alias,
                username=username,
            )

            # Log completion
            print(
                f"> \033[1m[{alias}]\033[0m "
                f"\033[1m{username}\033[0m has finished the game 🏅"
            )

        # Assure level is ranked (points > 0) to avoid redundant mastery
        # logs/messages (i.e for post-100% unranked solves and 0-score riddles)
        if self.points and await has_player_mastered_riddle(alias, username):
            await self.ph.grant_mastery()

        # Update level-related tables
        await self._update_info()

        return True

    async def _get_user_level_row(self):
        '''Return user/level record from DB.'''

        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle
                AND level_name = :level_name
                AND username = :username
        '''
        values = {
            'riddle': self.ph.riddle_alias,
            'level_name': self.level['name'],
            'username': self.ph.user.name,
        }
        row = await database.fetch_one(query, values)
        return row

    async def _update_info(self):
        '''Update level-related tables.'''

        if not await is_user_incognito():
            # Update global user completion count
            query = '''
                UPDATE levels
                SET completion_count = completion_count + 1
                WHERE riddle = :riddle AND name = :level_name
            '''
            values = {
                'riddle': self.ph.riddle_alias,
                'level_name': self.level['name']
            }
            await database.execute(query, values)

        # Update user and global scores
        await self.ph.update_score(self.points)


def is_trivial_redirect(path_from: str, path_to: str) -> bool:
    '''Check whether a redirect is trivial (i.e not a relevant page).'''

    def _matches_either_way(f: Callable[[str], str]):
        return f(path_from) == path_to or path_from == f(path_to)

    # Ignore query strings when comparing
    path_from = path_from.partition('?')[0]
    path_to = path_to.partition('?')[0]

    if path_from == path_to:
        # Scheme/host/port change
        return True
    if _matches_either_way(lambda path: path.removesuffix('/')):
        # Folder trailing slashes
        return True
    if _matches_either_way(lambda path: re.sub(r'(index)?([.]\w+)?$', '', path)):
        # Implicit [index].htm[l] (usually Neocities)
        return True
    if path_from.lower() == path_to:
        # Case insensitive webserver w/ auto-lowercase (e.g wingheart)
        return True

    return False

