from datetime import datetime

from pymysql.err import IntegrityError
from quart import Blueprint, abort
from quartcord import requires_authorization

from admin.admin_auth import admin_auth, root_auth
from inject import get_riddles
from riddle import level_ranks, cheevo_ranks
from util.db import database

# Create app blueprint
admin_update = Blueprint('admin', __name__)


@admin_update.get('/admin/update-all-riddles')
@requires_authorization
async def update_all_riddles():
    '''Update everything in every single riddle.'''

    # Only root can do it!
    ok = await root_auth()
    if not ok:
        abort(401)

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


@admin_update.get('/admin/<alias>/update-all')
@requires_authorization
async def update_all(alias: str):
    '''Wildcard route for running all update routines below.'''

    update_methods = (
        update_scores, update_page_count,
        update_completion_count, update_ratings,
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


@admin_update.get('/admin/<alias>/update-page-count')
@requires_authorization
async def update_page_count(alias: str):
    '''Úpdate riddle players' page count.'''

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


@admin_update.get('/admin/<alias>/update-completion')
@requires_authorization
async def update_completion_count(alias: str):
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


@admin_update.get('/admin/<alias>/update-user-credentials')
@requires_authorization
async def update_user_credentials(alias: str):
    '''
    Update `user_credentials` with missing records,
    i.e folder paths present in `user_pages` but not recorded yet.
    '''

    # Check for admin permissions
    await admin_auth(alias)

    query = '''
        SELECT DISTINCT rc.*, up.username AS acc_username
        FROM riddle_credentials rc INNER JOIN user_pages up
            ON rc.riddle = up.riddle
                AND up.path LIKE CONCAT(rc.folder_path, "/%")
        WHERE rc.riddle = :riddle
            AND folder_path NOT IN (
                SELECT folder_path FROM user_credentials uc
                WHERE up.username = uc.username
            )
        ORDER BY acc_username
    '''
    values = {'riddle': alias}
    missing_credentials = await database.fetch_all(query, values)
    if not missing_credentials:
        return 'No missing user credentials to add.', 200

    success = False
    for credential in missing_credentials:
        query = '''
            INSERT INTO user_credentials
                (riddle, username, folder_path)
            VALUES (:riddle, :username, :folder_path)
        '''
        values |= {
            'username': credential['acc_username'],
            'folder_path': credential['folder_path']
        }
        try:
            await database.execute(query, values)
        except IntegrityError:
            pass
        else:
            s = f"{credential['username']}:{credential['password']}"
            tnow = datetime.utcnow()
            print(
                f"> \033[1m[{alias}]\033[0m "
                f"Added credential \033[3m\033[1m{s}\033[0m "
                f"for user \033[1m{credential['acc_username']}\033[0m "
                f"({tnow})"
            )
    
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


@admin_update.get('/admin/<alias>/update-page-changes')
@requires_authorization
async def update_page_changes(alias: str):

    # Check for admin permissions
    await admin_auth(alias)

    async def _update_page_level(path: str, new_level: str):
        '''Update level for page with given path.'''
        query = '''
            UPDATE level_pages
            SET level_name = :new_level
            WHERE riddle = :riddle AND path = :path
        '''
        values = {'riddle': alias, 'path': path, 'new_level': new_level}
        await database.execute(query, values)

    query = '''
        SELECT * FROM _page_changes
        WHERE riddle = :riddle
    '''
    page_changes = await database.fetch_all(query, {'riddle': alias})
    for page_change in page_changes:
        path, new_path = page_change['path'], page_change['new_path']
        level, new_level = page_change['level'], page_change['new_level']
        if path:
            # Remove level from old page
            await _update_page_level(path, None)

            if not new_path:
                # Page wasn't moved but removed, nothing more to do
                continue

            if page_change['trivial_move']:
                # "Trivial move" means path change was essentially
                # due to logistics and not actually new/different content;
                # therefore, grant new page to everyone who had the old one
                query = '''
                    SELECT username, access_time FROM user_pages
                    WHERE riddle = :riddle AND path = :path
                '''
                values = {'riddle': alias, 'path': path}
                players = await database.fetch_all(query, values)
                query = '''
                    INSERT IGNORE INTO user_pages (
                        riddle, username, level_name, path, access_time
                    ) VALUES (
                        :riddle, :username, :level_name, :new_path, :access_time
                    )
                '''
                values = [
                    {
                        'riddle': alias,
                        'username': player['username'],
                        'level_name': new_level or level,
                        'new_path': new_path,
                        'access_time': player['access_time'],
                    }
                    for player in players
                ]
                await database.execute_many(query, values)

            # Possibly update level data in case old path was a front one
            query = '''
                UPDATE levels
                SET path = :new_path
                WHERE riddle = :riddle AND path = :path
            '''
            values = {'riddle': alias, 'path': path, 'new_path': new_path}
            await database.execute(query, values)
            query = '''
                UPDATE levels
                SET answer = :new_path
                WHERE riddle = :riddle AND answer = :path
            '''
            await database.execute(query, values)
                
        # Add level to moved/new page
        await _update_page_level(new_path, new_level or level)
    
    return 'SUCCESS :)', 200
