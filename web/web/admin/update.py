from datetime import datetime
import json

from pymysql.err import IntegrityError
from quart import Blueprint, abort
from quartcord import requires_authorization
import requests

from admin.admin_auth import admin_auth, root_auth
from inject import get_accounts, get_riddles
from riddles import level_ranks, cheevo_ranks
from util.db import database
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
    query = 'UPDATE accounts SET global_score = 0'
    await database.execute(query)
    query = 'SELECT username, score FROM riddle_accounts'
    riddle_accounts = await database.fetch_all(query)
    for row in riddle_accounts:
        query = '''
            UPDATE accounts
            SET global_score = global_score + :score
            WHERE username = :name
        '''
        values = {'score': row['score'], 'name': row['username']}
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


@admin_update.get('/admin/<alias>/update-all')
@requires_authorization
async def update_all(alias: str):
    '''Wildcard route for running all update routines below.'''

    update_methods = (
        update_scores,
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
        # Get current score
        cur_score = acc['score']

        # Add beaten level points to new score
        new_score = 0
        query = '''
            SELECT *
            FROM user_levels INNER JOIN levels
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
            new_score += points

        # Add unlocked cheevo points to new score
        query = '''
            SELECT *
            FROM user_achievements INNER JOIN achievements
            ON user_achievements.riddle = achievements.riddle
                AND user_achievements.title = achievements.title
            WHERE achievements.riddle = :riddle
                AND username = :name
        '''
        unlocked_cheevos = await database.fetch_all(query, values)
        for cheevo in unlocked_cheevos:
            points = cheevo_ranks[cheevo['rank']]['points']
            new_score += points

        # Update player's riddle score
        query = '''
            UPDATE riddle_accounts SET score = :score
            WHERE riddle = :riddle
                AND username = :name
        '''
        values |= {'score': new_score}
        await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-completion-counts')
@requires_authorization
async def update_completion_counts(alias: str):
    '''Úpdate riddle levelś' completion count.'''

    # Check for admin permissions
    await admin_auth(alias)

    # Get list of levels and completion counts
    query = '''
        SELECT level_name, COUNT(*) AS count FROM user_levels
        WHERE riddle = :riddle AND completion_time IS NOT NULL
        GROUP BY level_name
    '''
    levels = await database.fetch_all(query, {'riddle': alias})

    # Update completion count for all riddle levels
    for level in levels:
        query = '''
            UPDATE levels SET completion_count = :count
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
        SELECT racc.username, COUNT(level_name) AS page_count
        FROM riddle_accounts AS racc INNER JOIN user_pages AS up
        ON racc.username = up.username
        WHERE up.riddle = :riddle
        GROUP BY racc.riddle, racc.username
    '''
    accounts = await database.fetch_all(query, {'riddle': alias})

    # Update page count for each riddle account in DB
    for acc in accounts:
        query = '''
            UPDATE riddle_accounts SET page_count = :page_count
            WHERE riddle = :riddle
                AND username = :username
        '''
        values = {
            'riddle': alias,
            'page_count': acc['page_count'],
            'username': acc['username'],
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
            SELECT username FROM user_pages
            WHERE riddle = :riddle
                AND path LIKE :path AND path NOT LIKE :path_previous
            GROUP BY username
        """
        values = {
            'riddle': alias,
            'path': f"{path}%",
            'path_previous': f"{path_previous}%",
        }
        user_pages = await database.fetch_all(query, values)
        for username in [page['username'] for page in user_pages]:
            # Add nondated credentials to user (if indeed missing)
            query = '''
                INSERT INTO user_credentials
                    (riddle, username, path)
                VALUES (:riddle, :username, :path)
            '''
            values = {'riddle': alias, 'username': username, 'path': path}
            try:
                await database.execute(query, values)
            except IntegrityError:
                continue
            else:
                print(
                    f"> \033[1m[{alias}]\033[0m "
                    f"Added credentials for "
                    f"path \033[3m\033[1m{path}\033[0m "
                    f"and user \033[1m{username}\033[0m"
                )

        path_previous = path if '.' in path else f"{path}/"
    
    return 'SUCCESS :)', 200


@admin_update.get('/admin/<alias>/update-ratings')
@requires_authorization
async def update_ratings(alias: str):
    '''Úpdate riddle levels' user ratings.'''

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
