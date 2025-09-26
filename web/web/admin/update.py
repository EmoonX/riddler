import json

from quart import Blueprint
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth, root_auth
from inject import get_accounts, get_riddles
from riddles import level_ranks, cheevo_ranks
from util.db import database
from util.levels import get_ancestor_levels
from webclient import bot_request

# Create app blueprint
admin_update = Blueprint('admin', __name__)


@admin_update.get('/admin/update-all-riddles')
@requires_authorization
async def update_all_riddles():
    '''Update everything in every single riddle.'''

    # Only root can do it!
    await root_auth()

    # Run update_all on every riddle
    riddles = await get_riddles()
    for riddle in riddles:
        alias = riddle['alias']
        response = await update_all(alias)
        if response[1] != 200:
            return response

    # Update separately players' global scores
    for acc_table, racc_table in [
        ('accounts', 'riddle_accounts'),
        ('_incognito_accounts', '_incognito_riddle_accounts'),
    ]:
        query = f"""
            UPDATE {acc_table} acc
            SET global_score = (
                SELECT COALESCE(SUM(score), 0) FROM {racc_table} racc
                WHERE acc.username = racc.username
            )
        """
        await database.execute(query)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-all')
@requires_authorization
async def update_all(alias: str):
    '''Wildcard route for running all update routines below.'''

    update_methods = (
        update_scores,
        update_current_levels,
        update_completion_counts, update_page_counts,
        update_user_credentials, update_ratings,
    )
    for update in update_methods:
        response = await update(alias)
        if response[1] != 200:
            return response

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-scores')
@requires_authorization
async def update_scores(alias: str):
    '''Úpdate riddle players' score.'''

    # Check for admin permissions
    await admin_auth(alias)

    # Iterate over riddle accounts
    query = 'SELECT * FROM riddle_accounts WHERE riddle = :riddle'
    accounts = await database.fetch_all(query, {'riddle': alias})
    for acc in accounts:
        # Add beaten level points to new score
        score = incognito_score = 0
        query = '''
            SELECT * FROM user_levels INNER JOIN levels
                ON user_levels.riddle = levels.riddle
                    AND user_levels.level_name = levels.name
            WHERE levels.riddle = :riddle
                AND username = :name
                AND completion_time IS NOT NULL
        '''
        values = {'riddle': alias, 'name': acc['username']}
        completed_levels = await database.fetch_all(query, values)
        for level in completed_levels:
            points = level_ranks[level['rank']]['points']
            if level['incognito_solve']:
                incognito_score += points
            else:
                score += points

        # Add unlocked cheevo points to new score
        query = '''
            SELECT * FROM user_achievements INNER JOIN achievements
                ON user_achievements.riddle = achievements.riddle
                    AND user_achievements.title = achievements.title
            WHERE achievements.riddle = :riddle AND username = :name
        '''
        unlocked_cheevos = await database.fetch_all(query, values)
        for cheevo in unlocked_cheevos:
            points = cheevo_ranks[cheevo['rank']]['points']
            if cheevo['incognito']:
                incognito_score += points
            else:
                score += points

        # Update player's riddle score
        for table, _score in [
            ('_incognito_riddle_accounts', incognito_score),
            ('riddle_accounts', score),
        ]:
            query = f"""
                UPDATE {table}
                SET score = :score
                WHERE riddle = :riddle AND username = :name
            """
            values |= {'score': _score}
            await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-current-levels')
