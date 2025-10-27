from quart import Blueprint, render_template

from util.db import database

# Create app blueprint
countries = Blueprint('countries', __name__)

# Dict of pairs (alpha_2 -> short_country_name)
country_names = {}


@countries.get("/countries")
async def global_list():
    '''Global countries list.'''

    # Get player (+ riddle account) data from DB
    query = '''
        SELECT racc.*, LEFT(acc.country, 2) AS country
        FROM riddle_accounts AS racc INNER JOIN accounts AS acc
            ON racc.username = acc.username
        WHERE score > 0
    '''
    riddle_accounts = await database.fetch_all(query)

    # Build countries dict with data
    country_dict = {}
    for racc in riddle_accounts:
        alpha_2 = racc['country']
        country = country_dict.get(
            alpha_2,
            {'honors': 0, 'players': set(), 'total_score': 0}
        )
        if racc['current_level'] == '🏅':
            country['honors'] += 1
        country['players'].add(racc['username'])
        country['total_score'] += racc['score']
        country_dict[alpha_2] = country

    # Calculate further info from data
    for country in country_dict.values():
        country['player_count'] = len(country['players'])
        country['average_score'] = \
            round(country['total_score'] / country['player_count'])

    # Generate ranked country list from dict
    key = lambda c: (
        c['honors'], c['average_score'],
        c['total_score'], c['player_count']
    )
    country_list = [
        {'country': alpha_2} | country
            for alpha_2, country in country_dict.items()
    ]
    country_list.sort(key=key, reverse=True)

    # Render page with countries info
    return await render_template(
        'countries/global.htm', countries=country_list
    )


# @countries.get("/<alias>/countries")
async def riddle_list(alias: str):
    '''Riddle countries list.'''

    # Get riddle-specific countries data from DB
    query = '''
        SELECT LEFT(country, 2) AS country, COUNT(*) AS player_count,
            SUM(score) AS total_score, AVG(score) AS avg_score
        FROM riddle_accounts AS r_acc INNER JOIN accounts AS acc
            ON r_acc.username = acc.username
        WHERE riddle = :riddle AND score > 1000
        GROUP BY country
        ORDER BY total_score DESC, avg_score DESC, player_count ASC
    '''
    countries_list = await database.fetch_all(query, {'riddle': alias})

    # Build list of countries, removing ones with fewer than 2 players
    # countries = []
    # for row in result:
    #     if row['player_count'] >= 2:
    #         countries.append(row)

    # Render page with countries info
    return await render_template(
        'countries/riddle.htm', alias=alias, countries=countries_list
    )
