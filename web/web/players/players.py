from functools import cmp_to_key
from typing import Optional

from quart import Blueprint, render_template

from auth import discord
from inject import get_achievements
from players.account import is_user_incognito
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
        SELECT * FROM accounts
        {'WHERE country = :country' if country else ''}
    """
    values = {}
    if country:
        values['country'] = country
    accounts = {
        acc['username']: dict(acc) | {
            'current_level': {},
            'cheevo_count': {},
            'has_incognito_progress': False,
        }
        for acc in await database.fetch_all(query, values)
    }

    # Incognito data
    user = await discord.get_user() if discord.user_id else None
    query = f"""
        SELECT * FROM _incognito_accounts
        {'WHERE country = :country' if country else ''}
    """
    incognito_accounts = await database.fetch_all(query, values)
    for iacc in incognito_accounts:
        if user and iacc['username'] == user.name:
            for key in ['global_score', 'recent_score']:
                accounts[iacc['username']][key] += iacc[key]

    # Order accounts by score, filtering out 0-score ones
    accounts = {
        acc['username']: acc
        for acc in sorted(
            accounts.values(), key=lambda acc: acc['global_score'], reverse=True
        ) if acc['global_score'] > 0
    }

    # Get current levels for each riddle and player (ignore unplayed ones)
    query = 'SELECT * FROM riddle_accounts'
    for racc in await database.fetch_all(query):
        if not racc['username'] in accounts:
            continue
        account = accounts[racc['username']]
        score, current_level = racc['score'], racc['current_level']
        if user and racc['username'] == user.name:
            # Take incognito progress into account for logged-in user
            query = '''
                SELECT * FROM _incognito_riddle_accounts
                WHERE riddle = :riddle AND username = :username
            '''
            values = {'riddle': racc['riddle'], 'username': racc['username']}
            if iracc := await database.fetch_one(query, values):
                score += iracc['score']
                current_level = iracc['current_level']
                account['has_incognito_progress'] |= bool(iracc['score'])
        if score:
            account['current_level'][racc['riddle']] = current_level

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
                if await has_player_mastered_riddle(alias, username):
                    player['mastered_riddles'].append(riddle)
                else:
                    player['completed_riddles'].append(riddle)
            else:
                player['other_riddles'].append(riddle)

    # Render page with account info
    return await render_template(
        'players/list.htm',
        accounts=accounts,
        country=country,
        riddles=riddles,
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

    # Get riddle page count
    query = '''
        SELECT COUNT(*) AS page_count FROM level_pages
        WHERE riddle = :riddle
            AND level_name IS NOT NULL
            AND hidden IS NOT TRUE
    '''
    values = {'riddle': alias}
    page_count = await database.fetch_val(query, values)

    # Get riddle level set info
    query = '''
        SELECT name, final_level, emoji FROM level_sets
        WHERE riddle = :riddle
    '''
    result = await database.fetch_all(query, values)
    sets_by_final_level = {row['final_level']: row for row in result}

    # Get players data from database
    query = f"""
        SELECT *
        FROM accounts AS acc INNER JOIN riddle_accounts racc
            ON acc.username = racc.username
        WHERE riddle = :riddle
            {'AND country = :country' if country else ''}
        ORDER BY racc.score DESC, last_page_time ASC
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

    # Incognito data
    user = await discord.get_user() if discord.user_id else None
    query = f"""
        SELECT *
        FROM accounts AS acc INNER JOIN _incognito_riddle_accounts racc
            ON acc.username = racc.username
        WHERE riddle = :riddle
            {'AND country = :country' if country else ''}
    """
    incognito_accounts = await database.fetch_all(query, values)
    for iacc in incognito_accounts:
        if user and iacc['username'] == user.name:
            account = accounts[iacc['username']]
            account['has_incognito_progress'] = False
            for key in ['score', 'recent_score', 'page_count']:
                account[key] += iacc[key]
                account['has_incognito_progress'] |= bool(iacc[key])
            account['last_page_time'] = iacc['last_page_time']

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
            # Show 💎 and register mastery time
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
                SELECT * FROM user_levels ul
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
                            AND (is_secret IS TRUE OR set_index >= 99)
                    ) {
                        'AND incognito_unlock IS NOT TRUE'
                        if not user or username != user.name else ''
                    }
            """
            levels = await database.fetch_all(query, values)
            for level in levels:
                name = level['level_name']
                if name not in players_by_level:
                    players_by_level[name] = set()
                players_by_level[name].add(username)
                is_session_user = bool(user and username == user.name)
                if (
                    level['completion_time']
                    and (not level['incognito_solve'] or is_session_user)
                ):
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
        a_time = a['last_page_time'].timestamp() if a['last_page_time'] else 0
        b_time = b['last_page_time'].timestamp() if b['last_page_time'] else 0
        a_data = (-a['score'], -a_count, a_time)
        b_data = (-b['score'], -b_count, b_time)
        return +1 if a_data < b_data else -1

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
