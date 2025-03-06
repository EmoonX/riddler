from functools import cmp_to_key

from quart import Blueprint, render_template

from auth import discord
from inject import get_achievements
from webclient import bot_request
from util.db import database

# Create app blueprint
home = Blueprint('home', __name__)


@home.route('/')
@home.route('/home')
async def homepage():
    '''Frontpage for the website.'''

    # Big number counters
    query = '''
        SELECT COUNT(*) count FROM riddles
        WHERE unlisted IS NOT TRUE
    '''
    riddle_count = await database.fetch_val(query, column='count')
    query = '''
        SELECT COUNT(*) count FROM levels
        WHERE riddle NOT IN (
            SELECT alias FROM riddles WHERE unlisted IS TRUE
        )
    '''
    level_count = await database.fetch_val(query, column='count')
    query = '''
        SELECT COUNT(*) count FROM level_pages
        WHERE
            riddle NOT IN (
                SELECT alias FROM riddles WHERE unlisted IS TRUE
            )
            AND level_name IS NOT NULL
    '''
    page_count = await database.fetch_val(query, column='count')
    query = '''
        SELECT COUNT(*) count FROM accounts
        WHERE global_score > 0
    '''
    player_count = await database.fetch_val(query, column='count')

    # Recent player progress (newly found pages)
    query = '''
        SELECT *, MAX(access_time) AS time FROM user_pages
        WHERE
            TIMESTAMPDIFF(MONTH, access_time, NOW()) < 30
            AND riddle NOT IN (
                SELECT alias FROM riddles WHERE unlisted IS TRUE
            )
        GROUP BY username
        ORDER BY time DESC
    '''
    recent_progress = await database.fetch_all(query)

    # Recent player level completion data
    query = '''
        SELECT u1.*, completion_time AS time
        FROM user_levels u1 INNER JOIN (
            SELECT username, MAX(completion_time) AS max_time
            FROM user_levels
            WHERE TIMESTAMPDIFF(MONTH, completion_time, NOW()) < 30
            GROUP BY username
        ) u2
        ON u1.username = u2.username
            AND u1.completion_time = u2.max_time
        WHERE u1.riddle NOT IN (
            SELECT alias FROM riddles WHERE unlisted IS TRUE
        )
        ORDER BY completion_time DESC
    '''
    result = await database.fetch_all(query)
    recent_levels = {row['username']: row for row in result}
    
    # Swap generic progress for completion whenever it happened
    for i, row in enumerate(recent_progress):
        if row['username'] in recent_levels:
            recent_progress[i] = dict(recent_levels[row['username']])
            recent_progress[i]['is_completion'] = True

    # Ensure final list is time-sorted
    recent_progress.sort(key=(lambda x: x['time']), reverse=True)

    return await render_template('home.htm', **locals())
