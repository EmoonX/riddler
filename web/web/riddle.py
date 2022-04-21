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

# Flavored score-based player ranks
h = lambda s, t, c : {'min_score': s, 'title': t, 'color': c}
player_ranks = [
    h(200000, 'Ascended Riddler', 'crimson'),
    h(100000, 'Master Riddler', 'orangered'),
    h(50000, 'Expert Riddler', 'goldenrod'),
    h(10000, 'Seasoned Riddler', 'greenyellow'),
    h(1000, 'Beginner Riddler', 'lightgreen'),
]
