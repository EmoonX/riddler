from functools import cmp_to_key

from quart import Blueprint, render_template

from auth import discord
from admin import admin
from inject import get_achievements
from webclient import bot_request
from util.db import database

# Create app blueprint
players = Blueprint('players', __name__)


@players.route('/')
@players.route('/players')
@players.route('/players/<country>')
async def global_list(country: str = None):
    '''Global (and by country) players list.'''

    # Get riddle data from database (minus unlisted ones) as a dict
    query = 'SELECT * FROM riddles ' \
            'WHERE unlisted IS FALSE '
    result = await database.fetch_all(query)
    riddles = {riddle['alias']: dict(riddle) for riddle in result}

    # Fetch riddles' last level and cheevo counts and add them to dict
    query = 'SELECT l1.*, l1.name AS name ' \
            'FROM levels AS l1 INNER JOIN (' \
                'SELECT riddle, MAX(`index`) AS max_index FROM levels ' \
                'WHERE is_secret IS NOT TRUE ' \
                'GROUP BY riddle ' \
            ') AS l2 ' \
                'ON l1.riddle = l2.riddle AND l1.`index` = l2.max_index'
    last_levels = await database.fetch_all(query)
    for row in last_levels:
        alias = row['riddle']
        if alias not in riddles:
            continue
        riddles[alias]['last_level'] = row['name']
    query = 'SELECT riddle, COUNT(*) as cheevo_count ' \
            'FROM achievements ' \
            'GROUP BY riddle'
    cheevo_counts = await database.fetch_all(query)
    for row in cheevo_counts:
        alias = row['riddle']
        if alias not in riddles:
            continue
        riddles[alias]['cheevo_count'] = row['cheevo_count']

    # Get players data from database
    cond_country = ('AND country = "%s" ' % country) if country else ''
    query = 'SELECT *, SUM(page_count) ' \
            'FROM accounts AS acc INNER JOIN riddle_accounts AS racc ' \
                'ON acc.username = racc.username ' \
                    'AND acc.discriminator = racc.discriminator ' \
            'WHERE global_score > 0 ' + cond_country + \
            'GROUP BY acc.username, acc.discriminator ' \
            'ORDER BY global_score DESC, page_count DESC'
    result = await database.fetch_all(query)

    # Init dict of (handle -> player info)
    players = {}
    for row in result:
        handle = '%s#%s' % (row['username'], row['discriminator'])
        player = dict(row) | {'last_level': {}, 'cheevo_count': {}}
        players[handle] = player

    # Fetch players' last found level add them to dict
    query = 'SELECT u1.* ' \
            'FROM user_levels AS u1 INNER JOIN ( ' \
                'SELECT riddle, username, discriminator, ' \
                    'MAX(find_time) AS max_find ' \
                'FROM user_levels AS ul ' \
                'WHERE level_name NOT IN ( ' \
                    'SELECT name FROM levels AS lv ' \
                    'WHERE ul.riddle = lv.riddle ' \
                        'AND is_secret IS TRUE ) ' \
                'GROUP BY riddle, username, discriminator ' \
            ') AS u2 ' \
                'ON u1.riddle = u2.riddle ' \
                    'AND u1.username = u2.username ' \
                    'AND u1.discriminator = u2.discriminator ' \
                    'AND u1.find_time = u2.max_find'
    player_last_levels = await database.fetch_all(query)
    for row in player_last_levels:
        handle = '%s#%s' % (row['username'], row['discriminator'])
        if not handle in players:
            continue
        alias = row['riddle']
        players[handle]['last_level'][alias] = row['level_name']
    
    # Fetch players' cheevo counts and add them to dict
    query = 'SELECT riddle, username, discriminator, ' \
                'COUNT(*) as cheevo_count ' \
            'FROM user_achievements ' \
            'GROUP BY riddle, username, discriminator'
    player_cheevo_counts = await database.fetch_all(query)
    for row in player_cheevo_counts:
        handle = '%s#%s' % (row['username'], row['discriminator'])
        if not handle in players:
            continue
        alias = row['riddle']
        players[handle]['cheevo_count'][alias] = row['cheevo_count']

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None

    for handle, player in players.items():
        # Hide username, country and riddles for
        # non logged-in `hidden` players
        if player['hidden']:        
            if not (user and player['username'] == user.username
                    and player['discriminator'] == user.discriminator):
                player['username'] = 'Anonymous'
                player['discriminator'] = '0000'
                player['country'] = 'ZZ'
                continue

        # Build list of riddles player has honors for
        player['created_riddles'] = []
        player['mastered_riddles'] = []
        player['completed_riddles'] = []
        player['other_riddles'] = []
        for alias, riddle in riddles.items():
            # Check if player is creator of current riddle
            if riddle['creator_username'] == player['username'] \
                    and riddle['creator_disc'] == player['discriminator']:
                player['created_riddles'].append(riddle)
                continue

            # Check ir player played such riddle
            played = alias in player['last_level']
            if not played:
                continue

            # Check completion
            completed = player['last_level'][alias] == riddle['last_level']
            if completed:                
                # Append riddle to list of mastered or completed ones
                mastered = player['cheevo_count'][alias] \
                        == riddle['cheevo_count']
                if mastered:
                    player['mastered_riddles'].append(riddle)
                else:
                    player['completed_riddles'].append(riddle)
            else:
                player['other_riddles'].append(riddle)

    # Render page with account info
    return await render_template('players/list.htm',
            players=players.values(), riddles=riddles, country=country)


