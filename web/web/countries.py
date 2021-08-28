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
    query = 'SELECT country, COUNT(*) AS player_count, ' \
                'SUM(global_score) AS total_score, ' \
                'AVG(global_score) AS avg_score ' \
            'FROM accounts ' \
            'WHERE global_score > 2000 ' \
            'GROUP BY country ' \
            'ORDER BY total_score DESC, avg_score DESC, player_count ASC'
    countries = await database.fetch_all(query)
    
    # Build list of countries, removing ones with fewer than 2 players
    # countries = []
    # for row in result:
    #     if row['player_count'] >= 2:
    #         countries.append(row)

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
