'''Riddle-related stuff (like level/cheevo scoring and info).'''

# Dict of pairs rank -> (points, color)
f = lambda p, c : {'points': p, 'color': c}
level_ranks = {
    'D': f(50, 'cornflowerblue'),
    'C': f(100, 'lawngreen'),
    'B': f(200, 'gold'),
    'A': f(400, 'crimson'),
    'S': f(1200, 'lightcyan')
}

# Colors for achievements outline based on ranks
g = lambda e, p, s, c, d : {
    'emoji': e, 'points': p, 'size': s, 'color': c, 'description': d
}
cheevo_ranks = {
    'C': g(
        '🥉', 50, 40, 'firebrick',
        '"Dumb" and/or easy-to-reach cheevos.'
    ),
    'B': g(
        '🥈', 100, 50, 'lightcyan',
        'Substancial ones that require creativity '
            'and/or out-of-the-box thinking.'
    ),
    'A': g(
        '🥇', 200, 60, 'gold',
        'Good challenges like secret levels or very well hidden eggs.'
    ),
    'S': g(
        '💎', 500, 80, 'darkturquoise',
        'Should be reserved for the best among the best '
         '(like reaching a vital game\'s landmark).'
    )
}