@players.route('/<alias>/players')
@players.route('/<alias>/players/<country>')
async def riddle_list(alias: str, country: str = None):
    '''Riddle (and by country) player lists.'''

    # Get riddle data from database
    query = 'SELECT * from riddles WHERE alias = :alias'
    result = await database.fetch_one(query, {'alias': alias})
    riddle = dict(result)

    # Get riddles' icon URL
    url = await bot_request('get-riddle-icon-url',
            guild_id=riddle['guild_id'])
    riddle['icon_url'] = url
    
    # Get total number of riddle achievements
    query = 'SELECT COUNT(*) as count FROM achievements ' \
            'WHERE riddle = :riddle'
    values = {'riddle': riddle['alias']}
    result = await database.fetch_one(query, values)
    riddle['cheevo_count'] = result['count']
    
    # Get players data from database
    cond_country = ('WHERE country = "%s" ' % country) if country else ''
    query = 'SELECT * FROM (' \
            '(SELECT *, 999999 AS `index`, ' \
                    '2 AS filter FROM riddle_accounts ' \
                'WHERE riddle_accounts.riddle = :riddle ' + \
                    'AND current_level = "🏅") ' \
            'UNION ALL ' \
            '(SELECT riddle_accounts.*, levels.`index`, ' \
                    '1 AS filter FROM riddle_accounts ' \
                'INNER JOIN levels ' \
                'ON current_level = levels.name ' \
                'WHERE riddle_accounts.riddle = :riddle ' \
                    'AND levels.riddle = :riddle) ' \
            ') AS result ' \
            'INNER JOIN accounts AS acc ' \
                'ON result.username = acc.username ' \
                    'AND result.discriminator = acc.discriminator ' \
            + cond_country + \
            'ORDER BY score DESC LIMIT 1000 '
    result = await database.fetch_all(query, {'riddle': alias})
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
        query = 'SELECT * FROM accounts ' \
                'WHERE username = :username AND discriminator = :disc'
        values = {'username': account['username'],
                'disc': account['discriminator']}
        result = await database.fetch_one(query, values)
        account['country'] = result['country']

        # Fetch achievement dict
        account['cheevos'] = await get_achievements(alias, account)
        
        if account['current_level'] == '🏅':
            # Show 💎 if player has gotten all possible cheevos on riddle
            query = 'SELECT COUNT(*) as count FROM user_achievements ' \
                    'WHERE riddle = :riddle ' \
                    'AND username = :username AND discriminator = :disc '
            values = {'riddle': alias, **values}
            result = await database.fetch_one(query, values)
            if result['count'] == riddle['cheevo_count']:
                account['current_level'] = '💎'
        
        # Hide username and country for non logged-in `hidden` players
        # (ignored if current player is respective riddle's admin)
        if account['hidden']:        
            if not riddle_admin and \
                    not (user and account['username'] == user.username
                    and account['discriminator'] == user.discriminator):
                account['username'] = 'Anonymous'
                account['discriminator'] = '0000'
                account['country'] = 'ZZ'

    # Pluck creator account from main list to show it separately 👑
    # Also, remove 0-score accounts.
    creator_account = None
    aux = []
    for account in accounts:
        if account['username'] == riddle['creator_username'] \
                and account['discriminator'] == riddle['creator_disc']:
            creator_account = account
        elif account['score'] > 0:
            aux.append(account)
    accounts = aux
    
    def _account_cmp(a, b):
        '''Compare accounts first by score and then page count.'''
        if a['score'] == b['score']:
            a_count = a['page_count'] if 'page_count' in a else 0
            b_count = b['page_count'] if 'page_count' in b else 0
            return 1 if a_count < b_count else -1
        return 1 if a['score'] < b['score'] else -1

    # Sort account list using custom key above
    cmp_key = cmp_to_key(_account_cmp)
    accounts.sort(key=cmp_key)

    # Render page with account info
    return await render_template('players/riddle/list.htm',
            alias=alias, creator_account=creator_account,
            accounts=accounts, country=country)
