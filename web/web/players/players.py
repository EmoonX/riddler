from quart import Blueprint, render_template

from webclient import bot_request
from util.db import database

# Create app blueprint
players = Blueprint('players', __name__)


@players.route("/")
@players.route("/players")
async def global_list():
    """Global player list."""

    # Get riddles data from database
    query = 'SELECT * from riddles ' \
            'WHERE unlisted IS FALSE'
    result = await database.fetch_all(query)
    riddles = [dict(riddle) for riddle in result]

    for riddle in riddles:
        # Get riddle's icon URL
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
    query = 'SELECT * FROM accounts ' \
            'WHERE global_score > 0 ' \
            'ORDER BY global_score DESC'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]
    
    for account in accounts:
        # Build list of riddle account has beaten (so far)
        account['mastered_riddles'] = []
        account['completed_riddles'] = []        
        for riddle in riddles:
            query = 'SELECT * FROM riddle_accounts ' \
                    'WHERE riddle = :riddle ' \
                        'AND username = :name AND discriminator = :disc ' \
                        'AND current_level = "🏅"'
            values = {'riddle': riddle['alias'],
                    'name': account['username'], 'disc': account['discriminator']}
            completed = await database.fetch_one(query, values)
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

    # Render page with account info
    return await render_template('players/list.htm',
            accounts=accounts, riddles=riddles)


@players.route("/<alias>/players")
async def riddle_list(alias: str):
    """Riddle player list."""

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
    query = 'SELECT * FROM (' \
            '(SELECT *, 999999 AS `index`, ' \
                    '2 AS filter FROM riddle_accounts ' \
                'WHERE riddle_accounts.riddle = :riddle ' \
                    'AND current_level = "🏅") ' \
            'UNION ALL ' \
            '(SELECT riddle_accounts.*, levels.`index`, ' \
                    '1 AS filter FROM riddle_accounts ' \
                'INNER JOIN levels ' \
                'ON current_level = levels.name ' \
                'WHERE riddle_accounts.riddle = :riddle ' \
                    'AND levels.riddle = :riddle) ' \
            ') AS result ' \
            'ORDER BY `index` DESC, score DESC LIMIT 1000 '
    result = await database.fetch_all(query, {'riddle': alias})
    accounts = [dict(account) for account in result]

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
        result = await database.fetch_one(query, values);
        account['page_count'] = result['page_count']
        
        # Show 💎 if player has gotten all possible cheevos on riddle
        query = 'SELECT COUNT(*) as count FROM user_achievements ' \
                'WHERE riddle = :riddle ' \
                    'AND username = :name AND discriminator = :disc '
        result = await database.fetch_one(query, values)
        if result['count'] == riddle['cheevo_count']:
            account['current_level'] = '💎'

    # Render page with account info
    return await render_template('players/riddle/list.htm',
            alias=alias, accounts=accounts)
