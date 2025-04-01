from functools import cmp_to_key
from typing import Optional

from quart import Blueprint, render_template

from auth import discord
from inject import get_achievements
from webclient import bot_request
from util.db import database
from util.levels import remove_ancestor_levels
from util.riddle import has_player_mastered_riddle

# Create app blueprint
players = Blueprint('players', __name__)


@players.get('/players')
@players.get('/players/<country>')
async def global_list(country: Optional[str] = None):
    '''Global (and country-wise) players list.'''

    # Get riddle data from database
    query = 'SELECT * FROM riddles'
    result = await database.fetch_all(query)
    riddles = {riddle['alias']: dict(riddle) for riddle in result}

    # Do the same for cheevo counts
    query = '''
        SELECT riddle, COUNT(*) as cheevo_count FROM achievements
        GROUP BY riddle
    '''
    cheevo_counts = await database.fetch_all(query)
    for row in cheevo_counts:
        alias = row['riddle']
        if alias not in riddles:
            continue
        riddles[alias]['cheevo_count'] = row['cheevo_count']

    # Init dict of (handle -> player info)
    accounts = {}
    query = f"""
        SELECT acc.*, SUM(page_count), MAX(last_page_time)
        FROM accounts AS acc INNER JOIN riddle_accounts AS racc
            ON acc.username = racc.username
        WHERE
            (
                global_score > 0
                OR acc.username IN (SELECT creator_username FROM riddles)
            )
            {'AND country = :country' if country else ''}
        GROUP BY acc.username
        ORDER BY global_score DESC, page_count DESC, last_page_time DESC
    """
    values = {}
    if country:
        values['country'] = country
    result = await database.fetch_all(query, values)
    for row in result:
        player = dict(row) | {'current_level': {}, 'cheevo_count': {}}
        accounts[row['username']] = player

    # Get current levels for each riddle and player (ignore unplayed ones)
    query = 'SELECT * FROM riddle_accounts WHERE score > 0'
    result = await database.fetch_all(query)
    for row in result:
        if not row['username'] in accounts:
            continue
        alias = row['riddle']
        accounts[row['username']]['current_level'][alias] = row['current_level']

    # Fetch players' cheevo counts and add them to dict
    query = '''
        SELECT riddle, username, COUNT(*) as cheevo_count
        FROM user_achievements
        GROUP BY riddle, username
    '''
    player_cheevo_counts = await database.fetch_all(query)
    for row in player_cheevo_counts:
        if not row['username'] in accounts:
            continue
        alias = row['riddle']
        accounts[row['username']]['cheevo_count'][alias] = row['cheevo_count']

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None

    for username, player in accounts.items():
        # Hide username, country and riddles for non logged-in `hidden` players
        if player['hidden']:
            if not user and username == user.username:
                player['username'] = 'Anonymous'
                player['country'] = 'ZZ'
                continue

        # Build list of riddles player has honors for
        player['created_riddles'] = []
        player['mastered_riddles'] = []
        player['completed_riddles'] = []
        player['other_riddles'] = []
        for alias, riddle in riddles.items():
            # Check if player is creator of current riddle
            if (riddle['creator_username'] == username):
                player['created_riddles'].append(riddle)
                continue

            # Check ir player played such riddle
            current_level = player['current_level'].get(alias)
            if not current_level:
                continue

            # Check completion
            completed = current_level == '🏅'
            if completed:
                # Append riddle to list of mastered or completed ones
                mastered = \
                    player['cheevo_count'][alias] == riddle['cheevo_count']
                if mastered:
                    player['mastered_riddles'].append(riddle)
                else:
                    player['completed_riddles'].append(riddle)
            else:
                player['other_riddles'].append(riddle)

    # Render page with account info
    return await render_template(
        'players/list.htm',
        players=accounts.values(), riddles=riddles, country=country
    )


