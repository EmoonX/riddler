from functools import cmp_to_key

from quart import Blueprint, render_template

from auth import discord
from admin import admin
from webclient import bot_request
from util.db import database

# Create app blueprint
players = Blueprint('players', __name__)


@players.route('/')
@players.route('/players')
@players.route('/players/<country>')
async def global_list(country: str = None):
    '''Global (and by country) players list.'''

    # Get riddles data from database
    query = 'SELECT * from riddles ' \
            'WHERE unlisted IS FALSE'
    result = await database.fetch_all(query)
    riddles = [dict(riddle) for riddle in result]

    for riddle in riddles:   
        # Get total number of riddle achievements
        query = 'SELECT COUNT(*) as count FROM achievements ' \
                'WHERE riddle = :riddle'
        values = {'riddle': riddle['alias']}
        result = await database.fetch_one(query, values)
        riddle['cheevo_count'] = result['count']
    
    # Get players data from database
    cond_country = ('AND country = "%s" ' % country) if country else ''
    query = 'SELECT *, COUNT(*) AS page_count FROM accounts AS acc ' \
            'INNER JOIN user_pages AS up ' \
                'ON acc.username = up.username ' \
                    'AND acc.discriminator = up.discriminator ' \
            'WHERE global_score > 0 ' + cond_country + \
            'GROUP BY acc.username, acc.discriminator ' \
            'ORDER BY global_score DESC, page_count DESC'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None
    
    for account in accounts:
        # Hide username, country and riddles for
        # non logged-in `hidden` players
        if account['hidden']:        
            if not (user and account['username'] == user.username
                    and account['discriminator'] == user.discriminator):
                account['username'] = 'Anonymous'
                account['discriminator'] = '0000'
                account['country'] = 'ZZ'
                continue

        # Build list of riddles player has honors for
        account['created_riddles'] = []
        account['mastered_riddles'] = []
        account['completed_riddles'] = []
        account['other_riddles'] = []
        account['riddle_progress'] = {}
        for riddle in riddles:
            # Check if player is creator of current riddle
            if riddle['creator_username'] == account['username'] \
                    and riddle['creator_disc'] == account['discriminator']:
                account['created_riddles'].append(riddle)
                continue

            # Search for riddles already played
            query = 'SELECT * FROM riddle_accounts ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc '
            values = {'riddle': riddle['alias'],
                    'name': account['username'],
                    'disc': account['discriminator']}
            played = await database.fetch_one(query, values)
            if not played:
                continue

            # Check completion
            completed = (played['current_level'] == "🏅")
            if completed:
                # Get number of achievements user has gotten on riddle
                query = 'SELECT COUNT(*) as count FROM user_achievements ' \
                        'WHERE riddle = :riddle ' \
                            'AND username = :name AND discriminator = :disc '
                result = await database.fetch_one(query, values)
                
                # Append riddle to list of mastered or completed ones
                if result['count'] == riddle['cheevo_count']:
                    account['mastered_riddles'].append(riddle)
                else:
                    account['completed_riddles'].append(riddle)
            else:
                account['other_riddles'].append(riddle)
                account['riddle_progress'][riddle['alias']] = played['current_level']

    # Render page with account info
    return await render_template('players/list.htm',
            accounts=accounts, riddles=riddles, country=country)


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
    riddle['cheevo_count'] = result['count'];
    
    # Get players data from database
    cond_country = ('AND country = "%s" ' % country) if country else ''
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
            'WHERE score > 0 ' + cond_country + \
            'ORDER BY score DESC LIMIT 1000 '
    result = await database.fetch_all(query, {'riddle': alias})
    accounts = [dict(account) for account in result]

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None
    riddle_admin = False
    if user:
        _, status = await admin.auth(alias)
        if status == 200:
            # Logged user is respective riddle's admin
            riddle_admin = True

    for account in accounts:
        # Get player country
        query = 'SELECT * FROM accounts WHERE ' \
                'username = :name AND discriminator = :disc'
        values = {'name': account['username'],
                'disc': account['discriminator']}
        result = await database.fetch_one(query, values)
        account['country'] = result['country']
        
        # Get found pages count
        query = 'SELECT riddle, username, discriminator, ' \
                    'COUNT(*) AS page_count ' \
                'FROM user_pages ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc ' \
                'GROUP BY riddle, username, discriminator'
        values = {'riddle': alias, **values}
        result = await database.fetch_one(query, values)
        try:
            account['page_count'] = result['page_count']
        except:
            pass
        
        if account['current_level'] == '🏅':
            # Show 💎 if player has gotten all possible cheevos on riddle
            query = 'SELECT COUNT(*) as count FROM user_achievements ' \
                    'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc '
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
    creator_account = None
    for i, account in enumerate(accounts):
        if account['username'] == riddle['creator_username'] \
                and account['discriminator'] == riddle['creator_disc']:
            creator_account = account
            accounts.pop(i)
            break
    
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
