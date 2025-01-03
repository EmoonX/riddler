from functools import cmp_to_key
from typing import Optional

from quart import Blueprint, render_template

from auth import discord
from inject import get_achievements
from webclient import bot_request
from util.db import database

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
async def riddle_list(alias: str, country: Optional[str] = None):
    '''Riddle (and country-wise) player lists.'''

    # Get riddle data from database
    query = 'SELECT * from riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    riddle = dict(result)

    # Get riddles' icon URL
    url = await bot_request(
        'get-riddle-icon-url', guild_id=riddle['guild_id']
    )
    if not url:
        url = f"/static/riddles/{alias}.png"
    riddle['icon_url'] = url

    # Get all level and achievement required non-sensitive info from riddle
    values = {'riddle': alias}
    query = '''
        SELECT `name` FROM levels
        WHERE riddle = :riddle
    '''
    levels = await database.fetch_all(query, values)
    query = '''
        SELECT `title`, description, image, `rank` FROM achievements
        WHERE riddle = :riddle
    '''
    cheevos = await database.fetch_all(query, values)

    # Get players data from database
    cond_country = 'WHERE country = :country ' if country else ''
    query = f'''
        SELECT result.*,
            acc.display_name, acc.country,
            acc.global_score, acc.hidden
        FROM ((
            SELECT *, 999999 AS `index`, 2 AS filter
            FROM riddle_accounts AS racc
            WHERE (racc.riddle = :riddle AND current_level = "🏅")
                OR racc.username = (
                    SELECT username FROM riddles AS r
                    WHERE r.alias = :riddle
                        AND racc.username = r.creator_username
                ) 
        ) UNION ALL (
            SELECT racc.*, lv.`index`, 1 AS filter
            FROM riddle_accounts AS racc
            INNER JOIN levels AS lv
                ON current_level = lv.name
            WHERE racc.riddle = :riddle AND lv.riddle = :riddle
        )) AS result
        INNER JOIN accounts AS acc
            ON result.username = acc.username
        {cond_country}
        ORDER BY score DESC, last_page_time DESC
        LIMIT 1000
    '''
    if country:
        values['country'] = country
    result = await database.fetch_all(query, values)
    accounts = [dict(account) for account in result]

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None
    riddle_admin = False
    if user:
        # _, status = await admin.auth(alias)
        # if status == 200:
        if False:
            # Logged user is respective riddle's admin
            riddle_admin = True

    for account in accounts:
        # Get player country
        query = '''
            SELECT * FROM accounts
            WHERE username = :username
        '''
        values = {'username': account['username']}
        result = await database.fetch_one(query, values)
        account['country'] = result['country']

        # Fetch achievement dict
        account['cheevos'] = await get_achievements(alias, account)

        if account['current_level'] == '🏅':
            # Show 💎 if player has gotten all possible points in riddle
            query = '''
                SELECT COUNT(*) as count FROM ((
                    SELECT `level_name` AS name FROM user_levels
                    WHERE riddle = :riddle AND username = :username
                        AND completion_time IS NOT NULL
                ) UNION ALL (
                    SELECT `title` AS name FROM user_achievements
                    WHERE riddle = :riddle AND username = :username
                )) AS result
            '''
            values |= {'riddle': alias}
            result = await database.fetch_one(query, values)
            if result['count'] == len(levels) + len(cheevos):
                account['current_level'] = '💎'

        # Hide username and country for non logged-in `hidden` players
        # (ignored if current player is respective riddle's admin)
        if account['hidden']:
            if (
                not riddle_admin and
                not (user and account['username'] == user.username)
            ):
                account['username'] = 'Anonymous'
                account['country'] = 'ZZ'

    # Pluck 0-score and creator accounts from main list
    creator_account = None
    aux = []
    for account in accounts:
        if account['username'] == riddle['creator_username']:
            creator_account = account
        elif account['score'] > 0:
            aux.append(account)
    accounts = aux

    def _account_cmp(a, b):
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
        alias=alias, creator_account=creator_account,
        accounts=accounts, country=country
    )