@requires_authorization
async def update_current_levels(alias: str):
    '''Úpdate riddle players' current levels (and 🏅s).'''

    # Check for admin permissions
    await admin_auth(alias)

    query = '''
        SELECT * FROM levels lv
        WHERE riddle = :riddle AND name = (
            SELECT final_level FROM riddles r
            WHERE lv.riddle = r.alias
        )
    '''
    values = {'riddle': alias}
    final_level = await database.fetch_one(query, values)
    if final_level:
        reverse_ordered_levels = (await get_ancestor_levels(
            alias, final_level, full_search=True
        )).values()
    else:
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle AND set_index < 99
            ORDER BY set_index DESC, `index` DESC
        '''
        reverse_ordered_levels = await database.fetch_all(query, values)

    # Iterate over riddle accounts
    query = 'SELECT * FROM riddle_accounts WHERE riddle = :riddle'
    riddle_accounts = await database.fetch_all(query, {'riddle': alias})    
    for racc in riddle_accounts:
        query = '''
            SELECT * FROM user_levels
            WHERE riddle = :riddle AND username = :username
        '''
        values = {'riddle': alias, 'username': racc['username']}
        user_levels = {
            level['level_name']: level
            for level in await database.fetch_all(query, values)
        }
        current_level = incognito_current_level = None
        for level in reverse_ordered_levels:
            if user_level := user_levels.get(level['name']):
                if (
                    final_level
                    and level['name'] == final_level['name']
                    and user_level['completion_time']
                ):
                    if user_level['incognito_solve']:
                        incognito_current_level = '🏅'
                    else:
                        current_level = '🏅'
                        break
                if not user_level['incognito_unlock']:
                    current_level = level['name']
                    break
                if not incognito_current_level:
                    incognito_current_level = level['name']

        for table, _current_level in (
            ('riddle_accounts', current_level),
            ('_incognito_riddle_accounts', incognito_current_level),
        ):
            query = f"""
                UPDATE {table}
                SET current_level = :current_level
                WHERE riddle = :riddle AND username = :username
            """
            values |= {'current_level': _current_level}
            await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-solve-counts')
@requires_authorization
async def update_completion_counts(alias: str):
    '''Úpdate riddle levelś' solve count.'''

    # Check for admin permissions
    await admin_auth(alias)

    # Get list of levels and completion counts
    query = '''
        SELECT level_name, COUNT(*) AS count FROM user_levels
        WHERE riddle = :riddle
            AND completion_time IS NOT NULL
            AND incognito_solve IS NOT TRUE
        GROUP BY level_name
    '''
    levels = await database.fetch_all(query, {'riddle': alias})

    # Update completion count for all riddle levels
    for level in levels:
        query = '''
            UPDATE levels
            SET completion_count = :count
            WHERE riddle = :riddle AND name = :level
        '''
        values = {
            'count': level['count'],
            'riddle': alias, 'level': level['level_name']
        }
        await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-page-counts')
@requires_authorization
async def update_page_counts(alias: str):
    '''Úpdate riddle players' page counts.'''

    # Check for admin permissions
    await admin_auth(alias)

    # Fetch page count for every riddle player
    query = '''
        SELECT *,
            SUM(incognito IS     TRUE) AS incognito_page_count,
            SUM(incognito IS NOT TRUE) AS page_count
        FROM user_pages up INNER JOIN level_pages lp
            ON up.riddle = lp.riddle AND up.path = lp.path
        WHERE up.riddle = :riddle
            AND up.level_name IS NOT NULL
            AND lp.hidden IS NOT TRUE
        GROUP BY up.username
    '''
    accounts = await database.fetch_all(query, {'riddle': alias})

    # Update page count for each riddle account in DB
    for acc in accounts:
        for table, page_count in [
            ('_incognito_riddle_accounts', acc['incognito_page_count']),
            ('riddle_accounts', acc['page_count']),
        ]:
            query = f"""
                UPDATE {table}
                SET page_count = :page_count
                WHERE riddle = :riddle AND username = :username
            """
            values = {
                'riddle': alias,
                'username': acc['username'],
                'page_count': page_count,
            }
            await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-user-credentials')
