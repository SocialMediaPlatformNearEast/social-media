THEME_COLORS = {
    'primary': '#E7E9EA',
    'primary_hover': '#D7D9DA',
    'female': '#E7E9EA',
    'success': '#00BA7C',
    'danger': '#F4212E',
    'warning': '#F5C542',
    'orange': '#F97316',
    'purple': '#8B5CF6',
    'cyan': '#38BDF8',
    'muted': '#71767B',
}

PROFILE_COLOR_UNLOCK_LEVEL = 20

GENDER_THEME = {
    'Male': {
        'theme_color': THEME_COLORS['primary'],
        'avatar': 'assets/default-male-avatar.svg',
    },
    'Female': {
        'theme_color': THEME_COLORS['female'],
        'avatar': 'assets/default-female-avatar.svg',
    },
}

LEVEL_COLOR_UNLOCKS = [
    {'min_level': 50, 'color': THEME_COLORS['warning']},
    {'min_level': 30, 'color': THEME_COLORS['warning']},
    {'min_level': 20, 'color': THEME_COLORS['orange']},
    {'min_level': 10, 'color': THEME_COLORS['purple']},
    {'min_level': 5, 'color': THEME_COLORS['cyan']},
    {'min_level': 1, 'color': THEME_COLORS['muted']},
]


def level_color_for_level(level):
    level = max(1, int(level or 1))
    for unlock in LEVEL_COLOR_UNLOCKS:
        if level >= unlock['min_level']:
            return unlock['color']
    return THEME_COLORS['muted']


def profile_color_unlocked(level):
    return max(1, int(level or 1)) >= PROFILE_COLOR_UNLOCK_LEVEL
