from quart import Blueprint, abort
from quart_discord import requires_authorization

from auth import discord
from inject import level_ranks, cheevo_ranks
from webclient import bot_request
from util.db import database

# Create app blueprint
admin = Blueprint('admin', __name__)


@requires_authorization
async def root_auth() -> bool:
    '''Check if you are... Emoon.'''
    user = await discord.get_user()
    return user.id == 315940379553955844


@requires_authorization
async def auth(alias: str):
    '''Check if alias is valid and user an admin of guild.'''

    # Get riddle/guild full name from database
    query = 'SELECT * FROM riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    if not result:
        # Invalid alias...
        abort(404)

    # Big boss can access everything 8)
    user = await discord.get_user()
    if user.id == 315940379553955844:
        return

    # Check if user is riddle's creator/admin
    query = '''
        SELECT * FROM riddles
        WHERE alias = :alias
            AND creator_username = :username AND creator_disc = :disc
    '''
    values = {
        'alias': alias,
        'username': user.name, 'disc': user.discriminator
    }
    is_creator = await database.fetch_one(query, values)
    if is_creator:
        return

    # Otherwise, check if user has enough permissions in given guild
    ok = await bot_request(
        'is-member-and-has-permissions',
        guild_id=result['guild_id'],
        username=user.name, disc=user.discriminator
    )
    if ok != "True":
        abort(401)


@admin.get('/admin/update-all-riddles')
@requires_authorization
async def update_all_riddles():
    '''Update everything on every single riddle.'''

    # Only root can do it!
    ok = await root_auth()
    if not ok:
        abort(401)

    # Get all riddle aliases from DB
    query = 'SELECT * FROM riddles'
    result = await database.fetch_all(query)
    riddles = {riddle['alias']: riddle for riddle in result}

    # Run update_all on every riddle
    for row in result:
        alias = row['alias']
        response = await update_all(alias)
        if response[1] != 200:
            return response

    # Update separately players' global scores
    query = 'UPDATE accounts SET global_score = 0'
    await database.execute(query)
    query = 'SELECT * FROM riddle_accounts'
    riddle_accounts = await database.fetch_all(query)
    for row in riddle_accounts:
        riddle = riddles[row['riddle']]
        if riddle['unlisted']:
            # Ignore unlisted riddles
            continue
        query = '''
            UPDATE accounts
            SET global_score = global_score + :score
            WHERE username = :name AND discriminator = :disc
        '''
        values = {
            'score': row['score'],
            'name': row['username'], 'disc': row['discriminator']
        }
        await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin.get('/admin/<alias>/update-all')
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


@admin.get('/admin/<alias>/update-scores')
@requires_authorization
async def update_scores(alias: str):
    '''Úpdates riddle players' score.'''

    # Check for admin permissions
    await auth(alias)

    # Iterate over riddle accounts
    query = 'SELECT * FROM riddle_accounts WHERE riddle = :riddle'
    accounts = await database.fetch_all(query, {'riddle': alias})
    for acc in accounts:
        # Get current score
        cur_score = acc['score']

        # Add beaten level points to new score
        new_score = 0
        query = '''
            SELECT * FROM user_levels
            INNER JOIN levels
                ON user_levels.riddle = levels.riddle
                    AND user_levels.level_name = levels.name
            WHERE levels.riddle = :riddle 
                AND username = :name and discriminator = :disc 
                AND completion_time IS NOT NULL
        '''
        values = {
            'riddle': alias,
            'name': acc['username'], 'disc': acc['discriminator']
        }
        completed_levels = await database.fetch_all(query, values)
        for level in completed_levels:
            points = level_ranks[level['rank']]['points']
            new_score += points

        # Add unlocked cheevo points to new score
        query = '''
            SELECT * FROM user_achievements 
            INNER JOIN achievements 
                ON user_achievements.riddle = achievements.riddle 
                    AND user_achievements.title = achievements.title 
            WHERE achievements.riddle = :riddle 
                AND username = :name and discriminator = :disc
        '''
        unlocked_cheevos = await database.fetch_all(query, values)
        for cheevo in unlocked_cheevos:
            points = cheevo_ranks[cheevo['rank']]['points']
            new_score += points

        # Update player's riddle score
        query = '''
            UPDATE riddle_accounts 
            SET score = :score 
            WHERE riddle = :riddle 
                AND username = :name and discriminator = :disc
        '''
        values = {'score': new_score, **values}
        await database.execute(query, values)

        # If riddle is listed, update player's global score
        query = 'SELECT * FROM riddles WHERE alias = :alias'
        values = {'alias': alias}
        riddle = await database.fetch_one(query, values)
        if not riddle['unlisted']:
            query = '''
                UPDATE accounts
                SET global_score = (global_score - :cur + :new)
                WHERE username = :name and discriminator = :disc
            '''
            new_values = {
                'cur': cur_score, 'new': new_score,
                'name': acc['username'], 'disc': acc['discriminator']
            }
            await database.execute(query, new_values)

    return 'SUCCESS :)', 200


@admin.get('/admin/<alias>/update-page-count')
@requires_authorization
async def update_page_count(alias: str):
    '''Úpdates riddle players' page count.'''

    # Check for admin permissions
    await auth(alias)

    # Fetch page count for every riddle player
    query = '''
        SELECT racc.username, racc.discriminator,
            COUNT(level_name) AS page_count 
        FROM riddle_accounts AS racc 
        INNER JOIN user_pages AS up 
            ON racc.username = up.username 
                AND racc.discriminator = up.discriminator 
        WHERE up.riddle = :riddle 
        GROUP BY racc.riddle, racc.username, racc.discriminator
    '''
    accounts = await database.fetch_all(query, {'riddle': alias})

    # Update page count for each riddle account in DB
    for acc in accounts:
        query = '''
            UPDATE riddle_accounts SET page_count = :page_count
            WHERE riddle = :riddle 
                AND username = :username and discriminator = :disc
        '''
        values = {
            'riddle': alias, 'page_count': acc['page_count'],
            'username': acc['username'], 'disc': acc['discriminator']
        }
        await database.execute(query, values)

    return 'SUCCESS :)', 200


@admin.get('/admin/<alias>/update-completion')
@requires_authorization
async def update_completion_count(alias: str):
    '''Úpdates riddle levelś' completion count.'''

    # Check for admin permissions
    await auth(alias)

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


@admin.get('/admin/<alias>/update-ratings')
@requires_authorization
async def update_ratings(alias: str):
    '''Úpdates riddle levels' user ratings.'''

    # Check for admin permissions
    await auth(alias)

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
        values = {'count': count, 'average': average, **values}
        await database.execute(query, values)

    return 'SUCCESS :)', 200
