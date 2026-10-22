from util.db import database


async def get_all_players() -> dict[dict]:
    '''Retrieve all players.'''

    query = '''
        SELECT * FROM accounts
    '''
    result = await database.fetch_all(query)
    players = {row['username']: row for row in result}

    return players