@players.get('/<alias>/players')
@players.get('/<alias>/players/<country>')
async def riddle_list(alias: str, country: str | None = None):
    '''Riddle (and country-wise) player lists.'''

    # Get riddle data from database
    query = 'SELECT * from riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    riddle = dict(result)

    # Get riddle icon URL
    riddle['icon_url'] = f"/static/riddles/{alias}.png"

    # Get riddle page count & achievement info
    query = '''
        SELECT COUNT(*) AS page_count FROM level_pages
        WHERE riddle = :riddle AND level_name IS NOT NULL
    '''
    values = {'riddle': alias}
    page_count = await database.fetch_val(query, values)
    query = '''
        SELECT `title`, description, image, `rank` FROM achievements
        WHERE riddle = :riddle
    '''
    cheevos = await database.fetch_all(query, values)

    # Get riddle level set info
    query = '''
        SELECT name, final_level, emoji FROM level_sets
        WHERE riddle = :riddle
    '''
    result = await database.fetch_all(query, values)
    sets_by_final_level = {row['final_level']: row for row in result}

    # Get players data from database
    query = f"""
        SELECT racc.*,
            acc.display_name, acc.country,
            acc.global_score, acc.hidden
        FROM riddle_accounts racc
        INNER JOIN accounts AS acc
            ON racc.username = acc.username
        WHERE riddle = :riddle 
            {'AND country = :country' if country else ''}
            AND (
                racc.score > 0
                OR racc.username IN (
                    SELECT creator_username FROM riddles
                    WHERE alias = racc.riddle
                )
            )
        ORDER BY score DESC, last_page_time ASC
        LIMIT 1000
    """
    if country:
        values |= {'country': country}
    result = await database.fetch_all(query, values)
    accounts = {
        acc['username']: dict(acc) | {
            'current_level': [], 'completed_milestones': {}
        }
        for acc in result
    }

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None
    riddle_admin = False
    if user:
        # _, status = await admin.auth(alias)
        # if status == 200:
        if False:
            # Logged user is respective riddle's admin
            riddle_admin = True

    players_by_level = {}
    for username, account in accounts.items():
        # Get player country
        query = '''
            SELECT * FROM accounts
            WHERE username = :username
        '''
        values = {'username': username}
        result = await database.fetch_one(query, values)
        account['country'] = result['country']

        values |= {'riddle': alias}
        if await has_player_mastered_riddle(alias, username):
            # Show 💎 and register mastery time if player reached max score
            account['current_level'] = '💎'
            query = '''
                SELECT MAX(`time`) FROM ((
                    SELECT riddle, username, completion_time AS `time`
                    FROM user_levels
                ) UNION ALL (
                    SELECT riddle, username, unlock_time AS `time`
                    FROM user_achievements
                )) AS result
                WHERE riddle = :riddle AND username = :username
            '''
            account['mastered_on'] = await database.fetch_val(query, values)
        else:
            # Retrieve player's milestones and furthest reached levels
            query = f"""
                SELECT level_name, completion_time FROM user_levels ul
                WHERE riddle = :riddle
                    AND username = :username
                    AND (
                        completion_time IS NULL
                        OR (
                            completion_time IS NOT NULL
                            AND level_name NOT IN (
                                SELECT lr.level_name
                                FROM level_requirements lr
                                INNER JOIN user_levels u2
                                    ON lr.riddle = u2.riddle
                                    AND lr.level_name = u2.level_name
                                WHERE requires = ul.level_name
                            )
                        ) OR level_name IN (
                            SELECT final_level FROM level_sets
                            WHERE riddle = :riddle
                        ) OR level_name IN (
                            SELECT level_name FROM level_requirements
                            WHERE riddle = :riddle
                            GROUP BY level_name
                            HAVING COUNT(*) >= 2
                        )
                    ) AND level_name NOT IN (
                        SELECT name FROM levels lv
                        WHERE ul.riddle = lv.riddle
                            AND ul.level_name = lv.name
                            AND is_secret IS TRUE
                    )
            """
            levels = await database.fetch_all(query, values)
            for level in levels:
                name = level['level_name']
                if name not in players_by_level:
                    players_by_level[name] = set()
                players_by_level[name].add(username)
                if level['completion_time']:
                    account['completed_milestones'][name] = level

        # Add achievements dict
        account['cheevos'] = await get_achievements(alias, account)

        # Hide username and country for non logged-in `hidden` players
        # (ignored if current player is respective riddle's admin)
        if account['hidden'] and (
            not riddle_admin
            and not (user and username == user.username)
        ):
            account['username'] = 'Anonymous'
            account['country'] = 'ZZ'

    players_by_level = await remove_ancestor_levels(alias, players_by_level)
    for level, players in players_by_level.items():
        # aux = level.split()
        # if len(aux) >= 2:
        #     small = ' '.join(aux[:-1])
        #     level = f"<span class=\"small\">{small}</span>{aux[-1]}"
        for username in players:
            current_levels = accounts[username]['current_level']
            if current_levels != '💎':
                current_levels.append(level)

    # Pluck 0-score and creator accounts from main list
    creator_account = None
    aux = []
    for username, account in accounts.items():
        if username == riddle['creator_username']:
            creator_account = account
        elif account['score'] > 0:
            aux.append(account)
    accounts = aux

    def _account_cmp(a: dict, b: dict) -> int:
        '''Compare accounts first by score and then page count.'''
        a_count = a.get('page_count', 0)
        b_count = b.get('page_count', 0)
        return -1 if (a['score'], a_count) < (b['score'], b_count) else +1

    # Sort account list using custom key above
    cmp_key = cmp_to_key(_account_cmp)
    accounts = sorted(accounts, key=cmp_key, reverse=True)

    # Render page with account info
    return await render_template(
        'players/riddle/list.htm',
        alias=alias,
        accounts=accounts,
        country=country,
        creator_account=creator_account,       
        page_count=page_count,
        sets_by_final_level=sets_by_final_level,
    )
