from util.db import database

async def get_ancestor_levels(riddle: str, root_level: dict) -> dict:
    '''
    Build set of ancestor levels
    by applying a reverse BFS in requirements DAG.
    '''

    ancestor_levels = {}
    root_level = {
        'name': root_level['name'],
        'discord_name': root_level['discord_name'],
    }
    queue = [root_level]
    while queue:
        # Get top level from queue
        level = queue.pop(0)

        # Don't search node's children if level is final in set
        # (sole exception if this is the root level itself)
        query = '''
            SELECT name FROM level_sets
            WHERE riddle = :riddle AND final_level = :level_name
        '''
        values = {'riddle': riddle, 'level_name': level['name']}
        is_final_in_set = bool(await database.fetch_one(query, values))
        if is_final_in_set and len(ancestor_levels) > 1:
            continue

        # Fetch level requirements and add unseen ones to queue
        query = '''
            SELECT requires FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        result = await database.fetch_all(query, values)
        for row in result:
            query = '''
                SELECT name, discord_name FROM levels
                WHERE riddle = :riddle and name = :level_name
            '''
            values['level_name'] = row['requires']
            other = await database.fetch_one(query, values)
            if other['name'] not in ancestor_levels:
                queue.append(other)

        # Add level to dict
        ancestor_levels[level['name']] = level

    return ancestor_levels


async def remove_ancestor_levels(riddle: str, players_by_level: dict) -> dict:
    '''
    '''

    def _dfs(level: str, players_ahead: set = set()):

        visited.add(level)

        to_be_deleted = []
        for username in players_by_level.get(level, ()):
            if username not in players_ahead:
                players_ahead.add(username)
            else:
                to_be_deleted.append(username)
        for username in to_be_deleted:
            players_by_level[level].remove(username)

        for parent in requirement_graph.get(level, ()):
            _dfs(parent, players_ahead)

        to_be_deleted = []
        for username in players_by_level.get(level, ()):
            to_be_deleted.append(username)
        for username in to_be_deleted:
            players_ahead.remove(username)


    query = '''
        SELECT lv.name FROM levels lv
        INNER JOIN level_sets ls
            ON lv.level_set = ls.name
        WHERE lv.riddle = :riddle
        ORDER BY ls.`index`, lv.`index`
    '''
    values = {'riddle': riddle}
    result = await database.fetch_all(query, values)
    ordered_levels = [row['name'] for row in result]

    query = '''
        SELECT level_name, requires FROM level_requirements
        WHERE riddle = :riddle
    '''
    result = await database.fetch_all(query, values)
    requirement_graph = {}
    for row in result:
        name = row['level_name']
        if not name in requirement_graph:
            requirement_graph[name] = []
        requirement_graph[name].append(row['requires'])

    visited = set()
    for level in reversed(ordered_levels):
        if not level in visited:
            _dfs(level)

    return {
        level: players_by_level[level]
        for level in ordered_levels if level in players_by_level
    }
