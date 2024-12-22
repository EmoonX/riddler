from quart import Blueprint, request, render_template, abort
from jinja2.exceptions import TemplateNotFound

# Create app blueprint
info = Blueprint('info', __name__)


@info.get('/<page>')
async def info_page(page: str):
    '''Simply show a info page by rendering its immediate template.
    Throws 404/405 if such template doesn't exist.'''
    path = 'info/%s.htm' % page
    try:
        return await render_template(path)
    except TemplateNotFound:
        if page == 'process':
            abort(405)
        else:
            abort(404)


@info.get('/thedudedude')
async def thedude():
    username = '????'
    disc = '????'
    from process import process_url
    from util.db import database
    first = 1
    last = 49
    inclusive = False
    query = 'SELECT * FROM levels ' \
            'WHERE riddle = "cipher" AND `index` >= :first AND `index` <= :last AND is_secret IS FALSE'
    values = {'first': first, 'last': last}
    levels = await database.fetch_all(query, values)
    for level in levels:
        front_path = 'http://gamemastertips.com/cipher' + level['path']
        answer_path = 'http://gamemastertips.com/cipher' + level['answer']
        image_path = front_path.rsplit('/', maxsplit=1)[0] + '/' + level['image']
        from time import sleep
        await process_url(username, disc, front_path)
        await process_url(username, disc, image_path)
        sleep(1)
        if level['index'] == last and not inclusive:
            break
        await process_url(username, disc, answer_path)
        sleep(1)
    
    return 'SUCCESS!', 200


@info.get('/theladylady')
async def thelady():
    username = 'Broccoli'
    disc = '8858'
    from process import process_url
    from util.db import database
    query = 'SELECT * FROM level_pages ' \
            'WHERE riddle = "cipher"'
    pages = await database.fetch_all(query)
    for page in pages:
        path = 'http://gamemastertips.com/cipher' + page['path']
        await process_url(username, disc, path)
        from time import sleep
        sleep(0.1)
    
    return 'SUCCESS!', 200


from util.db import database
from auth import discord
@info.route('/qwerty')
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
    print(cond_country)
    query = 'SELECT *, TIMESTAMPDIFF(SECOND, MIN(completion_time), MAX(completion_time)) / (24 * 3600) AS page_count FROM accounts AS acc ' \
            'INNER JOIN user_levels AS ul ' \
                'ON acc.username = ul.username ' \
            'WHERE global_score > 0 ' + cond_country + \
            'GROUP BY acc.username ' \
            'ORDER BY page_count DESC, global_score DESC, page_count DESC'
    result = await database.fetch_all(query)
    accounts = [dict(account) for account in result]

    # Get session user, if any
    user = await discord.get_user() if discord.user_id else None
    
    for account in accounts:
        # Hide username, country and riddles for
        # non logged-in `hidden` players
        if account['hidden']:        
            if not user and account['username'] == user.username:
                account['username'] = 'Anonymous'
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
            if riddle['creator_username'] == account['username']:
                account['created_riddles'].append(riddle)
                continue
            
            account['global_score'] = account['page_count']

            # Search for riddles already played
            query = 'SELECT * FROM riddle_accounts ' \
                    'WHERE riddle = :riddle AND username = :username'
            values = {
                'riddle': riddle['alias'],
                'username': account['username']
            }
            played = await database.fetch_one(query, values)
            if not played:
                continue

            # Check completion
            query = 'SELECT * FROM levels ' \
                    'WHERE riddle = :riddle ' \
                        'AND is_secret IS FALSE AND `name` NOT IN ( ' \
                            'SELECT level_name FROM user_levels ' \
                            'WHERE riddle = :riddle ' \
                                'AND username = :username ' \
                                'AND completion_time IS NOT NULL)'
            result = await database.fetch_one(query, values)
            completed = (result is None)
            if completed:
                # Get number of achievements user has gotten on riddle
                query = 'SELECT COUNT(*) as count FROM user_achievements ' \
                        'WHERE riddle = :riddle ' \
                            'AND username = :username '
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