@requires_authorization
async def update_user_credentials(alias: str):
    '''
    Update `user_credentials` with missing records,
    i.e paths present in `user_pages` but not in the former.
    '''

    # Check for admin permissions
    await admin_auth(alias)

    # Get list of riddle credentials, with innermost paths ordered first
    query = '''
        SELECT * FROM riddle_credentials
        WHERE riddle = :riddle
        ORDER BY riddle, path DESC
    '''
    credentials = await database.fetch_all(query, {'riddle': alias})

    path_previous = None
    for path in [cred['path'] for cred in credentials]:
        # Retrieve user-visited pages pointing to or within the credentials
        # path, bar the ones belonging to nested (already iterated) realms
        query = f"""
            SELECT * FROM (
                SELECT * FROM user_pages
                WHERE riddle = :riddle
                    AND path LIKE :path AND path NOT LIKE :path_previous
                GROUP BY username, incognito
            ) AS _
            GROUP BY username
        """
        values = {
            'riddle': alias,
            'path': f"{path}%",
            'path_previous': f"{path_previous}%",
        }
        players_in_path = await database.fetch_all(query, values)

        for player in players_in_path:
            # Add nondated credentials to user (if indeed missing)
            query = '''
                INSERT IGNORE INTO user_credentials
                    (riddle, username, path)
                VALUES (:riddle, :username, :path)
            '''
            values = {
                'riddle': alias,
                'username': player['username'],
                'path': path,
            }
            if await database.execute(query, values):
                print(
                    f"> \033[1m[{alias}]\033[0m "
                    f"Added credentials for "
                    f"path \033[3m\033[1m{path}\033[0m "
                    f"and user \033[1m{player['username']}\033[0m"
                )

            # `incognito` iff all the user's pages inside path have the flag
            query = '''
                UPDATE user_credentials
                SET incognito = :incognito
                WHERE riddle = :riddle AND username = :username AND path = :path
            '''
            values |= {'incognito': player['incognito'] or None}
            await database.execute(query, values)

        path_previous = path if '.' in path else f"{path}/"
    
    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-ratings')
@requires_authorization
async def update_ratings(alias: str):
    '''Úpdate riddle levels' player ratings.'''

    # Check for admin permissions
    await admin_auth(alias)

    # Iterate over levels
    query = 'SELECT * FROM levels WHERE riddle = :riddle'
    levels = await database.fetch_all(query, {'riddle': alias})
    for level in levels:
        # Get total number of votes and their average from DB
        count, average = 0, None
        query = '''
            SELECT COUNT(rating_given) AS count, AVG(rating_given) AS average
            FROM user_levels
            WHERE riddle = :riddle AND level_name = :name
            GROUP BY riddle, level_name
        '''
        values = {'riddle': alias, 'name': level['name']}
        level = await database.fetch_one(query, values)
        if level:
            count, average = level['count'], level['average']

        # Update count and average on levels table
        query = '''
            UPDATE levels
            SET rating_count = :count, rating_avg = :average
            WHERE riddle = :riddle AND name = :name
        '''
        values |= {'count': count, 'average': average}
        await database.execute(query, values)

    return 'SUCCESS :)', 200

@admin_update.get('/admin/update-discord-account-info')
@requires_authorization
async def update_discord_account_info():

    await root_auth()

    accounts = await get_accounts()
    for account in accounts.values():
        if not account['discord_id']:
            continue

        if not account['display_name']:
            # Old untracked account, needs update ASAP
            data = json.loads(await bot_request(
                'fetch-account-info',
                discord_id=account['discord_id']
            ))
            query = '''
                UPDATE accounts
                SET username = :username,
                    display_name = :display_name,
                    avatar_url = :avatar_url
                WHERE discord_id = :discord_id
            '''
            values = {
                'username': data['username'],
                'display_name': data['display_name'],
                'avatar_url': data['avatar_url'],
                'discord_id': account['discord_id'],
            }
            print(values, flush=True)
            await database.execute(query, values)

        else:
            url = account['avatar_url']
            response = requests.get(url)
            if response.status_code == 404:
                # Outdated profile picture
                avatar_url = await bot_request(
                    'get-avatar-url',
                    discord_id=account['discord_id']
                )
                query = '''
                    UPDATE accounts
                    SET avatar_url = :avatar_url
                    WHERE discord_id = :discord_id
                '''
                values = {
                    'avatar_url': avatar_url,
                    'discord_id': account['discord_id'],
                }
                print(values, flush=True)
                await database.execute(query, values)

    return 'SUCCESS :)', 200
