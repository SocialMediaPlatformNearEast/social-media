from datetime import date, datetime


MIN_AGE = 13
MAX_AGE = 120


def normalize_username(value):
    return (value or '').strip().lower()


def _replace_year(value, year):
    try:
        return value.replace(year=year)
    except ValueError:
        return value.replace(year=year, day=28)


def birthday_date_limits(today=None):
    today = today or date.today()
    return {
        'min': _replace_year(today, today.year - MAX_AGE),
        'max': _replace_year(today, today.year - MIN_AGE),
    }


def validate_birthday(value, required=False, today=None):
    value = (value or '').strip()
    if not value:
        if required:
            return None, "Birthday is required."
        return None, None

    try:
        birthday = datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None, "Birthday must use a real date in YYYY-MM-DD format."

    today = today or date.today()
    limits = birthday_date_limits(today)
    if birthday > today:
        return None, "Birthday cannot be in the future."
    if birthday > limits['max']:
        return None, f"You must be at least {MIN_AGE} years old to use LvL."
    if birthday < limits['min']:
        return None, "Birthday must be a realistic date."
    return birthday, None


def profile_banner_for_level(level):
    level = max(1, int(level or 1))
    if level >= 20:
        return {
            'class': 'level-5',
            'label': 'Mythic Circuit',
            'description': 'A high-rank banner for long-running LvL legends.',
        }
    if level >= 10:
        return {
            'class': 'level-4',
            'label': 'Hero Pulse',
            'description': 'A brighter profile stage for proven community energy.',
        }
    if level >= 5:
        return {
            'class': 'level-3',
            'label': 'Rising Charge',
            'description': 'A stronger banner for active members gaining momentum.',
        }
    if level >= 2:
        return {
            'class': 'level-2',
            'label': 'Neon Climb',
            'description': 'Your first upgraded LvL banner.',
        }
    return {
        'class': 'level-1',
        'label': 'First Step',
        'description': 'The starter banner for new LvL profiles.',
    }
