from auth import discord
from util.db import database


async def has_player_mastered_riddle(alias: str, username: str) -> bool:
    '''Check whether player has gotten all the available points in a riddle.'''

    user = await discord.get_user() if discord.user_id else None
    is_session_user = bool(user and username == user.name)

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
        query = f"""
            SELECT 1 FROM levels
            WHERE riddle = :riddle
                AND rank != 'F'
                AND name NOT IN (
                    SELECT level_name FROM user_levels
                    WHERE riddle = :riddle AND username = :username
                        AND completion_time IS NOT NULL
                        {
                            'AND incognito_solve IS NOT TRUE'
                            if not is_session_user else ''
                        }
                )
        """
        values = {'riddle': alias, 'username': username}
        return await database.fetch_val(query, values) is None

    async def _has_player_unlocked_all_cheevos() -> bool:
        query = f"""
            SELECT 1 FROM achievements
            WHERE riddle = :riddle AND title NOT IN (
                SELECT title FROM user_achievements
                WHERE riddle = :riddle AND username = :username
                {'AND incognito IS NOT TRUE' if not is_session_user else ''}
            )
        """
        values = {'riddle': alias, 'username': username}
        return await database.fetch_val(query, values) is None

    return (
        await _is_final_level_up()
        and await _has_player_beaten_all_levels()
        and await _has_player_unlocked_all_cheevos()
    )
