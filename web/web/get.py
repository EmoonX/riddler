import json
from urllib.parse import urljoin, urlsplit

from quart import abort, Blueprint, jsonify
from quartcord import requires_authorization

from admin.admin_auth import is_admin_of
from auth import discord
from inject import get_riddles
from levels import get_pages
from util.db import database
from webclient import bot_request

# Create app blueprint
get = Blueprint('get', __name__)


@get.get('/get-riddle-hosts')
async def get_riddle_hosts():
    '''Get list of riddle hosts from database.'''

    # def _get_wildcard_pattern(root_path: str):
    #     '''Return URL in '*://*.{root_path}/*' wildcard pattern.'''
    #     parsed = urlsplit(root_path)
    #     root_folder = f"{parsed.path}/"
    #     return f"*://*.{parsed.hostname}{root_folder}*"

    def _param_is_true(param: str):
        return request.args.get(param).lower() in ['', '1', 'on', 'true', 'yes']

    unlisted_only = _param_is_true('unlistedOnly')

    is_root = False
    if discord.user_id:
        is_root = await is_admin_of('*')

    # Build dict of {root_path -> alias} hosts
    riddles = await get_riddles(unlisted=is_root)
    hosts = {}
    for riddle in riddles:
        if unlisted_only and not riddle['unlisted']:
            continue
        try:
            for root_path in json.loads(riddle['root_path']):
                hosts[root_path] = riddle['alias']
        except json.decoder.JSONDecodeError:
            hosts[riddle['root_path']] = riddle['alias']

    # Return JSON dict as response
    return jsonify(hosts)


@get.get('/get-user-riddle-data')
@get.get('/get-user-riddle-data/<alias>')
async def get_user_riddle_data(alias: str | None = None) -> str:
    '''
    Get riddle data for authenticated user.
    If `alias` is passed, restrict results to just given riddle.
    '''

    if not discord.user_id:
        # Raw 401 to avoid redirections to /login
        abort(401)

    user = await discord.get_user()
    values = {'username': user.name}
    if not alias:
        # Get riddle currently being played (if any)
        query = '''
            SELECT alias FROM riddles
            WHERE alias = (
                SELECT current_riddle FROM accounts
                WHERE username = :username
            )
        '''
        current_riddle = await database.fetch_val(query, values)

    # Build initial riddle(s) dict
    query = '''
        SELECT alias, full_name AS fullName, root_path AS rootPath
        FROM riddles
        WHERE alias LIKE :riddle
    '''
    values = {'riddle': alias or '%'}
    result = await database.fetch_all(query, values)
    riddles = {
        row['alias']: dict(row) | {'blacklistedPages': [], 'orderedLevels': []}
        for row in result
    }

    # Get blacklisted pages
    query = '''
        SELECT riddle, path, next_path AS nextPath FROM _blacklisted_pages
        WHERE riddle LIKE :riddle
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        riddle = riddles[row['riddle']]
        riddle['blacklistedPages'].append(dict(row))

    # Get full list of (non removed) recorded pages (paths) by user
    query = '''
        SELECT *
        FROM level_pages lp INNER JOIN user_pages up
            ON lp.riddle = up.riddle AND lp.path = up.path
        WHERE lp.riddle LIKE :riddle
            AND lp.removed IS NOT TRUE
            AND up.username = :username
    '''
    values |= {'username': user.name}
    result = await database.fetch_all(query, values)
    recorded_paths = {}
    for row in result:
        recorded_paths.setdefault(row['riddle'], set()).add(row['path'])

    # Build list of levels unlocked/solved by user (in order)
    query = '''
        SELECT
            up.riddle, ls.name AS set_name, up.level_name,
                lv.path, lv.image, lv.answer,
                find_time, completion_time
            FROM user_pages up
                LEFT JOIN user_levels ul
                    ON up.riddle = ul.riddle AND up.level_name = ul.level_name
                        AND up.username = ul.username
                INNER JOIN levels lv
                    ON up.riddle = lv.riddle AND up.level_name = lv.name
                INNER JOIN level_sets ls
                    ON up.riddle = ls.riddle AND lv.level_set = ls.name
            WHERE up.riddle LIKE :riddle AND up.username = :username
            GROUP BY up.riddle, up.level_name
            ORDER BY ls.`index`, lv.`index`
    '''
    result = await database.fetch_all(query, values)
    for row in result:
        level = {
            'setName': row['level_set'],
            'name': row['name'],
            'solved': row['completion_time'] is not None,
        }

        # Handle either multiple or single front paths
        try:
            front_paths = [path for path in json.loads(row['path'])]
        except json.decoder.JSONDecodeError:
            front_paths = [row['path']]
        front_paths = list(filter(
            lambda path: path in recorded_paths.get(row['riddle'], set()),
            front_paths
        ))
        if front_paths:
            level |= {'frontPath':
                front_paths if len(front_paths) > 1 else
                front_paths[0]
            }

        level |= {'image': row['image']}
        if level['solved']:
            level |= {'answer': row['answer']}

        riddles[row['riddle']]['orderedLevels'].append(level)

    # Get last visited level/set for riddle(s)
    query = '''
        SELECT ra.riddle, level_set, last_visited_level, last_visited_page
        FROM riddle_accounts ra INNER JOIN levels lv
            ON ra.riddle = lv.riddle AND last_visited_level = lv.name
        WHERE ra.riddle LIKE :riddle AND username = :username
    '''
    result = await database.fetch_all(query, values)
    for row in result: 
        if row['last_visited_level']:            
            riddles[row['riddle']] |= {
                'lastVisitedSet': row['level_set'],
                'lastVisitedLevel': row['last_visited_level'],
                'lastVisitedPage': row['last_visited_page'],
            }

    # Create and return JSON dict with data
    if not alias:
        data = {'riddles': riddles, 'currentRiddle': current_riddle}
    else:
        data = riddles.get(alias, {})

    return jsonify(data)


@get.get('/get-current-riddle-data')
@requires_authorization
async def get_current_riddle_data():
    '''Get currently being played riddle data for authenticated user.'''

    # Get player and riddle data from DB
    user = await discord.get_user()
    query = '''
        SELECT * FROM accounts acc
        INNER JOIN riddles r ON acc.current_riddle = r.alias
        INNER JOIN riddle_accounts racc
            ON r.alias = racc.riddle AND acc.username = racc.username
        WHERE acc.username = :username
    '''
    values = {'username': user.name}
    riddle = await database.fetch_one(query, values)
    if not riddle:
        return 'No riddle being played...', 404
    alias = riddle['alias']

    # Get riddle icon URL
    icon_url = f"/static/riddles/{alias}.png"

    # Create and return JSON dict with data
    data = {
        'alias': alias,
        'full_name': riddle['full_name'], 'icon_url': icon_url,
        'visited_level': riddle['last_visited_level'],
    }
    return jsonify(data)


@get.get('/get-user-pages')
@requires_authorization
async def get_user_pages() -> str:
    '''Get user-accessed pages from every riddle.'''

    pages = {}
    riddles = await get_riddles(unlisted=True)
    for alias in [riddle['alias'] for riddle in riddles]:
        page_tree = await get_pages(alias, as_json=False)
        pages[alias] = page_tree

    return jsonify(pages)
