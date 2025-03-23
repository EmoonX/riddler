from collections import defaultdict

from quart import Blueprint, abort
from quartcord import requires_authorization

from admin.admin_auth import root_auth
from riddles import cheevo_ranks, level_ranks
from util.db import database

admin_recent = Blueprint('admin_recent', __name__)


@admin_recent.get('/admin/update-recent')
@requires_authorization
async def update_recent():
    '''Update players' recent scores and last placements.'''

    await root_auth()

    await _update_recent_scores(days=120)
    await _update_last_placements()

    return 'SUCCESS :)', 200


async def _update_recent_scores(days: int):
    '''Update recent player scores, both riddle-wise and global.'''

    # Init dict of recent user/riddle scores with ALL players at 0
    query = '''SELECT * FROM riddle_accounts'''
    riddle_accounts = await database.fetch_all(query)
    recent_scores = defaultdict(dict[str, int])
    for riddle_account in riddle_accounts:
        username = riddle_account['username']
        riddle = riddle_account['riddle']
        recent_scores[username][riddle] = 0

    # Fetch recently completed levels and unlocked achievements
    query = '''
        SELECT *
        FROM user_levels ul INNER JOIN levels lv
            ON ul.riddle = lv.riddle AND ul.level_name = lv.name
        WHERE completion_time IS NOT NULL
            AND TIMESTAMPDIFF(DAY, completion_time, NOW()) < :days
    '''
    values = {'days': days}
    recent_levels = await database.fetch_all(query, values)
    query = '''
        SELECT *
        FROM user_achievements ua INNER JOIN achievements ac
            ON ua.riddle = ac.riddle AND ua.title = ac.title
        WHERE TIMESTAMPDIFF(DAY, unlock_time, NOW()) < :days
    '''
    recent_achievements = await database.fetch_all(query, values)

    # Populate dict of recent scores by point sums
    for user_level in recent_levels:
        username = user_level['username']
        riddle = user_level['riddle']
        points = level_ranks[user_level['rank']]['points']
        recent_scores[username][riddle] += points
    for user_achievement in recent_achievements:
        username = user_achievement['username']
        riddle = user_achievement['riddle']
        points = cheevo_ranks[user_achievement['rank']]['points']
        recent_scores[username][riddle] += points

    for username in recent_scores:
        global_points = 0
        for riddle, riddle_points in recent_scores[username].items():
            # Update player's recent score for individual riddle
            query = '''
                UPDATE riddle_accounts
                SET recent_score = :points
                WHERE riddle = :riddle AND username = :username
            '''
            values = {
                'riddle': riddle,
                'username': username,
                'points': riddle_points,
            }
            await database.execute(query, values)
            global_points += riddle_points

        # Update player's global recent score
        query = '''
            UPDATE accounts
            SET recent_score = :points
            WHERE username = :username
        '''
        values = {'username': username, 'points': global_points}
        await database.execute(query, values)


async def _update_last_placements():
    '''Update players' last placements.'''

    # Update `last_placement` fields
    # in `accounts` with current player placements
    query = '''
        DROP TABLE IF EXISTS placements;
        CREATE TEMPORARY TABLE IF NOT EXISTS placements AS (
            SELECT username, RANK() OVER w AS idx
            FROM accounts
            WHERE global_score > 0
            WINDOW w AS (ORDER BY global_score DESC)
        );        
        UPDATE accounts AS acc
        SET last_placement = (
            SELECT idx FROM placements AS plc
            WHERE acc.username = plc.username
        )
        WHERE global_score > 0;
    '''
    await database.execute(query)

    # Update them also for individual riddles in `riddle_accounts`
    query = '''
        DROP TABLE IF EXISTS placements;
        CREATE TEMPORARY TABLE IF NOT EXISTS placements AS (
            SELECT riddle, username, RANK() OVER w AS idx
            FROM riddle_accounts
            WHERE score > 0
            WINDOW w AS (
                PARTITION BY riddle
                ORDER BY score DESC
            )
        );        
        UPDATE riddle_accounts AS racc
        SET last_placement = (
            SELECT idx FROM placements AS plc
            WHERE racc.riddle = plc.riddle
                AND racc.username = plc.username
        )
        WHERE score > 0;
    '''
    await database.execute(query)
