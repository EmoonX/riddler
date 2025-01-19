from util.db import database


async def has_player_mastered_riddle(alias: str, username: str) -> bool:
    '''Check if player has gotten all possible points in riddle.'''

    async def _is_final_level_up() -> bool:
        query = '''
            SELECT 1 FROM levels
            WHERE riddle = :alias AND name = (
                SELECT final_level FROM riddles
                WHERE alias = :alias
            )
        '''
        values = {'alias': alias}
        return bool(await database.fetch_val(query, values))

    async def _has_player_beaten_all_levels() -> bool:
        query = '''
            SELECT 1 FROM levels
            WHERE riddle = :riddle AND name NOT IN (
                SELECT level_name FROM user_levels
                WHERE riddle = :riddle AND username = :username
                    AND completion_time IS NOT NULL
            )
        '''
        values = {'riddle': alias, 'username': username}
        return await database.fetch_val(query, values) is None

    async def _has_player_unlocked_all_cheevos() -> bool:
        query = '''
            SELECT 1 FROM achievements
            WHERE riddle = :riddle AND title NOT IN (
                SELECT title FROM user_achievements
                WHERE riddle = :riddle AND username = :username
            )
        '''
        values = {'riddle': alias, 'username': username}
        return await database.fetch_val(query, values) is None

    return (
        await _is_final_level_up()
        and await _has_player_beaten_all_levels()
        and await _has_player_unlocked_all_cheevos()
    )
