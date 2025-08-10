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
        SELECT COUNT(*) AS count, COUNT(demo) AS demo_count FROM riddles
        WHERE unlisted IS NOT TRUE
    '''
    riddle_count, riddle_demo_count = (await database.fetch_one(query)).values()
    query = '''
        SELECT COUNT(*) AS count FROM levels
        WHERE riddle NOT IN (
            SELECT alias FROM riddles WHERE unlisted IS TRUE
        )
    '''
    level_count = await database.fetch_val(query)
    query = '''
        SELECT COUNT(*) AS count FROM level_pages
        WHERE
            riddle NOT IN (
                SELECT alias FROM riddles WHERE unlisted IS TRUE
            )
            AND level_name IS NOT NULL
            AND hidden IS NOT TRUE
    '''
    page_count = await database.fetch_val(query,)
    query = '''
        SELECT COUNT(*) AS count FROM accounts
        WHERE global_score > 0
    '''
    player_count = await database.fetch_val(query)

    # Recent player progress (newly found pages)
    query = '''
        SELECT *, MAX(access_time) AS time FROM user_pages
        WHERE TIMESTAMPDIFF(DAY, access_time, NOW()) < 30
            AND riddle NOT IN (
                SELECT alias FROM riddles WHERE unlisted IS TRUE
            )
            AND incognito IS NOT TRUE
        GROUP BY username
        ORDER BY time DESC
    '''
    recent_progress = await database.fetch_all(query)

    # Recent level find/completion data
    query = '''
        SELECT u1.*, completion_time AS time
        FROM user_levels u1 INNER JOIN (
            SELECT username, MAX(completion_time) AS max_time
            FROM user_levels
            WHERE TIMESTAMPDIFF(DAY, completion_time, NOW()) < 30
                AND incognito_solve IS NOT TRUE
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
    recently_completed = {row['username']: row for row in result}
    query = '''
        SELECT u1.*, find_time AS time
        FROM user_levels u1 INNER JOIN (
            SELECT username, MAX(find_time) AS max_time
            FROM user_levels ul INNER JOIN levels lv
                ON ul.riddle = lv.riddle AND ul.level_name = lv.name
            WHERE lv.is_secret IS TRUE
                AND TIMESTAMPDIFF(DAY, find_time, NOW()) < 30
                AND incognito_unlock IS NOT TRUE
            GROUP BY username
        ) u2
        ON u1.username = u2.username
            AND u1.find_time = u2.max_time
        WHERE u1.riddle NOT IN (
            SELECT alias FROM riddles WHERE unlisted IS TRUE
        )
        ORDER BY find_time DESC
    '''
    result = await database.fetch_all(query)
    secrets_recently_found = {row['username']: row for row in result}

    # Swap generic progress for find/completion whenever it happened
    for i, row in enumerate(recent_progress):
        get_time = lambda table: (
            table[row['username']]['time'].timestamp()
            if row['username'] in table else 0
        )
        secret_find_time = get_time(secrets_recently_found)
        completion_time = get_time(recently_completed)
        if secret_find_time and secret_find_time >= completion_time:
            recent_progress[i] = dict(secrets_recently_found[row['username']])
            recent_progress[i]['is_secret_find'] = True
        elif completion_time:
            recent_progress[i] = dict(recently_completed[row['username']])
            recent_progress[i]['is_solve'] = True

    # Ensure final list is time-sorted
    recent_progress.sort(key=(lambda x: x['time']), reverse=True)

    return await render_template('home.htm', **locals())
