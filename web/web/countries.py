from quart import Blueprint, render_template

from util.db import database

# Create app blueprint
countries = Blueprint('countries', __name__)

# Dict of pairs (alpha_2 -> short_country_name)
country_names = {}


@countries.route("/countries")
async def global_list():
    '''Global countries list.'''

    # Get countries data (player count and score) from DB
    query = 'SELECT * FROM accounts ' \
            'WHERE global_score > 0 '
    players = await database.fetch_all(query)

    # Check completion
    query = 'SELECT country, COUNT(*) AS count ' \
                'FROM riddle_accounts AS racc ' \
            'INNER JOIN accounts AS acc ' \
                'ON racc.username = acc.username ' \
                    'AND racc.discriminator = acc.discriminator ' \
            'WHERE current_level = "🏅" ' \
            'GROUP BY racc.username, racc.discriminator '
    result = await database.fetch_all(query)
    honors = {row['country']: row['count'] for row in result}   

    countries = {}
    for player in players:
        country = player['country']
        if not country in countries:
            countries[country] = {
                'honors': 0, 'player_count': 0, 'total_score': 0
            }
        if country in honors:
            countries[country]['honors'] += honors[country]
        countries[country]['player_count'] += 1
        countries[country]['total_score'] += player['global_score']
    
    for country in countries.values():
        country['average_score'] = \
                int(country['total_score'] / country['player_count'])
    
    key = lambda c: (c['honors'], c['average_score'],
            c['total_score'], c['player_count'])
    countries = [{'country': alpha_2, **country}
            for alpha_2, country in countries.items()]
    countries = sorted(countries, key=key, reverse=True) 

    # Render page with countries info
    return await render_template('countries/global.htm',
            countries=countries)


@countries.route("/<alias>/countries")
async def riddle_list(alias: str):
    '''Riddle countries list.'''

    # Get riddle-specific countries data from DB
    query = 'SELECT country, COUNT(*) AS player_count, ' \
                'SUM(score) AS total_score, ' \
                'AVG(score) AS avg_score ' \
            'FROM riddle_accounts AS r_acc ' \
                'INNER JOIN accounts AS acc ' \
                'ON r_acc.username = acc.username ' \
                    'AND r_acc.discriminator = acc.discriminator ' \
            'WHERE riddle = :riddle AND score > 1000 ' \
            'GROUP BY country ' \
            'ORDER BY total_score DESC, avg_score DESC, player_count ASC'
    values = {'riddle': alias}
    countries = await database.fetch_all(query, values)
    
    # Build list of countries, removing ones with fewer than 2 players
    # countries = []
    # for row in result:
    #     if row['player_count'] >= 2:
    #         countries.append(row)

    # Render page with countries info
    return await render_template('countries/riddle.htm',
            alias=alias, countries=countries)
