import os
import re
import secrets
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from supabase import create_client, Client
import bcrypt
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app_utils import birthday_date_limits, normalize_username, profile_banner_for_level, validate_birthday
from app_theme import GENDER_THEME, PROFILE_COLOR_UNLOCK_LEVEL, THEME_COLORS, level_color_for_level, profile_color_unlocked

load_dotenv()

from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__, static_folder='static', template_folder='templates')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-default-key")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True
)
logging.basicConfig(level=logging.INFO)

url: str = os.getenv("SUPABASE_URL", "")
key: str = os.getenv("SUPABASE_SECRET", os.getenv("SUPABASE_KEY", ""))
supabase: Client = create_client(url, key) if url and key else None
LOGIN_ATTEMPTS = {}
LOGIN_WINDOW = timedelta(minutes=10)
LOGIN_MAX_ATTEMPTS = 5
PASSWORD_RESET_TOKENS = {}
PASSWORD_RESET_TTL = timedelta(minutes=30)
POSTS_PER_PAGE = 10
POST_SELECT_QUERY = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
MAX_IMAGE_BYTES = 50 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "lvl-media")
MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", 100 * 1024 * 1024))
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'm4v'}
SUPABASE_VIDEO_BUCKET = os.getenv("SUPABASE_VIDEO_BUCKET", STORAGE_BUCKET)
LOCAL_IMAGE_UPLOAD_FALLBACK = os.getenv("LOCAL_IMAGE_UPLOAD_FALLBACK", "true").lower() not in {"0", "false", "no"}
IMAGE_CONTENT_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
}
VIDEO_CONTENT_TYPES = {
    'mp4': 'video/mp4',
    'webm': 'video/webm',
    'mov': 'video/quicktime',
    'm4v': 'video/x-m4v',
}
ASSET_VERSION = "92"
HOME_REEL_PREVIEW_LIMIT = 12
HOME_MEDIA_PREVIEW_LIMIT = 12

GENDER_OPTIONS = GENDER_THEME
SUPABASE_SOCIAL_PROVIDERS = [
    {'provider': 'google', 'label': 'Google', 'icon': 'G', 'class': 'google'},
]
SUPABASE_SOCIAL_PROVIDER_IDS = {provider['provider'] for provider in SUPABASE_SOCIAL_PROVIDERS}
SUPABASE_SOCIAL_PROVIDER_ALIASES = {}
COMMUNITY_DEFAULT_TAB = 'following'
COMMUNITY_TIMELINE_TABS = [
    {
        'key': 'followers',
        'label': 'Followers',
        'eyebrow': 'They follow you',
        'title': 'Posts from people who follow you',
        'description': 'See what the people already connected to you are sharing.',
        'empty_title': 'No follower posts yet',
        'empty_text': 'When someone who follows you posts, it will appear here.',
        'empty_help': 'This tab is for seeing your audience from the other side: people who follow you, even if you do not follow them back.',
        'empty_action_label': 'Search members',
        'empty_action_url': 'search'
    },
    {
        'key': 'following',
        'label': 'Following',
        'eyebrow': 'Your picks',
        'title': 'Posts from people you follow',
        'description': 'Your main community timeline, focused on accounts you chose.',
        'empty_title': 'Follow people to fill this timeline',
        'empty_text': 'Search for members or open profiles and follow them to build this feed.',
        'empty_help': 'This is the middle timeline and should feel like your chosen feed: accounts you intentionally follow.',
        'empty_action_label': 'Find people',
        'empty_action_url': 'search'
    },
    {
        'key': 'community',
        'label': 'Community',
        'eyebrow': 'Groups and threads',
        'title': 'Community threads across LvL',
        'description': 'Group posts and public threads ranked by activity and relevance.',
        'empty_title': 'No community threads yet',
        'empty_text': 'Join or create a community, then start a thread.',
        'empty_help': 'This tab is for shared rooms and topic threads, separate from personal follower/following feeds.',
        'empty_action_label': 'Create group',
        'empty_action_url': 'create_community'
    }
]

@app.before_request
def check_supabase():
    if request.method == 'POST':
        token = session.get('csrf_token')
        submitted = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not submitted or not secrets.compare_digest(token, submitted):
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': 'Security check failed. Refresh the page and try again.'}), 400
            flash("Security check failed. Refresh the page and try again.", "error")
            return redirect(safe_redirect_url(url_for('index')))
    public_auth_endpoints = {'static', 'service_worker', 'auth', 'forgot_password', 'reset_password'}
    if not supabase and request.endpoint in {'auth', 'forgot_password', 'reset_password'}:
        flash("Supabase connection failed. Add SUPABASE_URL and SUPABASE_SECRET to your .env file.", "error")
    elif not supabase and not app.config.get('TESTING') and request.endpoint not in public_auth_endpoints:
        flash("Database connection error.", "error")
        return redirect(url_for('auth'))

@app.context_processor
def inject_helpers():
    return {
        'csrf_token': get_csrf_token,
        'level_title': activity_title_for_level,
        'birthday_limits': birthday_date_limits,
        'theme_colors': THEME_COLORS,
        'display_profile_color': display_profile_color,
        'profile_color_unlocked': profile_color_unlocked,
        'profile_color_unlock_level': PROFILE_COLOR_UNLOCK_LEVEL,
        'static_asset': static_asset_url,
        'relative_time': relative_time,
        'oauth_providers': SUPABASE_SOCIAL_PROVIDERS,
    }

@app.context_processor
def inject_unread_count():
    user_id = session.get('user_id')
    return {
        'unread_notification_count': unread_notification_count(user_id),
        'unread_message_count': unread_message_count(user_id),
    }

def unread_notification_count(user_id):
    if not user_id or not supabase:
        return 0
    try:
        res = supabase.table('notifications').select('id', count='exact').eq('user_id', user_id).eq('is_read', False).execute()
        return res.count or 0
    except Exception:
        return 0

def unread_message_count(user_id):
    if not user_id or not supabase:
        return 0
    try:
        res = supabase.table('messages').select('id', count='exact').eq('receiver_id', user_id).eq('is_read', False).execute()
        return res.count or 0
    except Exception:
        return 0

import markupsafe

@app.template_filter('linkify_mentions')
def linkify_mentions_filter(text):
    if not text:
        return ""
    import re
    escaped_text = markupsafe.escape(text)
    pattern = r'@([a-zA-Z0-9_]+)'
    def replace_match(match):
        username = match.group(1)
        return f'<a href="/profile/{username}" class="mention-link" style="color: var(--lvl-primary); text-decoration: none; font-weight: bold;">@{username}</a>'
    linked_text = re.sub(pattern, replace_match, str(escaped_text))
    return markupsafe.Markup(linked_text)

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    app.logger.exception("Unhandled application error")
    return render_template('error.html', title="Something went wrong"), 500

def get_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token

def safe_redirect_url(target=None, fallback_endpoint='index'):
    fallback = url_for(fallback_endpoint)
    target = target or request.referrer or fallback
    parsed = urlparse(target)
    if parsed.netloc and parsed.netloc != request.host:
        return fallback
    if parsed.scheme and parsed.scheme not in {'http', 'https'}:
        return fallback
    return target

def external_url_for(endpoint, base_env='APP_BASE_URL', **values):
    base_url = (os.getenv(base_env) or os.getenv('APP_BASE_URL') or '').strip().rstrip('/')
    path = url_for(endpoint, **values)
    if base_url:
        configured_host = urlparse(base_url).hostname or ''
        request_host = request.host.split(':', 1)[0]
        configured_is_loopback = configured_host in {'127.0.0.1', 'localhost', '::1'}
        request_is_loopback = request_host in {'127.0.0.1', 'localhost', '::1'}
        if configured_is_loopback and not request_is_loopback:
            return url_for(endpoint, _external=True, **values)
        return f"{base_url}{path}"
    return url_for(endpoint, _external=True, **values)

def oauth_redirect_url():
    return external_url_for('oauth_callback', base_env='OAUTH_REDIRECT_BASE_URL')

def password_reset_token_hash(token):
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()

def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def env_truthy(value, default=True):
    if value is None or str(value).strip() == '':
        return default
    return str(value).strip().lower() not in {'0', 'false', 'no', 'off'}

def mail_settings():
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USERNAME") or os.getenv("SMTP_FROM")
    password = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("MAIL_FROM") or os.getenv("SMTP_FROM") or username
    host = os.getenv("MAIL_HOST") or os.getenv("SMTP_HOST") or "smtp.gmail.com"
    port = parse_int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT")) or 587
    use_tls = env_truthy(os.getenv("MAIL_USE_TLS") or os.getenv("SMTP_USE_TLS"), default=True)
    return {
        'username': username,
        'password': password,
        'from_email': from_email,
        'host': host,
        'port': port,
        'use_tls': use_tls,
    }

def parse_positive_int(value, default=1, maximum=100):
    parsed = parse_int(value)
    if not parsed or parsed < 1:
        return default
    return min(parsed, maximum)

def login_attempt_key(username):
    return f"{request.remote_addr or 'local'}:{(username or '').strip().lower()}"

def login_is_limited(username):
    now = datetime.utcnow()
    key = login_attempt_key(username)
    record = LOGIN_ATTEMPTS.get(key, {'count': 0, 'first_seen': now})
    if now - record['first_seen'] > LOGIN_WINDOW:
        LOGIN_ATTEMPTS.pop(key, None)
        return False
    return record['count'] >= LOGIN_MAX_ATTEMPTS

def record_login_failure(username):
    now = datetime.utcnow()
    key = login_attempt_key(username)
    record = LOGIN_ATTEMPTS.get(key, {'count': 0, 'first_seen': now})
    if now - record['first_seen'] > LOGIN_WINDOW:
        record = {'count': 0, 'first_seen': now}
    record['count'] += 1
    LOGIN_ATTEMPTS[key] = record

def clear_login_failures(username):
    LOGIN_ATTEMPTS.pop(login_attempt_key(username), None)

def xp_required_for_level(level):
    level = max(1, level)
    early = {1: 0, 2: 50, 3: 120, 4: 250, 5: 500, 6: 700, 7: 900, 8: 1100, 9: 1300, 10: 1500}
    if level in early: return early[level]
    return 1500 + ((level - 10) * (level - 10) * 50)

def level_for_xp(total_xp):
    level = 1
    while total_xp >= xp_required_for_level(level + 1):
        level += 1
    return level

def badge_color_for_level(level):
    return level_color_for_level(level)

def activity_title_for_level(level):
    if level >= 50:
        return 'Icon Legend'
    if level >= 30: return 'Mythic Legend'
    if level >= 20: return 'Elite Champion'
    if level >= 10: return 'Rising Hero'
    if level >= 5: return 'Quest Regular'
    return 'New Adventurer'

def level_update_payload(level, current_total_xp=0):
    level = max(1, parse_int(level) or 1)
    required_xp = xp_required_for_level(level)
    return {
        'level': level,
        'total_xp': max(parse_int(current_total_xp) or 0, required_xp),
        'badge_color': badge_color_for_level(level),
        'activity_title': activity_title_for_level(level),
    }

def set_user_level(username, level):
    username = normalize_username(username)
    if not username:
        raise ValueError("Choose a username.")
    level = parse_positive_int(level, default=0, maximum=500)
    if level < 1:
        raise ValueError("Choose a valid level.")

    res = supabase.table('users').select('id,username,total_xp').eq('username', username).execute()
    if not res or not res.data:
        raise LookupError("User not found.")

    user = res.data[0]
    updates = level_update_payload(level, user.get('total_xp'))
    update_res = supabase.table('users').update(updates).eq('id', user['id']).execute()
    updated = update_res.data[0] if update_res and update_res.data else {**user, **updates}
    return apply_forced_user_levels(updated)

def admin_token_is_valid(token):
    expected = os.getenv("LVL_ADMIN_TOKEN", "")
    return bool(expected and token and secrets.compare_digest(str(token), expected))

FORCED_LEVEL_ACCOUNT_ALIASES = {'sin', 'sin sin', 'sinsin', 'user sin', 'usersin'}
FORCED_LEVEL_ACCOUNT_LEVEL = 50

def forced_level_identifier(value):
    value = re.sub(r'[_-]+', ' ', str(value or '').strip().lower())
    return re.sub(r'\s+', ' ', value).strip()

def forced_level_for_user(user):
    if not isinstance(user, dict):
        return None
    identifiers = []
    for key in ('username', 'nickname', 'display_name'):
        identifiers.append(forced_level_identifier(user.get(key)))
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}"
    identifiers.append(forced_level_identifier(full_name))

    for identifier in identifiers:
        if not identifier:
            continue
        if identifier in FORCED_LEVEL_ACCOUNT_ALIASES or identifier.replace(' ', '') in FORCED_LEVEL_ACCOUNT_ALIASES:
            return FORCED_LEVEL_ACCOUNT_LEVEL
    return None

def apply_forced_user_levels(value, _seen=None):
    if _seen is None:
        _seen = set()
    if isinstance(value, list):
        for item in value:
            apply_forced_user_levels(item, _seen)
        return value
    if not isinstance(value, dict):
        return value

    value_id = id(value)
    if value_id in _seen:
        return value
    _seen.add(value_id)

    forced_level = forced_level_for_user(value)
    if forced_level:
        forced_total_xp = xp_required_for_level(forced_level)
        value['level'] = forced_level
        value['total_xp'] = max(parse_int(value.get('total_xp')) or 0, forced_total_xp)
        value['badge_color'] = badge_color_for_level(forced_level)
        value['activity_title'] = activity_title_for_level(forced_level)

    for nested in value.values():
        if isinstance(nested, (dict, list)):
            apply_forced_user_levels(nested, _seen)
    return value

def get_forced_level_users():
    forced_users = {}
    queries = [
        ('username', 'sin'),
        ('nickname', 'sin'),
        ('display_name', '%User Sin%'),
        ('display_name', '%sin sin%'),
    ]
    for column, matcher in queries:
        try:
            query = supabase.table('users').select('*')
            if '%' in matcher:
                query = query.ilike(column, matcher)
            else:
                query = query.eq(column, matcher)
            res = query.limit(5).execute()
            for user in res.data or []:
                apply_forced_user_levels(user)
                forced_users[user['id']] = user
        except Exception:
            pass
    return list(forced_users.values())

def merge_forced_level_users(users, limit=None):
    users = apply_forced_user_levels(list(users or []))
    users_by_id = {user.get('id'): user for user in users if user.get('id')}
    for user in get_forced_level_users():
        if user.get('id') not in users_by_id:
            users.append(user)
    users.sort(key=lambda item: (parse_int(item.get('level')) or 1, item.get('display_name') or item.get('username') or ''), reverse=True)
    return users[:limit] if limit else users

XP_REWARD_RULES = [
    {'label': 'Daily login', 'points': 5, 'description': 'Open LvL once per day.'},
    {'label': 'Create a post', 'points': 10, 'description': 'Share a normal profile post.'},
    {'label': 'Create a community post', 'points': 8, 'description': 'Start a post inside a community.'},
    {'label': 'Write a comment', 'points': 6, 'description': 'Reply to another post.'},
    {'label': 'Receive a comment', 'points': 4, 'description': 'Someone comments on your post.'},
    {'label': 'Give a like', 'points': 1, 'description': 'Like another post.'},
    {'label': 'Receive a like', 'points': 2, 'description': 'Someone likes your post.'},
    {'label': 'Repost', 'points': 5, 'description': 'Share another post again.'},
]

LEVEL_REWARD_TIERS = [
    {'level': 5, 'label': 'Emoji Kit', 'description': 'Unlock first profile expression tools and a cyan LvL badge.'},
    {'level': 10, 'label': 'Rising Medal', 'description': 'Unlock a purple medal badge, title upgrade, and stronger profile status.'},
    {'level': 15, 'label': 'Avatar Frame', 'description': 'Unlock avatar border styles that make your profile stand out.'},
    {'level': 20, 'label': 'Profile Color', 'description': 'Unlock custom profile colors and the Elite Champion title.'},
    {'level': 30, 'label': 'Mythic Badge', 'description': 'Unlock a gold medal badge and premium public status.'},
    {'level': 50, 'label': 'App Icon Recolor', 'description': 'Unlock the first prestige icon recolor tier for long-term players.'},
]

LEVEL_REWARD_PRODUCT_TABLE = [
    {
        'level': '1-4',
        'reward': 'Default identity',
        'type': 'Baseline',
        'visual': 'Black and white profile, standard avatar border, default LvL badge.',
        'purpose': 'Keeps new accounts clean and makes later color rewards feel earned.'
    },
    {
        'level': '5',
        'reward': 'Emoji Kit',
        'type': 'Expression',
        'visual': 'First emoji/profile expression tools plus the cyan LvL badge color.',
        'purpose': 'Small visible reward for early activity.'
    },
    {
        'level': '10',
        'reward': 'Rising Medal',
        'type': 'Badge',
        'visual': 'Purple medal styling and a stronger public rank title.',
        'purpose': 'Shows that the account has moved past beginner status.'
    },
    {
        'level': '15',
        'reward': 'Avatar Frame',
        'type': 'Profile',
        'visual': 'Avatar border styles for profile and feed identity.',
        'purpose': 'Adds recognition without changing the whole theme too early.'
    },
    {
        'level': '20',
        'reward': 'Profile Color',
        'type': 'Customization',
        'visual': 'Custom profile color for banners, chat headers, and profile accents.',
        'purpose': 'Unlocks personal color only after enough visible participation.'
    },
    {
        'level': '30',
        'reward': 'Mythic Badge',
        'type': 'Prestige',
        'visual': 'Gold public badge treatment and premium status visuals.',
        'purpose': 'Rewards long-term activity with a clearly rare look.'
    },
    {
        'level': '50+',
        'reward': 'App Icon Recolor',
        'type': 'Prestige',
        'visual': 'First special LvL icon recolor tier for very active members.',
        'purpose': 'Creates a long-term chase reward without affecting core usability.'
    },
]

ACHIEVEMENT_DEFINITIONS = [
    {'id': 'first_post', 'name': 'First Post', 'description': 'Share your first post.', 'metric': 'posts', 'target': 1},
    {'id': 'active_poster', 'name': 'Active Poster', 'description': 'Share 5 posts.', 'metric': 'posts', 'target': 5},
    {'id': 'conversation_starter', 'name': 'Conversation Starter', 'description': 'Write 10 comments.', 'metric': 'comments', 'target': 10},
    {'id': 'known_member', 'name': 'Known Member', 'description': 'Reach 5 followers.', 'metric': 'followers', 'target': 5},
    {'id': 'squad_builder', 'name': 'Squad Builder', 'description': 'Connect with 3 friends.', 'metric': 'friends', 'target': 3},
    {'id': 'xp_collector', 'name': 'XP Collector', 'description': 'Earn 1,000 total XP.', 'metric': 'total_xp', 'target': 1000},
    {'id': 'rising_member', 'name': 'Rising Member', 'description': 'Reach LvL 5.', 'metric': 'level', 'target': 5},
    {'id': 'hero_status', 'name': 'Hero Status', 'description': 'Reach LvL 10.', 'metric': 'level', 'target': 10},
    {'id': 'elite_champion', 'name': 'Elite Champion', 'description': 'Reach LvL 20.', 'metric': 'level', 'target': 20},
    {'id': 'mythic_legend', 'name': 'Mythic Legend', 'description': 'Reach LvL 30.', 'metric': 'level', 'target': 30},
]

def next_level_reward_for_level(level):
    for reward in LEVEL_REWARD_TIERS:
        if level < reward['level']:
            return reward
    return {'level': level, 'label': 'Max prestige track', 'description': 'Keep earning XP to hold a top community position.'}

def profile_achievements(profile, stats):
    metric_values = {
        'posts': stats.get('posts', 0),
        'comments': stats.get('comments', 0),
        'followers': stats.get('followers', 0),
        'friends': stats.get('friends', 0),
        'level': profile.get('level', 1),
        'total_xp': profile.get('total_xp', 0),
    }
    achievements = []
    for item in ACHIEVEMENT_DEFINITIONS:
        current = max(0, int(metric_values.get(item['metric']) or 0))
        target = max(1, int(item['target']))
        capped_current = min(current, target)
        achievements.append({
            **item,
            'current': current,
            'progress': min(100, (capped_current / target) * 100),
            'progress_label': f"{capped_current} / {target}",
            'unlocked': current >= target,
        })
    return achievements

def achievement_summary(achievements):
    return {
        'unlocked': sum(1 for item in achievements if item['unlocked']),
        'total': len(achievements),
    }

def update_streak(sender_id, receiver_id):
    """
    Increment the daily streak between two users when sender sends receiver a message.
    Called at most once per calendar day per pair (idempotent within the same day).
    Returns (streak_count, xp_awarded).
    XP is tiered to stay balanced: 3 XP days 2-6, 5 XP days 7-29, 8 XP days 30+.
    """
    if not supabase:
        return 0, 0
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        first = min(sender_id, receiver_id)
        second = max(sender_id, receiver_id)

        res = supabase.table('user_streaks').select('*').eq('user_1', first).eq('user_2', second).execute()

        if not res.data:
            supabase.table('user_streaks').insert({
                'user_1': first, 'user_2': second,
                'streak_count': 1, 'last_streak_date': today
            }).execute()
            return 1, 0

        streak = res.data[0]
        last_date = streak.get('last_streak_date', '')
        count = streak.get('streak_count', 1)

        if last_date == today:
            return count, 0  # Already interacted today

        new_count = (count + 1) if last_date == yesterday else 1

        supabase.table('user_streaks').update({
            'streak_count': new_count,
            'last_streak_date': today,
            'updated_at': datetime.now().isoformat()
        }).eq('user_1', first).eq('user_2', second).execute()

        xp = 0
        if new_count >= 2:
            xp = 3 if new_count < 7 else (5 if new_count < 30 else 8)
            award_xp(sender_id, 'streak', xp, event_key=f'streak_{first}_{second}_{today}')
        return new_count, xp
    except Exception:
        return 0, 0

def parse_streak_date(value):
    if not value:
        return None
    if hasattr(value, 'date') and not isinstance(value, str):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None

def active_streak_count(streak_row, today=None):
    if not streak_row:
        return 0
    today = today or datetime.now().date()
    last_date = parse_streak_date(streak_row.get('last_streak_date'))
    if not last_date:
        return 0
    if (today - last_date).days >= 2:
        return 0
    return max(0, parse_int(streak_row.get('streak_count')) or 0)

def is_streak_friend(streak_row, today=None):
    return active_streak_count(streak_row, today=today) >= 7

def get_pair_streak_status(user_a, user_b):
    status = {
        'count': 0,
        'is_friend': False,
        'days_until_friend': 7,
        'last_streak_date': None,
    }
    if not supabase or not user_a or not user_b or user_a == user_b:
        return status
    try:
        first = min(user_a, user_b)
        second = max(user_a, user_b)
        res = supabase.table('user_streaks').select('*').eq('user_1', first).eq('user_2', second).execute()
        streak = res.data[0] if res and res.data else None
        count = active_streak_count(streak)
        status.update({
            'count': count,
            'is_friend': count >= 7,
            'days_until_friend': max(0, 7 - count),
            'last_streak_date': streak.get('last_streak_date') if streak else None,
        })
    except Exception:
        pass
    return status

def get_streak_friend_ids(profile_id):
    if not supabase or not profile_id:
        return {}, []
    try:
        rows = supabase.table('user_streaks').select('user_1,user_2,streak_count,last_streak_date').or_(f"user_1.eq.{profile_id},user_2.eq.{profile_id}").execute()
    except Exception:
        return {}, []

    today = datetime.now().date()
    streaks_by_user = {}
    ordered_ids = []
    for row in rows.data or []:
        if not is_streak_friend(row, today=today):
            continue
        other_id = row.get('user_2') if row.get('user_1') == profile_id else row.get('user_1')
        if not other_id or other_id in streaks_by_user:
            continue
        streaks_by_user[other_id] = active_streak_count(row, today=today)
        ordered_ids.append(other_id)
    return streaks_by_user, ordered_ids

def award_xp(user_id, event_type, points, event_key=''):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        event_key = str(event_key)[:120] if event_key else today

        supabase.table('xp_events').insert({
            'user_id': user_id,
            'event_type': event_type,
            'event_key': event_key,
            'points': points,
            'reward_date': today
        }).execute()

        user_res = supabase.table('users').select('total_xp', 'level').eq('id', user_id).execute()
        if user_res.data:
            user = user_res.data[0]
            new_total = user['total_xp'] + points
            new_level = level_for_xp(new_total)
            badge_color = badge_color_for_level(new_level)
            title = activity_title_for_level(new_level)

            supabase.table('users').update({
                'total_xp': new_total,
                'level': new_level,
                'badge_color': badge_color,
                'activity_title': title
            }).eq('id', user_id).execute()

            if new_level > user['level']:
                flash(f"Level up! You reached LvL {new_level}.", "success")
    except Exception:
        pass

def get_current_user():
    if 'user_id' in session:
        try:
            res = supabase.table('users').select('*').eq('id', session['user_id']).execute()
            if res.data:
                return apply_forced_user_levels(res.data[0])
        except Exception:
            return None
    return None

def handle_db_error(e, default_msg="An error occurred. Please try again."):
    error_msg = str(e)
    if hasattr(e, 'message'):
        error_msg += " " + e.message
    if "nodename nor servname provided" in error_msg or "Could not resolve host" in error_msg:
        return "Supabase connection failed. Check your Project URL/DNS and .env values."
    if "Invalid API key" in error_msg or "JWSError" in error_msg or "JWT" in error_msg:
        return "Supabase key appears to be invalid. Check your SUPABASE_SECRET value."
    if "users_nickname_key" in error_msg or "users_username_key" in error_msg:
        return "This username is already taken."
    if "users_email_key" in error_msg:
        return "This email is already registered."
    return default_msg

@app.route('/service-worker.js')
def service_worker():
    response = send_from_directory(app.static_folder, 'service-worker.js', max_age=0)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def static_asset_url(filename):
    return url_for('static', filename=filename, v=ASSET_VERSION)

def normalize_gender(value):
    value = (value or '').strip().title()
    return value if value in GENDER_OPTIONS else ''

def gender_defaults(gender):
    return GENDER_OPTIONS.get(gender, GENDER_OPTIONS['Male'])

def normalize_oauth_provider(provider):
    provider = (provider or '').strip().lower()
    provider = SUPABASE_SOCIAL_PROVIDER_ALIASES.get(provider, provider)
    return provider if provider in SUPABASE_SOCIAL_PROVIDER_IDS else ''

def oauth_provider_label(provider):
    provider = normalize_oauth_provider(provider)
    for item in SUPABASE_SOCIAL_PROVIDERS:
        if item['provider'] == provider:
            return item['label']
    return 'social login'

def oauth_attr(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)

def oauth_storage_key(auth_client, suffix):
    storage_key = getattr(auth_client, '_storage_key', 'supabase.auth.token')
    return f"{storage_key}-{suffix}"

def store_oauth_code_verifier(auth_client):
    storage = getattr(auth_client, '_storage', None)
    if not storage:
        return
    verifier = storage.get_item(oauth_storage_key(auth_client, 'code-verifier'))
    if verifier:
        session['oauth_code_verifier'] = verifier

def restore_oauth_code_verifier(auth_client):
    verifier = session.get('oauth_code_verifier')
    storage = getattr(auth_client, '_storage', None)
    if verifier and storage:
        storage.set_item(oauth_storage_key(auth_client, 'code-verifier'), verifier)

def clear_oauth_flow_session(include_pending=False):
    for key in ['oauth_state', 'oauth_provider', 'oauth_code_verifier']:
        session.pop(key, None)
    if include_pending:
        session.pop('pending_oauth_profile', None)

def split_oauth_name(display_name):
    parts = (display_name or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])

def extract_oauth_profile(auth_user, fallback_provider=''):
    metadata = oauth_attr(auth_user, 'user_metadata', {}) or {}
    app_metadata = oauth_attr(auth_user, 'app_metadata', {}) or {}
    provider = normalize_oauth_provider(
        fallback_provider or
        app_metadata.get('provider') or
        metadata.get('provider')
    )
    email = (oauth_attr(auth_user, 'email', '') or metadata.get('email') or '').strip().lower()
    display_name = (
        metadata.get('full_name') or
        metadata.get('name') or
        metadata.get('display_name') or
        metadata.get('user_name') or
        metadata.get('preferred_username') or
        (email.split('@', 1)[0] if email else '')
    ).strip()
    first_name = (metadata.get('given_name') or '').strip()
    last_name = (metadata.get('family_name') or '').strip()
    if not first_name and not last_name:
        first_name, last_name = split_oauth_name(display_name)

    return {
        'provider': provider,
        'subject': str(oauth_attr(auth_user, 'id', '') or metadata.get('sub') or ''),
        'email': email,
        'display_name': display_name,
        'first_name': first_name,
        'last_name': last_name,
        'avatar_url': metadata.get('avatar_url') or metadata.get('picture') or metadata.get('profile_image_url') or '',
    }

def oauth_suggested_username(profile):
    base = normalize_username(
        profile.get('display_name') or
        (profile.get('email') or '').split('@', 1)[0] or
        profile.get('first_name') or
        ''
    )
    return base[:24] if len(base) >= 3 else ''

def first_oauth_user_match(profile):
    query_attempts = []
    if profile.get('subject'):
        query_attempts.extend([
            [('supabase_auth_user_id', profile['subject'])],
            [('oauth_provider', profile.get('provider')), ('oauth_subject', profile['subject'])],
        ])
    if profile.get('email'):
        query_attempts.append([('email', profile['email'])])

    for filters in query_attempts:
        try:
            query = supabase.table('users').select('*')
            for column, value in filters:
                if value:
                    query = query.eq(column, value)
            res = query.execute()
            if res.data:
                return res.data[0]
        except Exception:
            continue
    return None

def sync_oauth_user_fields(user, profile):
    if not user or not profile:
        return
    updates = {
        'oauth_provider': profile.get('provider'),
        'oauth_subject': profile.get('subject'),
        'supabase_auth_user_id': profile.get('subject'),
        'oauth_email': profile.get('email'),
    }
    if profile.get('avatar_url') and not user.get('profile_photo_url'):
        updates['profile_photo_url'] = profile['avatar_url']
    try:
        supabase.table('users').update(updates).eq('id', user['id']).execute()
    except Exception:
        pass

def oauth_schema_error(exc):
    message = str(exc)
    return any(column in message for column in [
        'supabase_auth_user_id',
        'oauth_provider',
        'oauth_subject',
        'oauth_email',
    ])

def normalize_hex_color(value, fallback=THEME_COLORS['primary']):
    value = (value or '').strip()
    return value.upper() if re.match(r'^#[0-9A-Fa-f]{6}$', value) else fallback

def display_profile_color(user):
    if not user:
        return THEME_COLORS['muted']
    level = parse_int(user.get('level')) or 1
    stored = normalize_hex_color(user.get('theme_color') or user.get('avatar_color'), THEME_COLORS['muted'])
    return stored if profile_color_unlocked(level) else THEME_COLORS['muted']

def normalize_website(value):
    value = (value or '').strip()
    if not value:
        return ''
    return value if re.match(r'^https?://', value) else ''

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def ensure_media_bucket(bucket_name, file_size_limit, allowed_mime_types):
    if not supabase:
        raise RuntimeError("Supabase is not configured.")
    try:
        supabase.storage.get_bucket(bucket_name)
    except Exception:
        supabase.storage.create_bucket(bucket_name, options={
            "public": True,
            "file_size_limit": file_size_limit,
            "allowed_mime_types": allowed_mime_types
        })

def ensure_storage_bucket(bucket_name):
    ensure_media_bucket(bucket_name, MAX_IMAGE_BYTES, [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp"
    ])

def safe_upload_folder(folder):
    parts = []
    for part in (folder or '').split('/'):
        safe_part = secure_filename(part)
        if safe_part:
            parts.append(safe_part)
    return '/'.join(parts) if parts else 'images'

def store_image_locally(payload, folder, extension):
    safe_folder = safe_upload_folder(folder)
    filename = f"{uuid.uuid4().hex}.{extension}"
    relative_path = os.path.join('uploads', *safe_folder.split('/'), filename)
    absolute_path = os.path.join(app.static_folder, relative_path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, 'wb') as image_file:
        image_file.write(payload)
    public_path = '/'.join(relative_path.split(os.sep))
    return url_for('static', filename=public_path)

def store_video_locally(payload, folder, extension):
    safe_folder = safe_upload_folder(folder)
    filename = f"{uuid.uuid4().hex}.{extension}"
    relative_path = os.path.join('uploads', *safe_folder.split('/'), filename)
    absolute_path = os.path.join(app.static_folder, relative_path)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, 'wb') as video_file:
        video_file.write(payload)
    public_path = '/'.join(relative_path.split(os.sep))
    return url_for('static', filename=public_path)

def upload_image_to_storage(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_image_file(file_storage.filename):
        raise ValueError("Images must be JPG, PNG, GIF, or WebP.")

    try:
        file_storage.stream.seek(0)
    except (AttributeError, OSError):
        pass
    payload = file_storage.read()
    if not payload:
        raise ValueError("Selected image is empty.")
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("Images must be 50 MB or smaller.")

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit('.', 1)[1].lower()
    storage_path = f"{safe_upload_folder(folder)}/{uuid.uuid4().hex}.{extension}"
    content_type = IMAGE_CONTENT_TYPES.get(extension, file_storage.mimetype or "application/octet-stream")

    if supabase:
        try:
            ensure_storage_bucket(STORAGE_BUCKET)
            supabase.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                payload,
                file_options={"content-type": content_type, "upsert": "false"}
            )
            public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
            return public_url
        except Exception as exc:
            app.logger.warning("Supabase image upload failed; using local upload fallback: %s", exc)
            app.logger.debug("Supabase image upload fallback details", exc_info=True)
            if not LOCAL_IMAGE_UPLOAD_FALLBACK:
                raise RuntimeError("Image upload failed. Create the Supabase storage bucket and policies, then try again.") from exc

    if LOCAL_IMAGE_UPLOAD_FALLBACK:
        return store_image_locally(payload, folder, extension)

    raise RuntimeError("Image upload failed. Supabase Storage is not configured for image uploads.")

def upload_video_to_storage(file_storage, folder):
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a video to upload.")
    if not allowed_video_file(file_storage.filename):
        raise ValueError("Videos must be MP4, WebM, MOV, or M4V.")

    try:
        file_storage.stream.seek(0)
    except (AttributeError, OSError):
        pass
    payload = file_storage.read()
    if not payload:
        raise ValueError("Selected video is empty.")
    if len(payload) > MAX_VIDEO_BYTES:
        limit_mb = max(1, MAX_VIDEO_BYTES // (1024 * 1024))
        raise ValueError(f"Videos must be {limit_mb} MB or smaller.")

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit('.', 1)[1].lower()
    expected_content_type = VIDEO_CONTENT_TYPES.get(extension)
    mimetype = (file_storage.mimetype or '').lower()
    if mimetype and expected_content_type and mimetype not in {expected_content_type, 'application/octet-stream'}:
        if extension == 'm4v' and mimetype == 'video/mp4':
            pass
        else:
            raise ValueError("Selected file type does not match the video extension.")

    storage_path = f"{safe_upload_folder(folder)}/{uuid.uuid4().hex}.{extension}"
    content_type = expected_content_type or mimetype or "application/octet-stream"

    if supabase:
        try:
            ensure_media_bucket(SUPABASE_VIDEO_BUCKET, MAX_VIDEO_BYTES, list(VIDEO_CONTENT_TYPES.values()))
            supabase.storage.from_(SUPABASE_VIDEO_BUCKET).upload(
                storage_path,
                payload,
                file_options={"content-type": content_type, "upsert": "false"}
            )
            public_url = supabase.storage.from_(SUPABASE_VIDEO_BUCKET).get_public_url(storage_path)
            return public_url, storage_path
        except Exception as exc:
            app.logger.warning("Supabase video upload failed; using local upload fallback: %s", exc)
            app.logger.debug("Supabase video upload fallback details", exc_info=True)
            if not LOCAL_IMAGE_UPLOAD_FALLBACK:
                raise RuntimeError("Video upload failed. Create the Supabase storage bucket and policies, then try again.") from exc

    if LOCAL_IMAGE_UPLOAD_FALLBACK:
        return store_video_locally(payload, folder, extension), None

    raise RuntimeError("Video upload failed. Supabase Storage is not configured for video uploads.")

def get_user_safety_state(viewer_id, target_user_id):
    state = {'blocked': False, 'muted': False, 'blocked_by': False, 'interaction_blocked': False}
    if not viewer_id or not target_user_id or viewer_id == target_user_id:
        return state
    try:
        res = supabase.table('user_safety_actions').select('action_type').eq('actor_id', viewer_id).eq('target_user_id', target_user_id).in_('action_type', ['block', 'mute']).execute()
        for row in res.data or []:
            if row.get('action_type') == 'block':
                state['blocked'] = True
            if row.get('action_type') == 'mute':
                state['muted'] = True
    except Exception:
        pass
    try:
        incoming = supabase.table('user_safety_actions').select('id').eq('actor_id', target_user_id).eq('target_user_id', viewer_id).eq('action_type', 'block').limit(1).execute()
        state['blocked_by'] = bool(incoming.data)
    except Exception:
        state['blocked_by'] = False
    state['interaction_blocked'] = state['blocked'] or state['blocked_by']
    return state

def blocked_user_ids_for_viewer(viewer_id, candidate_ids=None, include_mutes=True):
    if not viewer_id:
        return set()
    candidate_set = {value for value in (candidate_ids or []) if value and value != viewer_id}
    hidden_ids = set()
    try:
        query = supabase.table('user_safety_actions').select('actor_id,target_user_id,action_type').or_(f"actor_id.eq.{viewer_id},target_user_id.eq.{viewer_id}")
        if include_mutes:
            query = query.in_('action_type', ['block', 'mute'])
        else:
            query = query.eq('action_type', 'block')
        res = query.execute()
        for row in res.data or []:
            actor_id = row.get('actor_id')
            target_id = row.get('target_user_id')
            action_type = row.get('action_type')
            if action_type == 'block':
                other_id = target_id if actor_id == viewer_id else actor_id
                if other_id and (not candidate_set or other_id in candidate_set):
                    hidden_ids.add(other_id)
            elif include_mutes and action_type == 'mute' and actor_id == viewer_id:
                if target_id and (not candidate_set or target_id in candidate_set):
                    hidden_ids.add(target_id)
    except Exception:
        return set()
    return hidden_ids

def filter_blocked_users(users, viewer_id, include_mutes=True):
    if not users:
        return []
    hidden_ids = blocked_user_ids_for_viewer(viewer_id, [user.get('id') for user in users], include_mutes=include_mutes)
    return [user for user in users if user.get('id') not in hidden_ids]

def interaction_blocked(viewer_id, target_user_id):
    return get_user_safety_state(viewer_id, target_user_id).get('interaction_blocked', False)

def visible_post_filter(posts, viewer_id):
    if not posts:
        return []
    author_ids = {post.get('user_id') for post in posts if post.get('user_id') and post.get('user_id') != viewer_id}
    hidden_ids = blocked_user_ids_for_viewer(viewer_id, author_ids, include_mutes=True)
    return [post for post in posts if post.get('user_id') not in hidden_ids]

def slugify(value):
    value = (value or '').strip().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value[:48] or 'community'

def community_tables_message():
    return "Community tables are not ready yet. Apply database/community_schema.sql in Supabase, then try again."

def enrich_posts(posts, viewer_id):
    if not posts: return []
    apply_forced_user_levels(posts)
    post_ids = [p['id'] for p in posts]
    author_ids = {p.get('user_id') or (p.get('user') or {}).get('id') for p in posts}
    author_ids = {author_id for author_id in author_ids if author_id and author_id != viewer_id}

    likes_res = supabase.table('likes').select('post_id').eq('user_id', viewer_id).in_('post_id', post_ids).execute()
    viewer_liked_ids = {l['post_id'] for l in likes_res.data} if likes_res.data else set()

    reposts_res = supabase.table('reposts').select('post_id').eq('user_id', viewer_id).in_('post_id', post_ids).execute()
    viewer_reposted_ids = {r['post_id'] for r in reposts_res.data} if reposts_res.data else set()

    followed_author_ids = set()
    if author_ids:
        try:
            follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).in_('following_id', list(author_ids)).execute()
            followed_author_ids = {row['following_id'] for row in follows_res.data or []}
        except Exception:
            followed_author_ids = set()

    for p in posts:
        author_id = p.get('user_id') or (p.get('user') or {}).get('id')
        p['like_count'] = p.get('likes', [{}])[0].get('count', 0) if p.get('likes') else 0
        p['reply_count'] = p.get('comments', [{}])[0].get('count', 0) if p.get('comments') else 0
        p['repost_count'] = p.get('reposts', [{}])[0].get('count', 0) if p.get('reposts') else 0
        p['viewer_liked'] = p['id'] in viewer_liked_ids
        p['viewer_reposted'] = p['id'] in viewer_reposted_ids
        p['author_followed'] = author_id in followed_author_ids
    return posts

def mark_following_state(users, viewer_id):
    if not users:
        return []
    apply_forced_user_levels(users)
    user_ids = [user['id'] for user in users if user.get('id') and user.get('id') != viewer_id]
    followed_ids = set()
    if user_ids:
        follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).in_('following_id', user_ids).execute()
        followed_ids = {row['following_id'] for row in follows_res.data} if follows_res and follows_res.data else set()
    for user in users:
        user['is_following'] = user.get('id') in followed_ids
    return users

def get_social_list(profile_user, list_type, viewer_id):
    profile_id = profile_user['id']
    title = {
        'followers': 'Followers',
        'following': 'Following',
        'friends': 'Friends'
    }.get(list_type, 'People')

    if list_type == 'followers':
        rows = supabase.table('follows').select('follower_id').eq('following_id', profile_id).execute()
        user_ids = [row['follower_id'] for row in rows.data or []]
    elif list_type == 'following':
        rows = supabase.table('follows').select('following_id').eq('follower_id', profile_id).execute()
        user_ids = [row['following_id'] for row in rows.data or []]
    elif list_type == 'friends':
        streaks_by_user, user_ids = get_streak_friend_ids(profile_id)
    else:
        streaks_by_user = {}
        user_ids = []

    user_ids = [user_id for user_id in dict.fromkeys(user_ids) if user_id]
    if not user_ids:
        return title, []
    users_res = supabase.table('users').select('*').in_('id', user_ids).execute()
    users = users_res.data if users_res and users_res.data else []
    if list_type == 'friends':
        for user in users:
            user['streak_count'] = streaks_by_user.get(user.get('id'), 0)
    return title, mark_following_state(filter_blocked_users(users, viewer_id, include_mutes=False), viewer_id)

def get_following_feed_posts(viewer_id, limit=POSTS_PER_PAGE, page=1):
    follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).execute()
    following_ids = [f['following_id'] for f in follows_res.data] if follows_res and follows_res.data else []
    if not following_ids:
        return []
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('user_id', following_ids).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    posts = posts_res.data if posts_res and posts_res.data else []
    return rank_timeline_posts(enrich_posts(visible_post_filter(posts, viewer_id), viewer_id), relationship_user_ids=following_ids)[:limit]

DUPLICATE_SUBMISSION_WINDOW = timedelta(seconds=12)

def recent_duplicate_submission(table_name, filters, text_field, text_value):
    text_value = (text_value or '').strip()
    if not supabase or not text_value:
        return False
    cutoff = (datetime.now(timezone.utc) - DUPLICATE_SUBMISSION_WINDOW).isoformat()
    query = supabase.table(table_name).select('id').eq(text_field, text_value).gte('created_at', cutoff)
    for key, value in filters.items():
        query = query.eq(key, value)
    res = query.limit(1).execute()
    return bool(res and res.data)

def dedupe_timeline_posts(posts):
    deduped = []
    seen_ids = set()
    for post in posts:
        post_id = post.get('id')
        if not post_id:
            deduped.append(post)
            continue
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        deduped.append(post)
    return deduped

def create_notification(user_id, actor_id, notif_type, post_id=None, reel_id=None, message_id=None):
    if not user_id or not actor_id or user_id == actor_id:
        return
    if interaction_blocked(actor_id, user_id):
        return
    payload = {
        'user_id': user_id,
        'actor_id': actor_id,
        'type': notif_type,
    }
    if post_id:
        payload['post_id'] = post_id
    if reel_id:
        payload['reel_id'] = reel_id
    if message_id:
        payload['message_id'] = message_id
    try:
        supabase.table('notifications').insert(payload).execute()
    except Exception:
        if not reel_id:
            raise
        payload.pop('reel_id', None)
        supabase.table('notifications').insert(payload).execute()

def get_feed_posts(viewer_id, limit=POSTS_PER_PAGE, page=1):
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(POST_SELECT_QUERY).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    direct_posts = posts_res.data if posts_res and posts_res.data else []

    reposts_res = supabase.table('reposts').select('user_id, post_id, created_at').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    repost_rows = reposts_res.data if reposts_res and reposts_res.data else []
    repost_post_ids = [row['post_id'] for row in repost_rows if row.get('post_id')]
    reposter_ids = list({row['user_id'] for row in repost_rows if row.get('user_id')})

    repost_posts_by_id = {}
    if repost_post_ids:
        repost_posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('id', repost_post_ids).is_('deleted_at', 'null').execute()
        repost_posts = repost_posts_res.data if repost_posts_res and repost_posts_res.data else []
        repost_posts_by_id = {post['id']: post for post in repost_posts}

    reposters_by_id = {}
    if reposter_ids:
        reposters_res = supabase.table('users').select('*').in_('id', reposter_ids).execute()
        reposters = reposters_res.data if reposters_res and reposters_res.data else []
        reposters_by_id = {user['id']: user for user in reposters}

    timeline = []
    for post in direct_posts:
        post['timeline_created_at'] = post.get('created_at')
        post['is_repost'] = False
        timeline.append(post)

    for row in repost_rows:
        original = repost_posts_by_id.get(row.get('post_id'))
        if not original:
            continue
        reposted_post = dict(original)
        reposted_post['timeline_created_at'] = row.get('created_at') or original.get('created_at')
        reposted_post['is_repost'] = True
        reposted_post['reposted_by'] = reposters_by_id.get(row.get('user_id'), {})
        timeline.append(reposted_post)

    timeline.sort(key=lambda post: post.get('timeline_created_at') or post.get('created_at') or '', reverse=True)
    return enrich_posts(visible_post_filter(dedupe_timeline_posts(timeline)[:limit], viewer_id), viewer_id)

def get_profile_posts(profile_user, viewer_id, limit=POSTS_PER_PAGE, page=1):
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(POST_SELECT_QUERY).eq('user_id', profile_user['id']).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    direct_posts = posts_res.data if posts_res and posts_res.data else []

    reposts_res = supabase.table('reposts').select('post_id, created_at').eq('user_id', profile_user['id']).order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    repost_rows = reposts_res.data if reposts_res and reposts_res.data else []
    repost_post_ids = [row['post_id'] for row in repost_rows if row.get('post_id')]

    repost_posts_by_id = {}
    if repost_post_ids:
        repost_posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('id', repost_post_ids).is_('deleted_at', 'null').execute()
        repost_posts = repost_posts_res.data if repost_posts_res and repost_posts_res.data else []
        repost_posts_by_id = {post['id']: post for post in repost_posts}

    timeline = []
    for post in direct_posts:
        post['timeline_created_at'] = post.get('created_at')
        post['is_repost'] = False
        timeline.append(post)

    for row in repost_rows:
        original = repost_posts_by_id.get(row.get('post_id'))
        if not original:
            continue
        reposted_post = dict(original)
        reposted_post['timeline_created_at'] = row.get('created_at') or original.get('created_at')
        reposted_post['is_repost'] = True
        reposted_post['reposted_by'] = profile_user
        timeline.append(reposted_post)

    timeline.sort(key=lambda post: post.get('timeline_created_at') or post.get('created_at') or '', reverse=True)
    return enrich_posts(visible_post_filter(dedupe_timeline_posts(timeline)[:limit], viewer_id), viewer_id)

def timeline_timestamp(value):
    if not value:
        return 0
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        normalized = str(value).replace('Z', '+00:00')
        return datetime.fromisoformat(normalized).timestamp()
    except (TypeError, ValueError):
        return 0

def relative_time(value, now=None):
    if not value:
        return ""
    if isinstance(value, datetime):
        target = value
    else:
        try:
            target = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return ""

    current = now or (datetime.now(target.tzinfo) if target.tzinfo else datetime.now())
    if target.tzinfo and current.tzinfo is None:
        current = current.replace(tzinfo=target.tzinfo)

    seconds = int((current - target).total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 30:
        return f"{days}d"
    months = days // 30
    if months < 12:
        return f"{months}mo"
    years = days // 365
    return f"{max(1, years)}y"

def nested_count(value):
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return parse_int(first.get('count')) or 0
    return parse_int(value) or 0

def post_engagement_score(post):
    return (
        nested_count(post.get('likes')) * 3
        + nested_count(post.get('comments')) * 4
        + nested_count(post.get('reposts')) * 5
        + (parse_int(post.get('reply_count')) or 0) * 4
        + (parse_int(post.get('like_count')) or 0) * 3
        + (parse_int(post.get('repost_count')) or 0) * 5
    )

def rank_timeline_posts(posts, relationship_user_ids=None, joined_community_ids=None):
    relationship_user_ids = set(relationship_user_ids or [])
    joined_community_ids = set(joined_community_ids or [])

    def score(post):
        author = post.get('user') or {}
        author_id = post.get('user_id') or author.get('id')
        community = post.get('community') or {}
        community_id = post.get('community_id') or community.get('id')
        recency = timeline_timestamp(post.get('timeline_created_at') or post.get('created_at'))
        relationship_boost = 900 if author_id in relationship_user_ids else 0
        community_boost = 700 if community_id in joined_community_ids else 0
        author_level = parse_int(author.get('level')) or 1
        return recency + (post_engagement_score(post) * 240) + relationship_boost + community_boost + (author_level * 35)

    return sorted(posts, key=score, reverse=True)

def unique_ids(rows, key):
    values = []
    for row in rows or []:
        value = row.get(key)
        if value and value not in values:
            values.append(value)
    return values

def get_community_highlights():
    try:
        res = supabase.table('users').select('*').order('level', desc=True).limit(3).execute()
        return merge_forced_level_users(res.data if res and res.data else [], limit=3)
    except Exception:
        return []

def get_communities(limit=6):
    try:
        res = supabase.table('communities').select('*, owner:users!communities_owner_id_fkey(*)').order('created_at', desc=True).limit(limit).execute()
        communities = res.data if res and res.data else []
        apply_forced_user_levels(communities)
        for item in communities:
            item['member_count'] = item.get('member_count', 0)
        return communities
    except Exception:
        return []

def get_community_by_slug(slug):
    try:
        res = supabase.table('communities').select('*, owner:users!communities_owner_id_fkey(*)').eq('slug', slug).execute()
        return apply_forced_user_levels(res.data[0]) if res and res.data else None
    except Exception:
        return None

def get_short_videos(limit=8, community_id=None):
    try:
        query = supabase.table('community_videos').select('*, author:users!community_videos_user_id_fkey(*), community:communities!community_videos_community_id_fkey(*)')
        if community_id:
            query = query.eq('community_id', community_id)
        res = query.order('created_at', desc=True).limit(limit).execute()
        return apply_forced_user_levels(res.data if res and res.data else [])
    except Exception:
        return []

def get_trending_posts(viewer_id, limit=5):
    try:
        posts_res = supabase.table('posts').select(POST_SELECT_QUERY).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit).execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        return enrich_posts(visible_post_filter(posts, viewer_id), viewer_id)
    except Exception:
        return []

def get_recent_posts(viewer_id, limit=3):
    try:
        res = supabase.table('posts').select(POST_SELECT_QUERY).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit).execute()
        posts = res.data if res and res.data else []
        return enrich_posts(visible_post_filter(posts, viewer_id), viewer_id)
    except Exception:
        return []

def get_search_discovery_context(viewer, people_limit=4, posts_limit=3):
    return {
        'suggested_users': get_popular_users(viewer['id'], people_limit),
        'recent_posts': get_recent_posts(viewer['id'], posts_limit),
    }

def get_popular_users(viewer_id, limit=5):
    try:
        res = supabase.table('users').select('*').order('level', desc=True).limit(limit).execute()
        users = res.data if res and res.data else []
        users = merge_forced_level_users(users, limit=limit)
        return mark_following_state(filter_blocked_users(users, viewer_id, include_mutes=False), viewer_id)
    except Exception:
        return []

def get_community_posts(community_id, viewer_id, limit=20):
    try:
        link_res = supabase.table('community_posts').select('post_id').eq('community_id', community_id).order('created_at', desc=True).limit(limit).execute()
        post_ids = [row['post_id'] for row in link_res.data] if link_res and link_res.data else []
        if not post_ids:
            return []
        posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('id', post_ids).is_('deleted_at', 'null').execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        posts_by_id = {post['id']: post for post in posts}
        ordered_posts = [posts_by_id[post_id] for post_id in post_ids if post_id in posts_by_id]
        return enrich_posts(visible_post_filter(ordered_posts, viewer_id), viewer_id)
    except Exception:
        return []

def get_community_members(community_id, limit=8, viewer_id=None):
    try:
        res = supabase.table('community_members').select('*, user:users!community_members_user_id_fkey(*)').eq('community_id', community_id).order('created_at', desc=True).limit(limit).execute()
        members = apply_forced_user_levels(res.data if res and res.data else [])
        if viewer_id:
            member_user_ids = [
                row.get('user_id') or (row.get('user') or {}).get('id')
                for row in members
            ]
            hidden_ids = blocked_user_ids_for_viewer(viewer_id, member_user_ids, include_mutes=False)
            members = [
                row for row in members
                if (row.get('user_id') or (row.get('user') or {}).get('id')) not in hidden_ids
            ]
        return members
    except Exception:
        return []

def get_viewer_membership(community_id, viewer_id):
    try:
        res = supabase.table('community_members').select('*').eq('community_id', community_id).eq('user_id', viewer_id).execute()
        return res.data[0] if res and res.data else None
    except Exception:
        return None

def get_followers_feed_posts(viewer_id, limit=POSTS_PER_PAGE):
    try:
        follows_res = supabase.table('follows').select('follower_id').eq('following_id', viewer_id).execute()
        follower_ids = unique_ids(follows_res.data if follows_res else [], 'follower_id')
        if not follower_ids:
            return []
        posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('user_id', follower_ids).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit * 2).execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        enriched = enrich_posts(visible_post_filter(posts, viewer_id), viewer_id)
        return rank_timeline_posts(enriched, relationship_user_ids=follower_ids)[:limit]
    except Exception:
        return []

def get_joined_community_ids(viewer_id):
    try:
        res = supabase.table('community_members').select('community_id').eq('user_id', viewer_id).execute()
        return unique_ids(res.data if res else [], 'community_id')
    except Exception:
        return []

def reels_table_not_ready(error):
    text = str(error).lower()
    return 'reels' in text and any(marker in text for marker in ['does not exist', 'schema cache', 'relation', 'not found'])

def get_demo_reels(count=5):
    demo_author = {
        'id': 0,
        'username': 'lvl',
        'display_name': 'LvL',
        'profile_photo_url': url_for('static', filename='assets/icon-192.png'),
        'level': 1,
    }
    demo_video_url = 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'
    captions = [
        'Demo reel: a quick vertical-video preview for LvL.',
        'Demo reel: upload your own short videos when storage is ready.',
        'Demo reel: scroll, tap, like, and keep moving.',
        'Demo reel: your right rail keeps moving without leaving Home.',
        'Demo reel: enough local samples to test the continuous scroll.',
    ]
    samples = []
    for index in range(max(count, 0)):
        caption = captions[index] if index < len(captions) else f'Demo reel: local preview sample {index + 1} keeps the rail moving.'
        samples.append((f'demo-{index + 1}', demo_video_url, caption))
    return [{
        'id': reel_id,
        'user_id': 0,
        'video_url': video_url,
        'caption': caption,
        'visibility': 'public',
        'allow_comments': False,
        'allow_downloads': False,
        'autoplay_next': True,
        'view_count': 0,
        'created_at': '',
        'user': demo_author,
        'author': demo_author,
        'community': None,
        'like_count': 0,
        'comment_count': 0,
        'viewer_liked': False,
        'is_owner': False,
        'is_demo': True,
    } for reel_id, video_url, caption in samples]

def get_home_reel_preview(viewer_id, limit=HOME_REEL_PREVIEW_LIMIT):
    try:
        home_reels_data, _ = get_reels(viewer_id, limit=limit, page=1)
        if home_reels_data:
            return home_reels_data
    except Exception:
        pass
    return get_demo_reels(limit)

def get_demo_media_previews(count=HOME_MEDIA_PREVIEW_LIMIT):
    demo_author = {
        'id': 0,
        'username': 'lvl',
        'display_name': 'LvL',
        'profile_photo_url': url_for('static', filename='assets/icon-192.png'),
        'level': 1,
    }
    captions = [
        'Demo media: photo posts and image updates live here while Reels stay centered.',
        'Demo media: a normal post preview sized for the right rail.',
        'Demo media: browse image posts without leaving the Reels page.',
        'Demo media: community moments in a quieter non-video format.',
    ]
    return [{
        'id': f'demo-media-{index + 1}',
        'image_url': url_for('static', filename='assets/icon-512.png'),
        'content': captions[index] if index < len(captions) else f'Demo media: local post preview sample {index + 1}.',
        'created_at': '',
        'user': demo_author,
        'like_count': 0,
        'reply_count': 0,
        'is_demo': True,
    } for index in range(max(count, 0))]

def get_home_media_preview(viewer_id, limit=HOME_MEDIA_PREVIEW_LIMIT):
    try:
        res = supabase.table('posts').select(POST_SELECT_QUERY).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit * 3).execute()
        rows = res.data if res and res.data else []
        media_posts = [post for post in visible_post_filter(rows, viewer_id) if post.get('image_url')]
        if media_posts:
            return enrich_posts(media_posts[:limit], viewer_id)
    except Exception:
        pass
    return get_demo_media_previews(limit)

def visible_reel_filter(reels, viewer_id):
    if not reels:
        return []

    author_ids = {row.get('user_id') for row in reels if row.get('user_id') and row.get('user_id') != viewer_id}
    hidden_author_ids = blocked_user_ids_for_viewer(viewer_id, author_ids, include_mutes=True)
    community_ids = {row.get('community_id') for row in reels if row.get('community_id')}
    followed_ids = set()
    member_roles = {}

    if author_ids:
        try:
            follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).in_('following_id', list(author_ids)).execute()
            followed_ids = {row['following_id'] for row in follows_res.data or []}
        except Exception:
            followed_ids = set()

    if community_ids:
        try:
            member_res = supabase.table('community_members').select('community_id,role').eq('user_id', viewer_id).in_('community_id', list(community_ids)).execute()
            member_roles = {row['community_id']: row.get('role', 'member') for row in member_res.data or []}
        except Exception:
            member_roles = {}

    visible = []
    for reel in reels:
        owner_id = reel.get('user_id')
        if owner_id in hidden_author_ids:
            continue
        visibility = reel.get('visibility') or 'public'
        community = reel.get('community') or {}
        community_id = reel.get('community_id') or community.get('id')

        if owner_id == viewer_id or visibility == 'public':
            visible.append(reel)
        elif visibility == 'private':
            continue
        elif visibility == 'followers' and owner_id in followed_ids:
            visible.append(reel)
        elif visibility == 'community' and community_id:
            is_community_owner = community.get('owner_id') == viewer_id
            is_member = community_id in member_roles
            if is_community_owner or is_member:
                visible.append(reel)
    return visible

def enrich_reels(reels, viewer_id):
    if not reels:
        return []
    apply_forced_user_levels(reels)

    reel_ids = [row['id'] for row in reels if isinstance(row.get('id'), int)]
    author_ids = {row.get('user_id') for row in reels if row.get('user_id') and row.get('user_id') != viewer_id}
    viewer_liked_ids = set()
    like_counts = {}
    comment_counts = {}
    followed_author_ids = set()

    if reel_ids:
        try:
            likes_res = supabase.table('reel_likes').select('reel_id').in_('reel_id', reel_ids).execute()
            for row in likes_res.data or []:
                reel_id = row.get('reel_id')
                like_counts[reel_id] = like_counts.get(reel_id, 0) + 1
        except Exception:
            like_counts = {}

        try:
            viewer_likes_res = supabase.table('reel_likes').select('reel_id').eq('user_id', viewer_id).in_('reel_id', reel_ids).execute()
            viewer_liked_ids = {row['reel_id'] for row in viewer_likes_res.data or []}
        except Exception:
            viewer_liked_ids = set()

        try:
            comments_res = supabase.table('reel_comments').select('reel_id').in_('reel_id', reel_ids).is_('deleted_at', 'null').execute()
            for row in comments_res.data or []:
                reel_id = row.get('reel_id')
                comment_counts[reel_id] = comment_counts.get(reel_id, 0) + 1
        except Exception:
            comment_counts = {}

    if author_ids:
        try:
            follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).in_('following_id', list(author_ids)).execute()
            followed_author_ids = {row['following_id'] for row in follows_res.data or []}
        except Exception:
            followed_author_ids = set()

    for reel in reels:
        author = reel.get('user') or reel.get('author') or {}
        reel['author'] = author
        reel['user'] = author
        reel['like_count'] = like_counts.get(reel.get('id'), nested_count(reel.get('reel_likes')))
        reel['comment_count'] = comment_counts.get(reel.get('id'), nested_count(reel.get('reel_comments')))
        reel['viewer_liked'] = reel.get('id') in viewer_liked_ids
        reel['is_owner'] = reel.get('user_id') == viewer_id
        reel['author_followed'] = reel.get('user_id') in followed_author_ids
        reel['is_demo'] = False
    return reels

def get_reels(viewer_id, limit=8, page=1, tab='for_you'):
    offset = (page - 1) * limit
    select_query = '*, user:users!reels_user_id_fkey(*), community:communities!reels_community_id_fkey(*)'
    query = supabase.table('reels').select(select_query).eq('status', 'active').is_('deleted_at', 'null')
    if tab == 'following':
        try:
            follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).execute()
            following_ids = [row['following_id'] for row in follows_res.data or []]
            following_ids.append(viewer_id)
            if following_ids:
                query = query.in_('user_id', following_ids)
        except Exception:
            pass
        query = query.order('created_at', desc=True)
    elif tab == 'discovery':
        query = query.order('view_count', desc=True).order('created_at', desc=True)
    else:
        query = query.order('created_at', desc=True)
    res = query.range(offset, offset + limit).execute()
    rows = res.data if res and res.data else []
    visible = visible_reel_filter(rows, viewer_id)
    return enrich_reels(visible[:limit], viewer_id), len(visible) > limit

def get_reel_by_id(reel_id, viewer_id=None):
    select_query = '*, user:users!reels_user_id_fkey(*), community:communities!reels_community_id_fkey(*)'
    res = supabase.table('reels').select(select_query).eq('id', reel_id).is_('deleted_at', 'null').execute()
    if not res or not res.data:
        return None
    reel = res.data[0]
    viewer_id = viewer_id or reel.get('user_id')
    visible = visible_reel_filter([reel], viewer_id)
    if not visible:
        return None
    return enrich_reels(visible, viewer_id)[0]

def get_reel_upload_communities(viewer_id):
    communities = {}
    try:
        owned_res = supabase.table('communities').select('id,name,slug,owner_id,accent_color').eq('owner_id', viewer_id).execute()
        for item in owned_res.data or []:
            communities[item['id']] = item
    except Exception:
        pass
    try:
        member_res = supabase.table('community_members').select('community:communities!community_members_community_id_fkey(id,name,slug,owner_id,accent_color)').eq('user_id', viewer_id).execute()
        for row in member_res.data or []:
            community = row.get('community')
            if community and community.get('id'):
                communities[community['id']] = community
    except Exception:
        pass
    return sorted(communities.values(), key=lambda item: (item.get('name') or '').lower())

def get_community_timeline_posts(viewer_id, limit=POSTS_PER_PAGE):
    try:
        joined_ids = get_joined_community_ids(viewer_id)
        link_res = supabase.table('community_posts').select('community_id,post_id,created_at').order('created_at', desc=True).limit(limit * 4).execute()
        links = link_res.data if link_res and link_res.data else []
        post_ids = unique_ids(links, 'post_id')
        community_ids = unique_ids(links, 'community_id')
        if not post_ids:
            return []

        posts_res = supabase.table('posts').select(POST_SELECT_QUERY).in_('id', post_ids).is_('deleted_at', 'null').execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        posts_by_id = {post['id']: post for post in posts}

        communities_by_id = {}
        if community_ids:
            communities_res = supabase.table('communities').select('id,name,slug,accent_color').in_('id', community_ids).execute()
            communities = communities_res.data if communities_res and communities_res.data else []
            communities_by_id = {item['id']: item for item in communities}

        timeline = []
        seen = set()
        for link in links:
            post_id = link.get('post_id')
            if not post_id or post_id in seen or post_id not in posts_by_id:
                continue
            post = dict(posts_by_id[post_id])
            community_id = link.get('community_id')
            post['timeline_created_at'] = link.get('created_at') or post.get('created_at')
            post['community_id'] = community_id
            post['community'] = communities_by_id.get(community_id, {})
            timeline.append(post)
            seen.add(post_id)

        enriched = enrich_posts(visible_post_filter(timeline, viewer_id), viewer_id)
        return rank_timeline_posts(enriched, joined_community_ids=joined_ids)[:limit]
    except Exception:
        return []

def get_community_timeline_context(viewer, requested_tab=None, limit=POSTS_PER_PAGE):
    active_tab = requested_tab if requested_tab in {tab['key'] for tab in COMMUNITY_TIMELINE_TABS} else COMMUNITY_DEFAULT_TAB
    feeds = {
        'followers': get_followers_feed_posts(viewer['id'], limit),
        'following': get_following_feed_posts(viewer['id'], limit=limit),
        'community': get_community_timeline_posts(viewer['id'], limit)
    }
    return {
        'tabs': COMMUNITY_TIMELINE_TABS,
        'active_tab': active_tab,
        'feeds': feeds,
        'counts': {key: len(value) for key, value in feeds.items()}
    }

def get_explore_context(viewer):
    context = {
        'metrics': {'users': 0, 'profiles': 0, 'posts': 0, 'comments': 0, 'likes': 0, 'follows': 0, 'messages': 0, 'notifications': 0, 'communities': 0},
        'recent_members': [],
        'popular_users': [],
        'trending_posts': [],
        'communities': [],
        'activity_items': []
    }
    try:
        users_count = supabase.table('users').select('id', count='exact').execute()
        posts_count = supabase.table('posts').select('id', count='exact').is_('deleted_at', 'null').execute()
        follows_count = supabase.table('follows').select('follower_id', count='exact').execute()
        likes_count = supabase.table('likes').select('user_id', count='exact').execute()
        comments_count = supabase.table('comments').select('id', count='exact').execute()
        context['metrics'].update({
            'users': users_count.count if users_count else 0,
            'profiles': users_count.count if users_count else 0,
            'posts': posts_count.count if posts_count else 0,
            'follows': follows_count.count if follows_count else 0,
            'likes': likes_count.count if likes_count else 0,
            'comments': comments_count.count if comments_count else 0
        })
    except Exception:
        pass

    try:
        recent_res = supabase.table('users').select('*').order('created_at', desc=True).limit(8).execute()
        context['recent_members'] = apply_forced_user_levels(recent_res.data if recent_res and recent_res.data else [])
    except Exception:
        pass

    context['popular_users'] = get_popular_users(viewer['id'], 5)
    context['trending_posts'] = get_trending_posts(viewer['id'], 5)
    context['communities'] = get_communities(6)
    context['metrics']['communities'] = len(context['communities'])

    for post in context['trending_posts'][:3]:
        context['activity_items'].append({
            'label': 'Trending post',
            'text': post.get('content', '')[:90],
            'url': url_for('post', id=post['id'])
        })
    for user in context['recent_members'][:3]:
        context['activity_items'].append({
            'label': 'New member',
            'text': f"@{user.get('username', '')} joined LvL",
            'url': url_for('profile', username=user.get('username', ''))
        })
    return context

def activity_item(kind, title, description, created_at=None, url=None, emoji='•'):
    return {
        'kind': kind,
        'title': title,
        'description': description,
        'created_at': created_at or '',
        'url': url,
        'emoji': emoji
    }

def get_user_activity(viewer, limit=36):
    items = []
    viewer_id = viewer['id']

    try:
        posts_res = supabase.table('posts').select('id,content,created_at').eq('user_id', viewer_id).is_('deleted_at', 'null').order('created_at', desc=True).limit(12).execute()
        for post in posts_res.data or []:
            text = post.get('content') or 'Picture post'
            items.append(activity_item('post', 'Post', text[:120], post.get('created_at'), url_for('post', id=post['id']), '📝'))
    except Exception:
        pass

    try:
        comments_res = supabase.table('comments').select('id,post_id,comment,created_at').eq('user_id', viewer_id).order('created_at', desc=True).limit(12).execute()
        for comment in comments_res.data or []:
            post_id = comment.get('post_id')
            items.append(activity_item('comment', 'Comment', (comment.get('comment') or '')[:120], comment.get('created_at'), url_for('post', id=post_id) if post_id else None, '💬'))
    except Exception:
        pass

    try:
        likes_res = supabase.table('likes').select('post_id,created_at').eq('user_id', viewer_id).order('created_at', desc=True).limit(12).execute()
        for like in likes_res.data or []:
            post_id = like.get('post_id')
            items.append(activity_item('like', 'Like', 'You liked a post.', like.get('created_at'), url_for('post', id=post_id) if post_id else None, '👍'))
    except Exception:
        pass

    try:
        reposts_res = supabase.table('reposts').select('post_id,created_at').eq('user_id', viewer_id).order('created_at', desc=True).limit(12).execute()
        for repost in reposts_res.data or []:
            post_id = repost.get('post_id')
            items.append(activity_item('repost', 'Repost', 'You reposted something to your network.', repost.get('created_at'), url_for('post', id=post_id) if post_id else None, '🔁'))
    except Exception:
        pass

    try:
        reels_res = supabase.table('reels').select('id,caption,created_at').eq('user_id', viewer_id).is_('deleted_at', 'null').order('created_at', desc=True).limit(12).execute()
        for reel in reels_res.data or []:
            text = reel.get('caption') or 'You uploaded a reel.'
            items.append(activity_item('reel', 'Reel', text[:120], reel.get('created_at'), f"{url_for('reels')}#reel-{reel['id']}", '▶'))
    except Exception:
        pass

    items.sort(key=lambda item: item.get('created_at') or '', reverse=True)
    return items[:limit]

def setup_health_check(label, ready, detail):
    return {
        'label': label,
        'status': 'ready' if ready else 'needs_attention',
        'detail': detail,
    }

def get_setup_health():
    checks = []
    checks.append(setup_health_check(
        "Supabase connection",
        bool(supabase),
        "Client configured." if supabase else "Add SUPABASE_URL and SUPABASE_SECRET to .env."
    ))

    for table, label in [
        ('users', 'Users table'),
        ('posts', 'Posts table'),
        ('reels', 'Reels table'),
        ('communities', 'Communities table'),
        ('user_safety_actions', 'Safety actions table'),
    ]:
        if not supabase:
            checks.append(setup_health_check(label, False, "Supabase is not configured."))
            continue
        try:
            supabase.table(table).select('id').limit(1).execute()
            checks.append(setup_health_check(label, True, f"The {table} table is queryable."))
        except Exception as exc:
            if table == 'reels' and reels_table_not_ready(exc):
                detail = "Run database/migrations/002_reels.sql in Supabase."
            else:
                detail = handle_db_error(exc, f"The {table} table could not be checked.")
            checks.append(setup_health_check(label, False, detail))

    if supabase:
        try:
            supabase.table('users').select('supabase_auth_user_id,oauth_provider,oauth_subject,oauth_email').limit(1).execute()
            checks.append(setup_health_check("OAuth identity columns", True, "Social login identity columns are available."))
        except Exception:
            checks.append(setup_health_check("OAuth identity columns", False, "Run database/migrations/005_oauth_identity.sql in Supabase."))
    else:
        checks.append(setup_health_check("OAuth identity columns", False, "Supabase is not configured."))

    if supabase:
        try:
            supabase.storage.get_bucket(STORAGE_BUCKET)
            checks.append(setup_health_check("Media storage bucket", True, f"{STORAGE_BUCKET} is available."))
        except Exception:
            checks.append(setup_health_check("Media storage bucket", False, f"Create or allow the {STORAGE_BUCKET} Supabase storage bucket."))
    else:
        checks.append(setup_health_check("Media storage bucket", False, "Supabase is not configured."))

    for relative_path, label in [
        ('static/manifest.json', 'PWA manifest'),
        ('static/service-worker.js', 'Service worker'),
        ('static/assets/icon-192.png', 'PWA 192 icon'),
        ('static/assets/icon-512.png', 'PWA 512 icon'),
    ]:
        full_path = os.path.join(app.root_path, relative_path)
        checks.append(setup_health_check(
            label,
            os.path.exists(full_path),
            f"{relative_path} exists." if os.path.exists(full_path) else f"{relative_path} is missing."
        ))

    return checks

STACKABLE_NOTIFICATION_TYPES = {'like', 'repost', 'comment', 'high_five', 'reel_like', 'reel_comment'}

def actor_summary(names, count):
    clean_names = [name for name in names if name]
    if count <= 1:
        return clean_names[0] if clean_names else 'Someone'
    if len(clean_names) >= 2 and count == 2:
        return f"{clean_names[0]} and {clean_names[1]}"
    if len(clean_names) >= 2:
        return f"{clean_names[0]}, {clean_names[1]}, and {count - 2} others"
    if clean_names:
        return f"{clean_names[0]} and {count - 1} others"
    return f"{count} people"

def stack_notifications(notifications):
    stacked = []
    stack_map = {}
    for notification in notifications:
        notification['stack_count'] = 1
        notification['stack_actor_names'] = [notification.get('actor_name') or 'Someone']
        notification['actor_summary'] = actor_summary(notification['stack_actor_names'], 1)

        notif_type = notification.get('type')
        if notif_type not in STACKABLE_NOTIFICATION_TYPES:
            stacked.append(notification)
            continue

        key = (notif_type, notification.get('post_id') or notification.get('reel_id') or 'global')
        existing = stack_map.get(key)
        if not existing:
            stack_map[key] = notification
            stacked.append(notification)
            continue

        existing['stack_count'] += 1
        existing['is_read'] = existing.get('is_read') and notification.get('is_read')
        name = notification.get('actor_name') or 'Someone'
        if name not in existing['stack_actor_names']:
            existing['stack_actor_names'].append(name)
        existing['actor_summary'] = actor_summary(existing['stack_actor_names'], existing['stack_count'])

    return stacked

@app.route('/')
def index():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    feed_mode = request.args.get('feed', 'all')
    page = parse_positive_int(request.args.get('page'), default=1, maximum=500)
    highlights = get_community_highlights()

    try:
        if feed_mode == 'following':
            posts = get_following_feed_posts(viewer['id'], page=page)
        else:
            posts = get_feed_posts(viewer['id'], page=page)
    except Exception as e:
        posts = []
        flash(handle_db_error(e, "An error occurred while loading posts."), "error")

    return render_template('index.html',
                           viewer=viewer,
                           posts=posts,
                           mode=feed_mode,
                           highlights=highlights,
                           page=page,
                           has_next=len(posts) == POSTS_PER_PAGE,
                           home_reels=get_home_reel_preview(viewer['id']))

@app.route('/reels')
def reels():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    page = parse_positive_int(request.args.get('page'), default=1, maximum=500)
    tab = request.args.get('tab', 'for_you')
    if tab not in {'for_you', 'following'}:
        tab = 'for_you'
    table_ready = True
    try:
        reels_list, has_next = get_reels(viewer['id'], limit=8, page=page, tab=tab)
    except Exception as exc:
        reels_list = []
        has_next = False
        table_ready = False
        if reels_table_not_ready(exc):
            flash("Reels database table is not ready. Run database/migrations/002_reels.sql in Supabase.", "error")
        else:
            flash(handle_db_error(exc, "Could not load reels."), "error")

    if not reels_list and not table_ready:
        reels_list = get_demo_reels()
        has_next = False

    return render_template('reels.html',
                           viewer=viewer,
                           reels=reels_list,
                           page=page,
                           has_next=has_next,
                           table_ready=table_ready,
                           tab=tab,
                           highlights=get_community_highlights(),
                           home_media=get_home_media_preview(viewer['id']))

@app.route('/api/reels')
def api_reels():
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    page = parse_positive_int(request.args.get('page'), default=1, maximum=500)
    try:
        reels_list, has_next = get_reels(viewer['id'], limit=8, page=page)
        return jsonify({'success': True, 'reels': reels_list, 'page': page, 'has_next': has_next})
    except Exception as exc:
        return jsonify({'success': False, 'error': handle_db_error(exc, "Could not load reels.")}), 400

@app.route('/reels/upload', methods=['GET', 'POST'])
def reel_upload():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    communities = get_reel_upload_communities(viewer['id'])
    if request.method == 'POST':
        video_file = request.files.get('video')
        caption = request.form.get('caption', '').strip()
        visibility = request.form.get('visibility', 'public')
        community_id = parse_int(request.form.get('community_id'))
        allow_comments = request.form.get('allow_comments') == 'on'
        allow_downloads = request.form.get('allow_downloads') == 'on'
        autoplay_next = request.form.get('autoplay_next') == 'on'
        valid_visibilities = {'public', 'followers', 'community', 'private'}

        if visibility not in valid_visibilities:
            flash("Choose a valid visibility setting.", "error")
            return redirect(url_for('reel_upload'))
        if len(caption) > 220:
            flash("Caption cannot exceed 220 characters.", "error")
            return redirect(url_for('reel_upload'))
        if visibility == 'community':
            allowed_community_ids = {item['id'] for item in communities}
            if not community_id or community_id not in allowed_community_ids:
                flash("Choose one of your communities for community-only reels.", "error")
                return redirect(url_for('reel_upload'))
        else:
            community_id = None

        try:
            video_url, storage_path = upload_video_to_storage(video_file, f"reels/{viewer['id']}")
            payload = {
                'user_id': viewer['id'],
                'community_id': community_id,
                'video_url': video_url,
                'storage_path': storage_path,
                'cover_url': None,
                'caption': caption,
                'visibility': visibility,
                'allow_comments': allow_comments,
                'allow_downloads': allow_downloads,
                'autoplay_next': autoplay_next,
                'status': 'active',
            }
            res = supabase.table('reels').insert(payload).execute()
            if res.data:
                reel_id = res.data[0]['id']
                award_xp(viewer['id'], 'reel_created', 15, reel_id)
            flash("Reel uploaded.", "success")
            return redirect(url_for('reels'))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
        except Exception as exc:
            if reels_table_not_ready(exc):
                flash("Reels database table is not ready. Run database/migrations/002_reels.sql in Supabase.", "error")
            else:
                flash(handle_db_error(exc, "Could not upload that reel."), "error")

    return render_template('reel_upload.html',
                           viewer=viewer,
                           communities=communities,
                           max_video_bytes=MAX_VIDEO_BYTES,
                           highlights=[])

@app.route('/reels/<int:reel_id>/like', methods=['POST'])
def toggle_reel_like(reel_id):
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    try:
        reel = get_reel_by_id(reel_id, viewer['id'])
        if not reel or reel.get('is_demo'):
            return jsonify({'success': False, 'error': 'Reel not found.'}), 404
        if interaction_blocked(viewer['id'], reel.get('user_id')):
            return jsonify({'success': False, 'error': 'You cannot interact with this user.'}), 403
        existing = supabase.table('reel_likes').select('reel_id').eq('reel_id', reel_id).eq('user_id', viewer['id']).execute()
        if existing.data:
            supabase.table('reel_likes').delete().eq('reel_id', reel_id).eq('user_id', viewer['id']).execute()
            liked = False
        else:
            supabase.table('reel_likes').insert({'reel_id': reel_id, 'user_id': viewer['id']}).execute()
            liked = True
            create_notification(reel.get('user_id'), viewer['id'], 'reel_like', reel_id=reel_id)
        count_res = supabase.table('reel_likes').select('reel_id', count='exact').eq('reel_id', reel_id).execute()
        count = count_res.count if count_res else 0
        return jsonify({'success': True, 'liked': liked, 'count': count, 'xp_toasts': []})
    except Exception as exc:
        return jsonify({'success': False, 'error': handle_db_error(exc)}), 400

@app.route('/reels/<int:reel_id>/comment', methods=['POST'])
def add_reel_comment(reel_id):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    wants_json = request.form.get('ajax') == '1'
    comment = request.form.get('comment', '').strip()
    try:
        reel = get_reel_by_id(reel_id, viewer['id'])
        if not reel or reel.get('is_demo'):
            if wants_json:
                return jsonify({'success': False, 'error': 'Reel not found.'}), 404
            flash("Reel not found.", "error")
        elif interaction_blocked(viewer['id'], reel.get('user_id')):
            if wants_json:
                return jsonify({'success': False, 'error': 'You cannot interact with this user.'}), 403
            flash("You cannot interact with this user.", "error")
        elif not reel.get('allow_comments', True):
            if wants_json:
                return jsonify({'success': False, 'error': 'Comments are closed for this reel.'}), 400
            flash("Comments are closed for this reel.", "error")
        elif not comment:
            if wants_json:
                return jsonify({'success': False, 'error': 'Write a comment first.'}), 400
            flash("Write a comment first.", "error")
        elif len(comment) > 280:
            if wants_json:
                return jsonify({'success': False, 'error': 'Comment cannot exceed 280 characters.'}), 400
            flash("Comment cannot exceed 280 characters.", "error")
        elif recent_duplicate_submission('reel_comments', {'reel_id': reel_id, 'user_id': viewer['id']}, 'comment', comment):
            if wants_json:
                count_res = supabase.table('reel_comments').select('reel_id', count='exact').eq('reel_id', reel_id).is_('deleted_at', 'null').execute()
                count = count_res.count if count_res else 0
                return jsonify({'success': False, 'error': 'Already commented.', 'count': count}), 409
            flash("Already commented.", "info")
        else:
            res = supabase.table('reel_comments').insert({
                'reel_id': reel_id,
                'user_id': viewer['id'],
                'comment': comment,
            }).execute()
            create_notification(reel.get('user_id'), viewer['id'], 'reel_comment', reel_id=reel_id)
            count_res = supabase.table('reel_comments').select('reel_id', count='exact').eq('reel_id', reel_id).is_('deleted_at', 'null').execute()
            count = count_res.count if count_res else 0
            if wants_json:
                return jsonify({'success': True, 'comment': res.data[0] if res.data else {}, 'count': count, 'xp_toasts': []})
            flash("Comment posted.", "success")
    except Exception as exc:
        if wants_json:
            return jsonify({'success': False, 'error': handle_db_error(exc)}), 400
        flash(handle_db_error(exc), "error")
    return redirect(url_for('reels'))

@app.route('/reels/<int:reel_id>/view', methods=['POST'])
def record_reel_view(reel_id):
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    try:
        reel = get_reel_by_id(reel_id, viewer['id'])
        if not reel or reel.get('is_demo'):
            return jsonify({'success': False, 'error': 'Reel not found.'}), 404
        supabase.table('reel_views').insert({'reel_id': reel_id, 'user_id': viewer['id']}).execute()
        current = parse_int(reel.get('view_count')) or 0
        supabase.table('reels').update({'view_count': current + 1}).eq('id', reel_id).execute()
        return jsonify({'success': True, 'count': current + 1})
    except Exception as exc:
        return jsonify({'success': False, 'error': handle_db_error(exc)}), 400

@app.route('/reels/<int:reel_id>/delete', methods=['POST'])
def delete_reel(reel_id):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    try:
        res = supabase.table('reels').select('id,user_id').eq('id', reel_id).is_('deleted_at', 'null').execute()
        if not res.data:
            flash("Reel not found.", "error")
        elif res.data[0].get('user_id') != viewer['id']:
            flash("You can only delete your own reels.", "error")
        else:
            supabase.table('reels').update({
                'status': 'deleted',
                'deleted_at': datetime.utcnow().isoformat(),
            }).eq('id', reel_id).execute()
            flash("Reel deleted.", "success")
    except Exception as exc:
        flash(handle_db_error(exc, "Could not delete that reel."), "error")
    return redirect(url_for('reels'))

@app.route('/api/reels/<int:reel_id>/comments')
def api_reel_comments(reel_id):
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401
    try:
        res = supabase.table('reel_comments').select('*, user:users!reel_comments_user_id_fkey(id,username,display_name,profile_photo_url)').eq('reel_id', reel_id).is_('deleted_at', 'null').order('created_at', desc=False).limit(50).execute()
        comments = res.data if res and res.data else []
        hidden_commenter_ids = blocked_user_ids_for_viewer(viewer['id'], [comment.get('user_id') for comment in comments], include_mutes=False)
        comments = [comment for comment in comments if comment.get('user_id') not in hidden_commenter_ids]
        return jsonify({'success': True, 'comments': comments})
    except Exception as exc:
        return jsonify({'success': False, 'error': handle_db_error(exc)}), 400


def send_verification_email(to_email, first_name, token):
    settings = mail_settings()

    if not settings['username'] or not settings['password'] or not settings['from_email']:
        app.logger.warning("Email credentials missing. Cannot send verification email.")
        return False

    verify_url = external_url_for('verify_email', token=token)
    msg = MIMEMultipart()
    msg['From'] = settings['from_email']
    msg['To'] = to_email
    msg['Subject'] = "Welcome to LvL! Verify your email to start leveling up"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #000; color: #fff; padding: 20px; text-align: center;">
      <h1 style="color: {THEME_COLORS['primary']};">Welcome to LvL, {first_name}!</h1>
      <p style="font-size: 16px;">We're excited to have you. To start earning XP and connecting with the community, please verify your email address by clicking the button below:</p>
      <div style="margin: 30px 0;">
        <a href="{verify_url}" style="background-color: {THEME_COLORS['primary']}; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 20px; font-weight: bold; font-size: 16px;">Verify My Email</a>
      </div>
      <p style="font-size: 12px; color: {THEME_COLORS['muted']};">If you did not create this account, please ignore this email.</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP(settings['host'], settings['port'])
        if settings['use_tls']:
            server.starttls()
        server.login(settings['username'], settings['password'])
        server.sendmail(settings['from_email'], to_email, msg.as_string())
        server.quit()
        app.logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        app.logger.error(f"Email verification failed to send to {to_email}: {e}")
        return False

def send_password_reset_email(user, token):
    to_email = (user or {}).get('email')
    if not to_email:
        return False

    settings = mail_settings()
    reset_url = external_url_for('reset_password', token=token)

    if not settings['username'] or not settings['password'] or not settings['from_email']:
        app.logger.warning("Email credentials missing. Password reset link for %s: %s", to_email, reset_url)
        return False

    display_name = (user or {}).get('display_name') or (user or {}).get('username') or 'LvL user'
    msg = MIMEMultipart()
    msg['From'] = settings['from_email']
    msg['To'] = to_email
    msg['Subject'] = "Reset your LvL password"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #000; color: #fff; padding: 20px;">
      <h1 style="color: {THEME_COLORS['primary']};">Reset your LvL password</h1>
      <p>Hi {display_name}, use the button below to set a new password. This link expires soon.</p>
      <p><a href="{reset_url}" style="background-color: {THEME_COLORS['primary']}; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 20px; font-weight: bold;">Reset password</a></p>
      <p style="font-size: 12px; color: {THEME_COLORS['muted']};">If you did not request this, you can ignore this email.</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP(settings['host'], settings['port'])
        if settings['use_tls']:
            server.starttls()
        server.login(settings['username'], settings['password'])
        server.sendmail(settings['from_email'], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        app.logger.error("Password reset email failed to send to %s: %s", to_email, exc)
        return False

def find_password_reset_user(account):
    value = (account or '').strip().lower()
    if not value or not supabase:
        return None
    for column in ('username', 'email'):
        res = supabase.table('users').select('id,email,display_name,username').eq(column, value).execute()
        if res and res.data:
            return res.data[0]
    return None

def password_reset_memory_fallback_enabled():
    app_env = (os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or '').strip().lower()
    return app_env not in {'production', 'prod'}

def store_password_reset_token(user_id, raw_token):
    token_hash = password_reset_token_hash(raw_token)
    expires_at = datetime.now(timezone.utc) + PASSWORD_RESET_TTL
    payload = {
        'user_id': user_id,
        'token_hash': token_hash,
        'expires_at': expires_at.isoformat(),
    }
    if supabase:
        try:
            supabase.table('password_reset_tokens').insert(payload).execute()
            return token_hash
        except Exception as exc:
            if not password_reset_memory_fallback_enabled():
                app.logger.error("Password reset token table unavailable; reset link was not created: %s", exc)
                return None
            app.logger.warning("Password reset token table unavailable; using local development fallback: %s", exc)
    PASSWORD_RESET_TOKENS[token_hash] = {**payload, 'used_at': None}
    return token_hash

def parse_reset_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None

def get_password_reset_record(token_hash):
    if supabase:
        res = supabase.table('password_reset_tokens').select('*').eq('token_hash', token_hash).is_('used_at', 'null').execute()
        return res.data[0] if res and res.data else None
    return PASSWORD_RESET_TOKENS.get(token_hash)

def reset_record_is_valid(record):
    if not record or record.get('used_at'):
        return False
    expires_at = parse_reset_datetime(record.get('expires_at'))
    if not expires_at:
        return False
    now = datetime.now(expires_at.tzinfo or timezone.utc)
    return expires_at > now

def mark_password_reset_used(record):
    used_at = datetime.now(timezone.utc).isoformat()
    if supabase and record.get('id'):
        supabase.table('password_reset_tokens').update({'used_at': used_at}).eq('id', record['id']).execute()
    else:
        record['used_at'] = used_at

@app.route('/verify/<token>')
def verify_email(token):
    try:
        res = supabase.table('users').select('*').eq('verification_token', token).execute()
        if res.data:
            user_id = res.data[0]['id']
            supabase.table('users').update({
                'is_verified': True,
                'verification_token': None
            }).eq('id', user_id).execute()
            flash("Your email has been successfully verified! You can now log in and start leveling up.", "success")
        else:
            flash("Invalid or expired verification link. Please request a new one.", "error")
    except Exception as e:
        flash("An error occurred during verification.", "error")

    return redirect(url_for('auth'))

@app.route('/auth/oauth/<provider>')
def oauth_start(provider):
    provider = normalize_oauth_provider(provider)
    if not provider:
        flash("That social login provider is not supported by LvL.", "error")
        return redirect(url_for('auth'))
    if not supabase:
        flash("Supabase connection is required for social login.", "error")
        return redirect(url_for('auth'))

    session['oauth_provider'] = provider

    try:
        response = supabase.auth.sign_in_with_oauth({
            'provider': provider,
            'options': {
                'redirect_to': oauth_redirect_url(),
            },
        })
        store_oauth_code_verifier(supabase.auth)
        return redirect(response.url)
    except Exception as exc:
        clear_oauth_flow_session()
        flash(handle_db_error(exc, f"{oauth_provider_label(provider)} login could not start."), "error")
        return redirect(url_for('auth'))

@app.route('/auth/oauth/callback')
def oauth_callback():
    if not supabase:
        flash("Supabase connection is required for social login.", "error")
        return redirect(url_for('auth'))

    # Handle errors from Supabase/Google - but ignore bad_oauth_state if we have a code
    # In serverless environments (Vercel), session cookies may not persist between
    # the oauth_start and oauth_callback requests, causing false bad_oauth_state errors.
    code = request.args.get('code')
    oauth_error_code = request.args.get('error_code') or ''
    oauth_error = request.args.get('error_description') or request.args.get('error')

    if oauth_error and not (code and oauth_error_code == 'bad_oauth_state'):
        # Only block on real errors; if we have a code and it's just a state mismatch
        # (common in serverless), try to proceed with the code exchange anyway.
        clear_oauth_flow_session()
        flash(f"Social login was cancelled or failed: {oauth_error}", "error")
        return redirect(url_for('auth'))

    expected_state = session.get('oauth_state')
    returned_state = request.args.get('state')
    # Skip strict state check in serverless where sessions may not persist
    if expected_state and returned_state and not secrets.compare_digest(expected_state, returned_state):
        # Log the mismatch but continue if we have a code — serverless session loss
        app.logger.warning("OAuth state mismatch (possible serverless session loss), proceeding with code exchange")

    if not code:
        clear_oauth_flow_session()
        flash("Social login did not return an authorization code.", "error")
        return redirect(url_for('auth'))

    provider = normalize_oauth_provider(session.get('oauth_provider') or 'google')
    try:
        from supabase import create_client
        # Create a temporary client so we don't mutate the global service role client!
        temp_client = create_client(url, key)
        
        restore_oauth_code_verifier(temp_client.auth)
        exchange_params = {
            'auth_code': code,
            'redirect_to': oauth_redirect_url(),
        }
        if session.get('oauth_code_verifier'):
            exchange_params['code_verifier'] = session['oauth_code_verifier']
            
        response = temp_client.auth.exchange_code_for_session(exchange_params)
        auth_user = response.user or (response.session.user if response.session else None)
        if not auth_user:
            raise RuntimeError("Supabase did not return a social login user.")

        profile = extract_oauth_profile(auth_user, provider)
        if not profile.get('provider'):
            profile['provider'] = provider
        if not profile.get('email'):
            flash("This provider did not share an email address. Enable email access in the provider settings and try again.", "error")
            clear_oauth_flow_session(include_pending=True)
            return redirect(url_for('auth'))

        app_user = first_oauth_user_match(profile)
        if app_user:
            sync_oauth_user_fields(app_user, profile)
            session['user_id'] = app_user['id']
            clear_oauth_flow_session(include_pending=True)
            award_xp(app_user['id'], 'daily_login', 5)
            flash(f"Signed in with {oauth_provider_label(profile['provider'])}.", "success")
            return redirect(url_for('index'))

        session['pending_oauth_profile'] = profile
        clear_oauth_flow_session()
        return redirect(url_for('oauth_onboarding'))
    except Exception as exc:
        app.logger.exception("OAuth callback failed")
        clear_oauth_flow_session(include_pending=True)
        flash(f"Social login could not be completed: {str(exc)}", "error")
        return redirect(url_for('auth'))

@app.route('/auth/oauth/onboarding', methods=['GET', 'POST'])
def oauth_onboarding():
    profile = session.get('pending_oauth_profile')
    if not profile:
        flash("Start with a social login provider first.", "info")
        return redirect(url_for('auth'))
    if not supabase:
        flash("Supabase connection is required for social login.", "error")
        return redirect(url_for('auth'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        nickname = normalize_username(request.form.get('nickname', ''))
        email = (request.form.get('email') or profile.get('email') or '').strip().lower()
        gender = normalize_gender(request.form.get('gender', ''))
        birthday = request.form.get('birthday', '').strip()

        if not all([first_name, last_name, nickname, email, gender]):
            flash("All fields are required to finish social registration.", "error")
            return render_template('oauth_onboarding.html', profile=profile, suggested_nickname=oauth_suggested_username(profile))

        if not re.match(r'^[a-z0-9_]{3,24}$', nickname):
            flash("Username must be 3-24 characters: letters, numbers, or underscores only.", "error")
            return render_template('oauth_onboarding.html', profile=profile, suggested_nickname=oauth_suggested_username(profile))

        birthday_value, birthday_error = validate_birthday(birthday, required=True)
        if birthday_error:
            flash(birthday_error, "error")
            return render_template('oauth_onboarding.html', profile=profile, suggested_nickname=oauth_suggested_username(profile))

        existing_user = first_oauth_user_match({**profile, 'email': email})
        if existing_user:
            sync_oauth_user_fields(existing_user, profile)
            session['user_id'] = existing_user['id']
            session.pop('pending_oauth_profile', None)
            award_xp(existing_user['id'], 'daily_login', 5)
            flash("Your social login is now connected to your existing LvL account.", "success")
            return redirect(url_for('index'))

        defaults = gender_defaults(gender)
        random_password = secrets.token_urlsafe(48)
        profile_photo_url = profile.get('avatar_url') or url_for('static', filename=defaults['avatar'])
        payload = {
            'first_name': first_name,
            'last_name': last_name,
            'nickname': nickname,
            'username': nickname,
            'display_name': f"{first_name} {last_name}",
            'email': email,
            'password_hash': bcrypt.hashpw(random_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            'gender': gender,
            'birthday': birthday_value.isoformat(),
            'profile_photo_url': profile_photo_url,
            'theme_color': defaults['theme_color'],
            'avatar_color': defaults['theme_color'],
            'is_verified': True,
            'oauth_provider': profile.get('provider'),
            'oauth_subject': profile.get('subject'),
            'supabase_auth_user_id': profile.get('subject'),
            'oauth_email': email,
        }

        try:
            new_user = supabase.table('users').insert(payload).execute()
            if new_user.data:
                session['user_id'] = new_user.data[0]['id']
                session.pop('pending_oauth_profile', None)
                award_xp(new_user.data[0]['id'], 'account_created', 20)
                flash(f"Welcome to LvL, {first_name}! Your social login is connected.", "success")
                return redirect(url_for('index'))
        except Exception as exc:
            if oauth_schema_error(exc):
                flash("Run database/migrations/005_oauth_identity.sql in Supabase before finishing social login.", "error")
            else:
                flash(handle_db_error(exc), "error")

    return render_template('oauth_onboarding.html', profile=profile, suggested_nickname=oauth_suggested_username(profile))

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        if not supabase:
            flash("Database connection error.", "error")
            return render_template('auth.html')

        action = request.form.get('action')

        if action == 'login':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            if not username or not password:
                flash("Username and password are required.", "error")
                return render_template('auth.html')
            if login_is_limited(username):
                flash("Too many failed login attempts. Wait a few minutes and try again.", "error")
                return render_template('auth.html')

            try:
                res = supabase.table('users').select('*').eq('username', username.lower()).execute()
                if not res.data:
                    res = supabase.table('users').select('*').eq('email', username.lower()).execute()

                if res.data:
                    user = res.data[0]
                    if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                        session['user_id'] = user['id']
                        clear_login_failures(username)
                        award_xp(user['id'], 'daily_login', 5)
                        return redirect(url_for('index'))
                record_login_failure(username)
                flash("Invalid username or password.", "error")
            except Exception as e:
                flash(handle_db_error(e, "An error occurred during login."), "error")

        elif action == 'register':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            nickname = normalize_username(request.form.get('nickname', ''))
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            gender = normalize_gender(request.form.get('gender', ''))
            birthday = request.form.get('birthday', '').strip()

            if not all([first_name, last_name, nickname, email, password, gender]):
                flash("All fields are required.", "error")
                return render_template('auth.html')

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template('auth.html')

            if not re.match(r'^[a-z0-9_]{3,24}$', nickname):
                flash("Username must be 3-24 characters: letters, numbers, or underscores only.", "error")
                return render_template('auth.html')

            birthday_value, birthday_error = validate_birthday(birthday, required=True)
            if birthday_error:
                flash(birthday_error, "error")
                return render_template('auth.html')

            hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            defaults = gender_defaults(gender)

            try:
                new_user = supabase.table('users').insert({
                    'first_name': first_name,
                    'last_name': last_name,
                    'nickname': nickname,
                    'username': nickname,
                    'display_name': f"{first_name} {last_name}",
                    'email': email,
                    'password_hash': hashed_pw,
                    'gender': gender,
                    'birthday': birthday_value.isoformat(),
                    'profile_photo_url': url_for('static', filename=defaults['avatar']),
                    'theme_color': defaults['theme_color'],
                    'avatar_color': defaults['theme_color'],
                    'is_verified': True,
                }).execute()

                if new_user.data:
                    session['user_id'] = new_user.data[0]['id']
                    award_xp(new_user.data[0]['id'], 'account_created', 20)
                    flash(f"Welcome to LvL, {first_name}! You've earned 20 XP for joining.", "success")
                    return redirect(url_for('index'))
            except Exception as e:
                flash(handle_db_error(e), "error")

    return render_template('auth.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        account = request.form.get('account', '')
        if supabase:
            try:
                user = find_password_reset_user(account)
                if user:
                    raw_token = secrets.token_urlsafe(32)
                    stored_hash = store_password_reset_token(user['id'], raw_token)
                    if stored_hash:
                        send_password_reset_email(user, raw_token)
            except Exception as exc:
                app.logger.warning("Password reset request could not be completed: %s", exc)
        flash("If that account exists, a reset link has been sent.", "success")
        return redirect(url_for('forgot_password'))
    return render_template('password_reset.html', mode='request')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_hash = password_reset_token_hash(token)
    try:
        record = get_password_reset_record(token_hash)
    except Exception as exc:
        app.logger.warning("Password reset lookup failed: %s", exc)
        record = None

    if not reset_record_is_valid(record):
        flash("That reset link is invalid or expired.", "error")
        return redirect(url_for('auth'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            if not supabase:
                flash("Database connection error.", "error")
                return render_template('password_reset.html', mode='reset', token=token)
            hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                supabase.table('users').update({'password_hash': hashed_pw}).eq('id', record['user_id']).execute()
                mark_password_reset_used(record)
                flash("Password updated. Log in with your new password.", "success")
                return redirect(url_for('auth'))
            except Exception as exc:
                flash(handle_db_error(exc, "Password could not be updated."), "error")

    return render_template('password_reset.html', mode='reset', token=token)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('auth'))

@app.route('/create_post', methods=['POST'])
def create_post():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    content = request.form.get('content', '').strip()
    image_url = None
    if request.files.get('image'):
        try:
            image_url = upload_image_to_storage(request.files['image'], f"posts/{viewer['id']}")
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return redirect(url_for('index'))

    if content or image_url:
        if len(content) > 280:
            flash("Post cannot exceed 280 characters.", "error")
        elif content and not image_url and recent_duplicate_submission('posts', {'user_id': viewer['id']}, 'content', content):
            flash("Already posted.", "info")
        else:
            try:
                payload = {
                    'user_id': viewer['id'],
                    'content': content
                }
                if image_url:
                    payload['image_url'] = image_url
                res = supabase.table('posts').insert(payload).execute()
                if res.data:
                    award_xp(viewer['id'], 'post_created', 10, res.data[0]['id'])
                flash("Post shared.", "success")
            except Exception as e:
                flash(handle_db_error(e), "error")
    else:
        flash("Post content cannot be empty.", "error")

    return redirect(url_for('index'))

@app.route('/community/<slug>/post', methods=['POST'])
def create_community_post(slug):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    community_item = get_community_by_slug(slug)
    if not community_item:
        return "Community not found.", 404

    membership = get_viewer_membership(community_item['id'], viewer['id'])
    if not membership and community_item.get('owner_id') != viewer['id']:
        flash("Join this community before posting.", "error")
        return redirect(url_for('community_detail', slug=slug))

    content = request.form.get('content', '').strip()
    image_file = request.files.get('image')
    image_url = ''
    video_url = request.form.get('video_url', '').strip()
    video_caption = request.form.get('video_caption', '').strip()

    if content and len(content) > 280:
        flash("Post cannot exceed 280 characters.", "error")
        return redirect(url_for('community_detail', slug=slug))

    if video_url and not re.match(r'^https?://', video_url):
        flash("Video URL must start with http:// or https://.", "error")
        return redirect(url_for('community_detail', slug=slug))

    if image_file and image_file.filename:
        try:
            image_url = upload_image_to_storage(image_file, f"posts/{viewer['id']}")
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for('community_detail', slug=slug))
        except Exception as e:
            flash(handle_db_error(e, "Image upload failed. Try again."), "error")
            return redirect(url_for('community_detail', slug=slug))

    try:
        if content or image_url:
            if content and not image_url and recent_duplicate_submission('posts', {'user_id': viewer['id']}, 'content', content):
                flash("Already posted.", "info")
                return redirect(url_for('community_detail', slug=slug))
            payload = {
                'user_id': viewer['id'],
                'content': content
            }
            if image_url:
                payload['image_url'] = image_url
            res = supabase.table('posts').insert(payload).execute()
            if res.data:
                post_id = res.data[0]['id']
                supabase.table('community_posts').insert({
                    'community_id': community_item['id'],
                    'post_id': post_id,
                    'user_id': viewer['id']
                }).execute()
                award_xp(viewer['id'], 'community_post_created', 8, post_id)

        if video_url:
            supabase.table('community_videos').insert({
                'community_id': community_item['id'],
                'user_id': viewer['id'],
                'video_url': video_url,
                'caption': video_caption or content or ''
            }).execute()

        if content or image_url or video_url:
            flash("Shared to community.", "success")
        else:
            flash("Write a post or add an image first.", "error")
    except Exception:
        flash(community_tables_message(), "error")

    return redirect(url_for('community_detail', slug=slug))

@app.route('/delete_post', methods=['POST'])
def delete_post():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    post_id = parse_int(request.form.get('post_id'))
    if not post_id:
        flash("Post not found.", "error")
        return redirect(safe_redirect_url())

    try:
        post_res = supabase.table('posts').select('id,user_id').eq('id', post_id).execute()
        if not post_res.data:
            flash("Post not found.", "error")
        elif post_res.data[0].get('user_id') != viewer['id']:
            flash("You can only delete your own posts.", "error")
        else:
            supabase.table('posts').update({'deleted_at': datetime.utcnow().isoformat()}).eq('id', post_id).execute()
            flash("Post deleted.", "success")
    except Exception as e:
        flash(handle_db_error(e, "Could not delete that post."), "error")
    return redirect(safe_redirect_url())

@app.route('/share_post/<int:post_id>', methods=['GET', 'POST'])
def share_post(post_id):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        target_id = parse_int(request.form.get('target_user_id'))
        if target_id:
            if target_id == viewer['id']:
                flash("Choose someone else to share with.", "error")
                return redirect(url_for('share_post', post_id=post_id))
            if interaction_blocked(viewer['id'], target_id):
                flash("You cannot share posts with this user.", "error")
                return redirect(url_for('share_post', post_id=post_id))
            try:
                post_url = url_for('post', id=post_id, _external=True)
                supabase.table('messages').insert({
                    'sender_id': viewer['id'],
                    'receiver_id': target_id,
                    'content': f"Check out this post: {post_url}"
                }).execute()
                flash("Post shared via DM!", "success")
                return redirect(url_for('index'))
            except Exception as e:
                flash(handle_db_error(e, "Could not share post."), "error")

    try:
        all_users_res = supabase.table('users').select('*').neq('id', viewer['id']).order('display_name').range(0, 999).execute()
        users = apply_forced_user_levels(all_users_res.data if all_users_res.data else [])
        users = filter_blocked_users(users, viewer['id'], include_mutes=False)
    except Exception:
        users = []

    return render_template('share_post.html', viewer=viewer, users=users, post_id=post_id)

@app.route('/add_comment', methods=['POST'])
def add_comment():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    post_id = parse_int(request.form.get('post_id'))
    comment = request.form.get('comment', '').strip()

    if not post_id:
        flash("Post not found.", "error")
        return redirect(safe_redirect_url(fallback_endpoint='index'))
    if not comment:
        flash("Write a comment first.", "error")
        return redirect(url_for('post', id=post_id))
    if len(comment) > 280:
        flash("Comment cannot exceed 280 characters.", "error")
        return redirect(url_for('post', id=post_id))

    try:
        post_res = supabase.table('posts').select('id,user_id').eq('id', post_id).is_('deleted_at', 'null').execute()
        if not post_res.data:
            flash("Post not found.", "error")
            return redirect(url_for('index'))
        if interaction_blocked(viewer['id'], post_res.data[0]['user_id']):
            flash("You cannot interact with this user.", "error")
            return redirect(url_for('index'))
        if recent_duplicate_submission('comments', {'post_id': post_id, 'user_id': viewer['id']}, 'comment', comment):
            flash("Already commented.", "info")
            return redirect(url_for('post', id=post_id))

        res = supabase.table('comments').insert({
            'post_id': post_id,
            'user_id': viewer['id'],
            'comment': comment
        }).execute()

        if res.data:
            award_xp(viewer['id'], 'comment_created', 6, res.data[0]['id'])

        owner_id = post_res.data[0]['user_id']
        if owner_id != viewer['id']:
            create_notification(owner_id, viewer['id'], 'comment', post_id=post_id)
            award_xp(owner_id, 'comment_received', 4, res.data[0]['id'] if res.data else None)

        flash("Comment posted.", "success")
    except Exception as e:
        flash(handle_db_error(e), "error")

    return redirect(url_for('post', id=post_id))

@app.route('/toggle_like', methods=['POST'])
def toggle_like():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    post_id = request.form.get('post_id')
    liked = False
    count = 0
    if post_id:
        try:
            post_id_int = int(post_id)
            post_res = supabase.table('posts').select('user_id').eq('id', post_id_int).is_('deleted_at', 'null').execute()
            if not post_res.data:
                raise ValueError("Post not found")
            owner_id = post_res.data[0]['user_id']
            if interaction_blocked(viewer['id'], owner_id):
                if request.form.get('ajax') == '1':
                    return jsonify({'success': False, 'error': 'You cannot interact with this user.'}), 403
                flash("You cannot interact with this user.", "error")
                return redirect(safe_redirect_url())

            res = supabase.table('likes').select('*').eq('user_id', viewer['id']).eq('post_id', post_id_int).execute()
            if res.data:
                supabase.table('likes').delete().eq('user_id', viewer['id']).eq('post_id', post_id_int).execute()
                liked = False
            else:
                supabase.table('likes').insert({'user_id': viewer['id'], 'post_id': post_id_int}).execute()
                liked = True
                award_xp(viewer['id'], 'like_given', 1, post_id)

                if owner_id != viewer['id']:
                    create_notification(owner_id, viewer['id'], 'like', post_id=post_id_int)
                    award_xp(owner_id, 'like_received', 2, f"{post_id}:{viewer['id']}")
            count_res = supabase.table('likes').select('post_id', count='exact').eq('post_id', post_id_int).execute()
            count = count_res.count if count_res else 0
        except Exception as e:
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': handle_db_error(e)}), 400
            flash(handle_db_error(e), "error")
    if request.form.get('ajax') == '1':
        return jsonify({'success': True, 'liked': liked, 'count': count})
    return redirect(safe_redirect_url())

@app.route('/toggle_repost', methods=['POST'])
def toggle_repost():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    post_id = request.form.get('post_id')
    reposted = False
    count = 0
    if post_id:
        try:
            post_id_int = int(post_id)
            post_res = supabase.table('posts').select('user_id').eq('id', post_id_int).is_('deleted_at', 'null').execute()
            if not post_res.data:
                raise ValueError("Post not found")
            owner_id = post_res.data[0]['user_id']
            if interaction_blocked(viewer['id'], owner_id):
                if request.form.get('ajax') == '1':
                    return jsonify({'success': False, 'error': 'You cannot interact with this user.'}), 403
                flash("You cannot interact with this user.", "error")
                return redirect(safe_redirect_url())

            res = supabase.table('reposts').select('*').eq('user_id', viewer['id']).eq('post_id', post_id_int).execute()
            if res.data:
                supabase.table('reposts').delete().eq('user_id', viewer['id']).eq('post_id', post_id_int).execute()
                reposted = False
            else:
                supabase.table('reposts').insert({'user_id': viewer['id'], 'post_id': post_id_int}).execute()
                reposted = True
                award_xp(viewer['id'], 'post_reposted', 5, post_id)

                if owner_id != viewer['id']:
                    create_notification(owner_id, viewer['id'], 'repost', post_id=post_id_int)
            count_res = supabase.table('reposts').select('post_id', count='exact').eq('post_id', post_id_int).execute()
            count = count_res.count if count_res else 0
        except Exception as e:
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': handle_db_error(e)}), 400
            flash(handle_db_error(e), "error")
    if request.form.get('ajax') == '1':
        return jsonify({'success': True, 'reposted': reposted, 'count': count})
    return redirect(safe_redirect_url())

@app.route('/toggle_follow', methods=['POST'])
def toggle_follow():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    target_id = request.form.get('target_id')
    following = False
    try:
        target_user_id = int(target_id) if target_id else None
    except (TypeError, ValueError):
        target_user_id = None

    if target_user_id and target_user_id != viewer['id']:
        try:
            if interaction_blocked(viewer['id'], target_user_id):
                if request.form.get('ajax') == '1':
                    return jsonify({'success': False, 'error': 'You cannot interact with this user.'}), 403
                flash("You cannot interact with this user.", "error")
                return redirect(safe_redirect_url())
            res = supabase.table('follows').select('*').eq('follower_id', viewer['id']).eq('following_id', target_user_id).execute()
            if res.data:
                supabase.table('follows').delete().eq('follower_id', viewer['id']).eq('following_id', target_user_id).execute()
                following = False
            else:
                supabase.table('follows').insert({'follower_id': viewer['id'], 'following_id': target_user_id}).execute()
                following = True
                create_notification(target_user_id, viewer['id'], 'follow')
        except Exception as e:
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': handle_db_error(e)}), 400
            flash(handle_db_error(e), "error")

    if request.form.get('ajax') == '1':
        return jsonify({'success': True, 'following': following})

    return redirect(safe_redirect_url())

@app.route('/request_friend', methods=['POST'])
def request_friend():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    is_ajax = request.form.get('ajax') == '1'
    message = "Friends are earned through 7-day high-five or message streaks."
    if is_ajax:
        return jsonify({'success': True, 'status': 'streak_based', 'label': 'High-five', 'message': message})
    flash(message, "info")

    return redirect(safe_redirect_url())

@app.route('/respond_friend_request', methods=['POST'])
def respond_friend_request():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    target_id = request.form.get('target_id')
    decision = request.form.get('decision')
    target_user_id = parse_int(target_id)
    if target_user_id and decision in ['accept', 'decline']:
        try:
            first = min(viewer['id'], target_user_id)
            second = max(viewer['id'], target_user_id)
            friendship = supabase.table('friendships').select('*').eq('user_1', first).eq('user_2', second).eq('status', 'pending').execute()
            if not friendship.data or friendship.data[0].get('action_user_id') == viewer['id']:
                flash("There is no friend request for you to respond to.", "error")
                return redirect(url_for('notifications'))

            if decision == 'accept':
                if interaction_blocked(viewer['id'], target_user_id):
                    flash("You cannot interact with this user.", "error")
                    return redirect(url_for('notifications'))
                supabase.table('friendships').update({'status': 'accepted', 'action_user_id': viewer['id']}).eq('user_1', first).eq('user_2', second).execute()
                create_notification(target_user_id, viewer['id'], 'friend_accept')
                flash("Friend request accepted.", "success")
            else:
                supabase.table('friendships').delete().eq('user_1', first).eq('user_2', second).execute()
                flash("Friend request declined.", "success")
        except Exception as e:
            flash(handle_db_error(e), "error")

    return redirect(url_for('notifications'))

@app.route('/send_message', methods=['POST'])
def send_message():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    receiver_id = parse_int(request.form.get('receiver_id'))
    content = request.form.get('content', '').strip()
    redirect_url = safe_redirect_url(request.form.get('redirect'), 'messages')

    if receiver_id and receiver_id != viewer['id'] and content:
        if len(content) > 1000:
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': 'Message cannot exceed 1000 characters.'}), 400
            flash("Message cannot exceed 1000 characters.", "error")
        elif interaction_blocked(viewer['id'], receiver_id):
            state = get_user_safety_state(viewer['id'], receiver_id)
            message = "Unblock this user to send a message." if state.get('blocked') else "You cannot message this user."
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': message}), 403
            flash(message, "error")
        elif recent_duplicate_submission('messages', {'sender_id': viewer['id'], 'receiver_id': receiver_id}, 'content', content):
            if request.form.get('ajax') == '1':
                return jsonify({'success': False, 'error': 'Already sent.'}), 409
            flash("Already sent.", "info")
        else:
            try:
                recipient = supabase.table('users').select('id').eq('id', receiver_id).execute()
                if not recipient.data:
                    raise ValueError("Recipient not found")
                res = supabase.table('messages').insert({
                    'sender_id': viewer['id'],
                    'receiver_id': receiver_id,
                    'content': content
                }).execute()
                if res.data:
                    create_notification(receiver_id, viewer['id'], 'message', message_id=res.data[0]['id'])
                    streak_count, streak_xp = update_streak(viewer['id'], receiver_id)
                    if request.form.get('ajax') == '1':
                        return jsonify({'success': True, 'message': res.data[0], 'streak': streak_count, 'streak_xp': streak_xp})
            except Exception as e:
                if request.form.get('ajax') == '1':
                    return jsonify({'success': False, 'error': handle_db_error(e)}), 400
                flash(handle_db_error(e), "error")
    elif receiver_id == viewer['id']:
        if request.form.get('ajax') == '1':
            return jsonify({'success': False, 'error': 'You cannot send a message to yourself.'}), 400
        flash("You cannot send a message to yourself.", "error")

    if request.form.get('ajax') == '1':
        return jsonify({'success': False, 'error': 'Message content cannot be empty.'}), 400

    return redirect(redirect_url)

@app.route('/delete_message', methods=['POST'])
def delete_message():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    message_id = parse_int(request.form.get('message_id'))
    redirect_url = safe_redirect_url(request.form.get('redirect'), 'messages')
    wants_json = request.form.get('ajax') == '1'

    if not message_id:
        if wants_json:
            return jsonify({'success': False, 'error': 'Message not found.'}), 400
        flash("Message not found.", "error")
        return redirect(redirect_url)

    try:
        msg_res = supabase.table('messages').select('id,sender_id,receiver_id').eq('id', message_id).execute()
        if not msg_res.data:
            if wants_json:
                return jsonify({'success': False, 'error': 'Message not found.'}), 404
            flash("Message not found.", "error")
        else:
            message = msg_res.data[0]
            participant_ids = {message.get('sender_id'), message.get('receiver_id')}
            if viewer['id'] not in participant_ids:
                if wants_json:
                    return jsonify({'success': False, 'error': 'You can only delete messages from your conversations.'}), 403
                flash("You can only delete messages from your conversations.", "error")
            else:
                supabase.table('notifications').update({'message_id': None}).eq('message_id', message_id).execute()
                supabase.table('messages').delete().eq('id', message_id).execute()
                if wants_json:
                    return jsonify({'success': True, 'message_id': message_id})
                flash("Message deleted.", "success")
    except Exception as e:
        if wants_json:
            return jsonify({'success': False, 'error': handle_db_error(e, "Could not delete that message.")}), 400
        flash(handle_db_error(e, "Could not delete that message."), "error")

    return redirect(redirect_url)

@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    viewer = get_current_user()
    if viewer:
        try:
            supabase.table('notifications').update({'is_read': True}).eq('user_id', viewer['id']).execute()
        except Exception:
            pass
    return redirect(url_for('notifications'))

@app.route('/admin/users/level', methods=['POST'])
def admin_update_user_level():
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    token = request.form.get('admin_token') or request.headers.get('X-LvL-Admin-Token')
    if not admin_token_is_valid(token):
        return jsonify({'success': False, 'error': 'Admin token is missing or invalid.'}), 403

    try:
        updated_user = set_user_level(request.form.get('username', ''), request.form.get('level'))
        return jsonify({'success': True, 'user': updated_user})
    except LookupError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': handle_db_error(exc, "Could not update that user's level.")}), 400

@app.route('/setup-health')
def setup_health():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
    return render_template('setup_health.html',
                           viewer=viewer,
                           checks=get_setup_health(),
                           highlights=get_community_highlights())

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            nickname = normalize_username(request.form.get('nickname', ''))
            bio = request.form.get('bio', '').strip()
            location = request.form.get('location', '').strip()
            website = request.form.get('website', '').strip()
            gender = normalize_gender(request.form.get('gender', ''))
            birthday = request.form.get('birthday', '').strip()
            requested_profile_color = normalize_hex_color(request.form.get('profile_pic'), viewer.get('theme_color') or viewer.get('avatar_color') or THEME_COLORS['muted'])
            profile_pic = requested_profile_color if profile_color_unlocked(viewer.get('level')) else THEME_COLORS['muted']
            remove_profile_photo = request.form.get('remove_profile_photo') == '1'

            if not all([first_name, last_name, nickname, gender]):
                flash("First name, last name, and username are required.", "error")
                return redirect(url_for('settings'))
            if not re.match(r'^[a-z0-9_]{3,24}$', nickname):
                flash("Username must be 3-24 characters and use only letters, numbers, or underscores.", "error")
                return redirect(url_for('settings'))
            if website and not normalize_website(website):
                flash("Website must start with http:// or https://.", "error")
                return redirect(url_for('settings'))
            uploaded_profile_url = None
            if request.files.get('profile_photo'):
                try:
                    uploaded_profile_url = upload_image_to_storage(request.files['profile_photo'], f"avatars/{viewer['id']}")
                except (ValueError, RuntimeError) as exc:
                    flash(str(exc), "error")
                    return redirect(url_for('settings'))
            birthday_value, birthday_error = validate_birthday(birthday)
            if birthday_error:
                flash(birthday_error, "error")
                return redirect(url_for('settings'))

            try:
                defaults = gender_defaults(gender)
                updates = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'nickname': nickname,
                    'username': nickname,
                    'display_name': f"{first_name} {last_name}",
                    'bio': bio,
                    'location': location,
                    'website': normalize_website(website),
                    'gender': gender,
                    'theme_color': profile_pic,
                    'avatar_color': profile_pic
                }
                default_avatar_urls = {
                    url_for('static', filename=option['avatar'])
                    for option in GENDER_OPTIONS.values()
                }
                if remove_profile_photo:
                    updates['profile_photo_url'] = url_for('static', filename=defaults['avatar'])
                elif not viewer.get('profile_photo_url') or viewer.get('profile_photo_url') in default_avatar_urls:
                    updates['profile_photo_url'] = url_for('static', filename=defaults['avatar'])
                if uploaded_profile_url:
                    updates['profile_photo_url'] = uploaded_profile_url
                updates['birthday'] = birthday_value.isoformat() if birthday_value else None

                supabase.table('users').update(updates).eq('id', viewer['id']).execute()
                flash("Profile updated.", "success")
                return redirect(url_for('profile', username=nickname))
            except Exception as e:
                flash(handle_db_error(e), "error")

    return render_template('settings.html',
                           viewer=viewer,
                           highlights=get_community_highlights(),
                           home_reels=get_home_reel_preview(viewer['id']))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    confirm_username = normalize_username(request.form.get('confirm_username', ''))
    current_password = request.form.get('current_password', '')

    if confirm_username != viewer.get('username'):
        flash("Type your username exactly to delete your account.", "error")
        return redirect(url_for('settings'))
    if not current_password:
        flash("Enter your current password to delete your account.", "error")
        return redirect(url_for('settings'))

    try:
        password_hash = (viewer.get('password_hash') or '').encode('utf-8')
        if not password_hash or not bcrypt.checkpw(current_password.encode('utf-8'), password_hash):
            flash("Current password is incorrect.", "error")
            return redirect(url_for('settings'))

        supabase.table('users').delete().eq('id', viewer['id']).execute()
        session.clear()
        flash("Your account has been deleted.", "success")
        return redirect(url_for('auth'))
    except ValueError:
        flash("Current password could not be verified.", "error")
    except Exception as e:
        flash(handle_db_error(e, "Could not delete your account."), "error")

    return redirect(url_for('settings'))

@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()[:180]
        location = request.form.get('location', '').strip()[:80]
        interests = ', '.join(request.form.getlist('interests')[:5])
        follow_ids = [parse_int(value) for value in request.form.getlist('follow_ids')]
        follow_ids = [value for value in follow_ids if value and value != viewer['id']]
        follow_ids = [value for value in follow_ids if not interaction_blocked(viewer['id'], value)]

        try:
            updates = {
                'bio': bio,
                'location': location,
                'onboarding_completed': True
            }
            if interests:
                updates['interests'] = interests
            supabase.table('users').update(updates).eq('id', viewer['id']).execute()

            for follow_id in follow_ids:
                existing = supabase.table('follows').select('follower_id').eq('follower_id', viewer['id']).eq('following_id', follow_id).execute()
                if not existing.data:
                    supabase.table('follows').insert({'follower_id': viewer['id'], 'following_id': follow_id}).execute()
            flash("Your profile is ready.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(handle_db_error(e, "Onboarding needs the latest database migration first."), "error")

    try:
        suggested_res = supabase.table('users').select('*').neq('id', viewer['id']).order('level', desc=True).limit(6).execute()
        suggested_users = merge_forced_level_users(suggested_res.data if suggested_res and suggested_res.data else [], limit=6)
        suggested_users = filter_blocked_users(suggested_users, viewer['id'], include_mutes=False)
    except Exception:
        suggested_users = []

    return render_template('onboarding.html', viewer=viewer, suggested_users=suggested_users)

@app.route('/profile')
def own_profile():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
    return redirect(url_for('profile', username=viewer['username']))

@app.route('/level-guide')
def level_guide():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
    highlights = get_community_highlights()
    level_requirements = [{'level': level, 'xp': xp_required_for_level(level)} for level in range(1, 31)]
    return render_template('level_guide.html',
                           viewer=viewer,
                           highlights=highlights,
                           level_requirements=level_requirements,
                           xp_rewards=XP_REWARD_RULES,
                           level_rewards=LEVEL_REWARD_TIERS,
                           reward_product_table=LEVEL_REWARD_PRODUCT_TABLE,
                           achievements=ACHIEVEMENT_DEFINITIONS)

@app.route('/activity')
def activity():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    return render_template('activity.html',
                           viewer=viewer,
                           highlights=get_community_highlights(),
                           activity_items=get_user_activity(viewer))

@app.route('/profile/<username>')
def profile(username):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    mode = request.args.get('m', 'posts')
    page = parse_positive_int(request.args.get('page'), default=1, maximum=500)
    highlights = get_community_highlights()

    try:
        res = supabase.table('users').select('*').eq('username', username).execute()
        if not res.data:
            return "Profile not found.", 404

        profile_user = apply_forced_user_levels(res.data[0])
        is_own_profile = viewer['id'] == profile_user['id']
        safety_state = get_user_safety_state(viewer['id'], profile_user['id'])
        profile_hidden_by_safety = safety_state.get('interaction_blocked') and not is_own_profile

        is_following = False
        friend_status = None
        friend_action_user_id = None
        streak_status = get_pair_streak_status(viewer['id'], profile_user['id'])

        if not is_own_profile and not profile_hidden_by_safety:
            follow_res = supabase.table('follows').select('*').eq('follower_id', viewer['id']).eq('following_id', profile_user['id']).execute()
            is_following = len(follow_res.data) > 0

        if profile_hidden_by_safety:
            stats = {'following': 0, 'followers': 0, 'friends': 0, 'posts': 0, 'comments': 0}
            posts = []
        else:
            posts_count = supabase.table('posts').select('id', count='exact').eq('user_id', profile_user['id']).is_('deleted_at', 'null').execute()
            comments_count = supabase.table('comments').select('id', count='exact').eq('user_id', profile_user['id']).execute()
            followers_count = supabase.table('follows').select('id', count='exact').eq('following_id', profile_user['id']).execute()
            following_count = supabase.table('follows').select('id', count='exact').eq('follower_id', profile_user['id']).execute()
            _, streak_friend_ids = get_streak_friend_ids(profile_user['id'])

            stats = {
                'following': following_count.count if following_count else 0,
                'followers': followers_count.count if followers_count else 0,
                'friends': len(streak_friend_ids),
                'posts': posts_count.count if posts_count else 0,
                'comments': comments_count.count if comments_count else 0
            }

            select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
            if mode == 'liked':
                likes_res = supabase.table('likes').select('post_id').eq('user_id', profile_user['id']).execute()
                liked_post_ids = [l['post_id'] for l in likes_res.data] if likes_res.data else []
                if liked_post_ids:
                    offset = (page - 1) * POSTS_PER_PAGE
                    posts_res = supabase.table('posts').select(select_query).in_('id', liked_post_ids).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + POSTS_PER_PAGE - 1).execute()
                    posts = visible_post_filter(posts_res.data if posts_res and posts_res.data else [], viewer['id'])
                else:
                    posts = []
            else:
                posts = get_profile_posts(profile_user, viewer['id'], page=page)

        if mode == 'liked':
            posts = enrich_posts(posts, viewer['id'])

        level = max(1, profile_user.get('level', 1))
        profile_banner = profile_banner_for_level(level)
        total_xp = profile_user.get('total_xp', 0)
        current_xp_req = xp_required_for_level(level)
        next_xp_req = xp_required_for_level(level + 1)
        progress = min(100, max(0, ((total_xp - current_xp_req) / max(1, next_xp_req - current_xp_req)) * 100))
        achievements = profile_achievements(profile_user, stats)
        summary = achievement_summary(achievements)

    except Exception as e:
        flash(handle_db_error(e), "error")
        return redirect(url_for('index'))

    return render_template('profile.html',
                           viewer=viewer,
                           profile=profile_user,
                           is_own_profile=is_own_profile,
                           is_following=is_following,
                           friend_status=friend_status,
                           friend_action_user_id=friend_action_user_id,
                           streak_status=streak_status,
                           safety_state=safety_state,
                           stats=stats,
                           posts=posts,
                           mode=mode,
                           page=page,
                           has_next=len(posts) == POSTS_PER_PAGE,
                           highlights=highlights,
                           profile_banner=profile_banner,
                           profile_banner_class=profile_banner['class'],
                           profile_xp_progress=progress,
                           profile_xp_needed=next_xp_req - total_xp,
                           profile_xp_current=max(0, total_xp - current_xp_req),
                           profile_xp_span=max(1, next_xp_req - current_xp_req),
                           next_level_reward=next_level_reward_for_level(level),
                           achievement_summary=summary,
                           achievements=achievements)

@app.route('/profile/<username>/high-five', methods=['POST'])
def high_five_profile(username):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    try:
        res = supabase.table('users').select('id, username, display_name').eq('username', username).execute()
        if not res.data:
            flash("Profile not found.", "error")
            return redirect(url_for('index'))

        target = res.data[0]
        if target['id'] == viewer['id']:
            flash("You cannot high-five yourself.", "info")
            return redirect(url_for('profile', username=username))
        if interaction_blocked(viewer['id'], target['id']):
            flash("You cannot interact with this user.", "error")
            return redirect(url_for('profile', username=username))

        streak_count, streak_xp = update_streak(viewer['id'], target['id'])
        try:
            create_notification(target['id'], viewer['id'], 'high_five')
        except Exception:
            app.logger.info("High-five notification could not be created", exc_info=True)

        if streak_count > 1:
            extra = f" {streak_xp} XP bonus." if streak_xp else ""
            flash(f"High-five sent. You have a {streak_count}-day high-five streak with {target['display_name']}.{extra}", "success")
        else:
            flash(f"High-five sent to {target['display_name']}. Come back tomorrow to build the streak.", "success")
    except Exception as e:
        flash(handle_db_error(e), "error")

    return redirect(url_for('profile', username=username))

@app.route('/profile/<username>/<list_type>')
def profile_social_list(username, list_type):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
    if list_type not in {'followers', 'following', 'friends'}:
        return "List not found.", 404

    try:
        profile_res = supabase.table('users').select('*').eq('username', normalize_username(username)).execute()
        if not profile_res.data:
            return "Profile not found.", 404
        profile_user = apply_forced_user_levels(profile_res.data[0])
        list_title, users = get_social_list(profile_user, list_type, viewer['id'])
        highlights = get_community_highlights()
    except Exception as e:
        flash(handle_db_error(e), "error")
        return redirect(url_for('profile', username=username))

    return render_template('social_list.html',
                           viewer=viewer,
                           profile=profile_user,
                           list_type=list_type,
                           list_title=list_title,
                           users=users,
                           highlights=highlights)

@app.route('/safety_action', methods=['POST'])
def safety_action():
    viewer = get_current_user()
    if not viewer:
        if request.form.get('ajax') == '1':
            return jsonify({'success': False, 'error': 'Login required.'}), 401
        return redirect(url_for('auth'))

    action_type = request.form.get('action_type')
    target_user_id = parse_int(request.form.get('target_user_id'))
    post_id = parse_int(request.form.get('post_id'))
    reason = request.form.get('reason', '').strip()[:280]
    is_ajax = request.form.get('ajax') == '1'

    if action_type not in {'report', 'block', 'mute'} or not target_user_id or target_user_id == viewer['id']:
        if is_ajax:
            return jsonify({'success': False, 'error': 'That safety action is not available.'}), 400
        flash("That safety action is not available.", "error")
        return redirect(safe_redirect_url())

    try:
        payload = {
            'actor_id': viewer['id'],
            'target_user_id': target_user_id,
            'post_id': post_id,
            'action_type': action_type,
            'reason': reason
        }
        existing = supabase.table('user_safety_actions').select('id').eq('actor_id', viewer['id']).eq('target_user_id', target_user_id).eq('action_type', action_type)
        if post_id:
            existing = existing.eq('post_id', post_id)
        existing_res = existing.execute()
        active = True
        if existing_res.data and action_type in {'block', 'mute'}:
            supabase.table('user_safety_actions').delete().eq('id', existing_res.data[0]['id']).execute()
            label = {'block': 'unblocked', 'mute': 'unmuted'}[action_type]
            active = False
        else:
            if not existing_res.data:
                supabase.table('user_safety_actions').insert(payload).execute()
            if action_type == 'block':
                first = min(viewer['id'], target_user_id)
                second = max(viewer['id'], target_user_id)
                supabase.table('follows').delete().eq('follower_id', viewer['id']).eq('following_id', target_user_id).execute()
                supabase.table('follows').delete().eq('follower_id', target_user_id).eq('following_id', viewer['id']).execute()
                supabase.table('friendships').delete().eq('user_1', first).eq('user_2', second).execute()
            label = {'report': 'reported', 'block': 'blocked', 'mute': 'muted'}[action_type]
        if is_ajax:
            return jsonify({'success': True, 'active': active, 'action_type': action_type, 'label': label})
        flash(f"User {label}.", "success")
    except Exception as e:
        if is_ajax:
            return jsonify({'success': False, 'error': handle_db_error(e)}), 400
        flash(handle_db_error(e, "Safety controls need the latest database migration first."), "error")
    return redirect(safe_redirect_url())

def attach_shared_posts(messages_list):
    if not messages_list:
        return messages_list
    post_ids = []
    for msg in messages_list:
        match = re.search(r'/post/(\d+)', msg.get('content', ''))
        if match:
            post_ids.append(int(match.group(1)))

    if post_ids:
        try:
            p_res = supabase.table('posts').select('*, user:users!posts_user_id_fkey(*)').in_('id', list(set(post_ids))).execute()
            apply_forced_user_levels(p_res.data if p_res and p_res.data else [])
            posts_by_id = {p['id']: p for p in p_res.data} if p_res and p_res.data else {}
            for msg in messages_list:
                match = re.search(r'/post/(\d+)', msg.get('content', ''))
                if match:
                    msg['shared_post'] = posts_by_id.get(int(match.group(1)))
        except Exception as e:
            app.logger.error(f"Error attaching shared posts: {e}")
    return messages_list

def mark_message_thread_read(viewer_id, other_user_id):
    if not viewer_id or not other_user_id:
        return
    supabase.table('messages').update({'is_read': True}).eq('sender_id', other_user_id).eq('receiver_id', viewer_id).execute()
    try:
        supabase.table('notifications').update({'is_read': True}).eq('user_id', viewer_id).eq('actor_id', other_user_id).eq('type', 'message').eq('is_read', False).execute()
    except Exception as exc:
        app.logger.debug("Message notification read sync skipped: %s", exc)

@app.route('/messages')
def messages():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    target_username = request.args.get('u', '')
    target_user = None
    chat_safety_state = {'blocked': False, 'blocked_by': False, 'interaction_blocked': False}
    messages_list = []

    try:
        if target_username:
            res = supabase.table('users').select('*').eq('username', target_username).execute()
            if res.data:
                target_user = apply_forced_user_levels(res.data[0])
                if target_user['id'] == viewer['id']:
                    flash("Choose someone else to message.", "error")
                    target_user = None
                else:
                    chat_safety_state = get_user_safety_state(viewer['id'], target_user['id'])
                    msg_res = supabase.table('messages').select('*').or_(f"and(sender_id.eq.{viewer['id']},receiver_id.eq.{target_user['id']}),and(sender_id.eq.{target_user['id']},receiver_id.eq.{viewer['id']})").order('created_at', desc=False).execute()
                    messages_list = msg_res.data if msg_res.data else []
                    messages_list = attach_shared_posts(messages_list)
                    mark_message_thread_read(viewer['id'], target_user['id'])

        all_users_res = supabase.table('users').select('*').neq('id', viewer['id']).order('display_name').range(0, 999).execute()
        all_users_raw = apply_forced_user_levels(all_users_res.data if all_users_res.data else [])
        all_users = filter_blocked_users(all_users_raw, viewer['id'], include_mutes=False)
        all_users_by_id = {user['id']: user for user in all_users_raw}

        conversation_res = supabase.table('messages').select('*').or_(f"sender_id.eq.{viewer['id']},receiver_id.eq.{viewer['id']}").order('created_at', desc=True).limit(100).execute()
        conversation_rows = conversation_res.data if conversation_res and conversation_res.data else []
        conversations = []
        seen_users = set()
        for message in conversation_rows:
            other_id = message['receiver_id'] if message['sender_id'] == viewer['id'] else message['sender_id']
            if other_id in seen_users or other_id not in all_users_by_id:
                continue
            other_user = dict(all_users_by_id[other_id])
            other_user['last_message'] = message.get('content', '')
            other_user['last_message_at'] = (message.get('created_at') or '')[11:16]
            other_user['is_read'] = message['sender_id'] == viewer['id'] or message.get('is_read', False)
            other_user['unread_count'] = sum(1 for row in conversation_rows if row.get('sender_id') == other_id and row.get('receiver_id') == viewer['id'] and not row.get('is_read'))
            other_user['streak_count'] = 0
            conversations.append(other_user)
            seen_users.add(other_id)

        # Ensure target_user always has streak_count
        if target_user and 'streak_count' not in target_user:
            target_user = dict(target_user)
            target_user['streak_count'] = 0

        # Attach streak counts to conversations
        try:
            viewer_id = viewer['id']
            streaks_res = supabase.table('user_streaks').select('user_1,user_2,streak_count').or_(
                f"user_1.eq.{viewer_id},user_2.eq.{viewer_id}"
            ).execute()
            streaks_by_user = {}
            for s in (streaks_res.data or []):
                other = s['user_2'] if s['user_1'] == viewer_id else s['user_1']
                streaks_by_user[other] = s.get('streak_count', 0)
            for conv in conversations:
                conv['streak_count'] = streaks_by_user.get(conv['id'], 0)
            if target_user:
                target_user['streak_count'] = streaks_by_user.get(target_user['id'], 0)
        except Exception:
            pass

    except Exception as e:
        flash(handle_db_error(e), "error")
        conversations = []
        all_users = []

    explore = get_explore_context(viewer)

    return render_template('messages.html',
                           viewer=viewer,
                           target_username=target_username,
                           target_user=target_user,
                           chat_safety_state=chat_safety_state,
                           conversations=conversations,
                           all_users=all_users,
                           messages_list=messages_list,
                           suggested_communities=explore['communities'][:3],
                           message_trending_posts=explore['trending_posts'][:3],
                           message_people=explore['popular_users'][:4],
                           highlights=get_community_highlights(),
                           home_reels=get_home_reel_preview(viewer['id']))

@app.route('/api/messages/<username>')
def api_messages(username):
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    since_id = parse_int(request.args.get('since_id')) or 0
    try:
        target_res = supabase.table('users').select('*').eq('username', username).execute()
        if not target_res.data:
            return jsonify({'success': False, 'error': 'User not found.'}), 404
        target_user = apply_forced_user_levels(target_res.data[0])
        if target_user['id'] == viewer['id']:
            return jsonify({'success': False, 'error': 'Choose someone else to message.'}), 400

        query = supabase.table('messages').select('*').or_(f"and(sender_id.eq.{viewer['id']},receiver_id.eq.{target_user['id']}),and(sender_id.eq.{target_user['id']},receiver_id.eq.{viewer['id']})")
        if since_id:
            query = query.gt('id', since_id)
        msg_res = query.order('created_at', desc=False).limit(50).execute()
        messages_list = msg_res.data if msg_res and msg_res.data else []
        messages_list = attach_shared_posts(messages_list)
        if messages_list:
            mark_message_thread_read(viewer['id'], target_user['id'])
        return jsonify({'success': True, 'messages': messages_list, 'viewer_id': viewer['id']})
    except Exception as e:
        return jsonify({'success': False, 'error': handle_db_error(e)}), 400

@app.route('/api/live-status')
def api_live_status():
    viewer = get_current_user()
    if not viewer:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401
    return jsonify({
        'success': True,
        'unread_notifications': unread_notification_count(viewer['id']),
        'unread_messages': unread_message_count(viewer['id']),
    })

@app.route('/notifications')
def notifications():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    try:
        notif_res = supabase.table('notifications').select('*, actor:users!actor_id(*)').eq('user_id', viewer['id']).order('created_at', desc=True).limit(50).execute()
        raw_notifications = apply_forced_user_levels(notif_res.data if notif_res and notif_res.data else [])
        hidden_actor_ids = blocked_user_ids_for_viewer(viewer['id'], [item.get('actor_id') for item in raw_notifications], include_mutes=False)
        raw_notifications = [item for item in raw_notifications if item.get('actor_id') not in hidden_actor_ids]

        formatted = []
        for n in raw_notifications:
            actor = n.get('actor', {})
            n['actor_username'] = actor.get('username', '')
            n['actor_name'] = actor.get('display_name', '')
            n['friendship_status'] = 'pending'
            n['friendship_action_user_id'] = actor.get('id')
            if n.get('type') == 'message':
                n['message_url'] = url_for('messages', u=n['actor_username']) if n['actor_username'] else url_for('messages')
            formatted.append(n)
        formatted = stack_notifications(formatted)
        post_ids = [item['post_id'] for item in formatted if item.get('post_id')]
        if post_ids:
            posts_res = supabase.table('posts').select('id, content').in_('id', list(set(post_ids))).execute()
            posts_by_id = {post['id']: post.get('content', '') for post in posts_res.data} if posts_res and posts_res.data else {}
            for item in formatted:
                item['post_content'] = posts_by_id.get(item.get('post_id'), 'View post')
        reel_ids = [item['reel_id'] for item in formatted if item.get('reel_id')]
        if reel_ids:
            reels_res = supabase.table('reels').select('id, caption').in_('id', list(set(reel_ids))).execute()
            reels_by_id = {reel['id']: reel.get('caption', '') for reel in reels_res.data} if reels_res and reels_res.data else {}
            for item in formatted:
                if item.get('reel_id'):
                    item['reel_caption'] = reels_by_id.get(item.get('reel_id'), 'Open reel')
                    item['reel_url'] = f"{url_for('reels')}#reel-{item['reel_id']}"
        for item in formatted:
            if item.get('type') == 'friend_request' and item.get('actor_id'):
                first = min(viewer['id'], item['actor_id'])
                second = max(viewer['id'], item['actor_id'])
                friend_res = supabase.table('friendships').select('status, action_user_id').eq('user_1', first).eq('user_2', second).execute()
                if friend_res.data:
                    item['friendship_status'] = friend_res.data[0].get('status')
                    item['friendship_action_user_id'] = friend_res.data[0].get('action_user_id')

        if any(not item.get('is_read') for item in formatted):
            supabase.table('notifications').update({'is_read': True}).eq('user_id', viewer['id']).eq('is_read', False).execute()

    except Exception as e:
        flash(handle_db_error(e), "error")
        formatted = []

    return render_template('notifications.html', viewer=viewer, notifications=formatted)

@app.route('/community')
def community():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    explore = get_explore_context(viewer)
    timeline_context = get_community_timeline_context(viewer, request.args.get('tab'))
    return render_template('community.html',
                           viewer=viewer,
                           metrics=explore['metrics'],
                           recent_members=explore['recent_members'],
                           popular_users=explore['popular_users'],
                           trending_posts=explore['trending_posts'],
                           communities=explore['communities'],
                           activity_items=explore['activity_items'],
                           community_tabs=timeline_context['tabs'],
                           active_tab=timeline_context['active_tab'],
                           timeline_feeds=timeline_context['feeds'],
                           timeline_counts=timeline_context['counts'],
                           highlights=get_community_highlights(),
                           home_reels=get_home_reel_preview(viewer['id']))

@app.route('/communities/new', methods=['GET', 'POST'])
def create_community():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        accent_color = normalize_hex_color(request.form.get('accent_color'), viewer.get('theme_color') or THEME_COLORS['primary'])
        slug = slugify(request.form.get('slug') or name)

        if not name or len(name) > 80:
            flash("Community name is required and must be 80 characters or less.", "error")
            return redirect(url_for('create_community'))

        if len(description) > 240:
            flash("Community description cannot exceed 240 characters.", "error")
            return redirect(url_for('create_community'))

        try:
            existing = supabase.table('communities').select('id').eq('slug', slug).execute()
            if existing and existing.data:
                flash("That community URL is already taken.", "error")
                return redirect(url_for('create_community'))

            res = supabase.table('communities').insert({
                'name': name,
                'slug': slug,
                'description': description,
                'owner_id': viewer['id'],
                'accent_color': accent_color
            }).execute()
            if res.data:
                community_id = res.data[0]['id']
                supabase.table('community_members').insert({
                    'community_id': community_id,
                    'user_id': viewer['id'],
                    'role': 'admin'
                }).execute()
                flash("Community created.", "success")
                return redirect(url_for('community_detail', slug=slug))
        except Exception:
            flash(community_tables_message(), "error")

    return render_template('community_form.html',
                           viewer=viewer,
                           community=None,
                           form_action=url_for('create_community'),
                           title="Create Community",
                           highlights=get_community_highlights())

@app.route('/community/<slug>')
def community_detail(slug):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    community_item = get_community_by_slug(slug)
    if not community_item:
        return "Community not found.", 404

    membership = get_viewer_membership(community_item['id'], viewer['id'])
    is_admin = community_item.get('owner_id') == viewer['id'] or (membership and membership.get('role') == 'admin')
    posts = get_community_posts(community_item['id'], viewer['id'])
    members = get_community_members(community_item['id'], viewer_id=viewer['id'])

    return render_template('community_detail.html',
                           viewer=viewer,
                           community=community_item,
                           membership=membership,
                           is_admin=is_admin,
                           posts=posts,
                           members=members,
                           highlights=get_community_highlights())

@app.route('/community/<slug>/edit', methods=['GET', 'POST'])
def edit_community(slug):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    community_item = get_community_by_slug(slug)
    if not community_item:
        return "Community not found.", 404
    if community_item.get('owner_id') != viewer['id']:
        flash("Only the community owner can edit this community.", "error")
        return redirect(url_for('community_detail', slug=slug))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        accent_color = normalize_hex_color(request.form.get('accent_color'), community_item.get('accent_color') or THEME_COLORS['primary'])

        if not name or len(name) > 80:
            flash("Community name is required and must be 80 characters or less.", "error")
            return redirect(url_for('edit_community', slug=slug))

        try:
            supabase.table('communities').update({
                'name': name,
                'description': description[:240],
                'accent_color': accent_color
            }).eq('id', community_item['id']).execute()
            flash("Community updated.", "success")
            return redirect(url_for('community_detail', slug=slug))
        except Exception:
            flash(community_tables_message(), "error")

    return render_template('community_form.html',
                           viewer=viewer,
                           community=community_item,
                           form_action=url_for('edit_community', slug=slug),
                           title="Edit Community",
                           highlights=get_community_highlights())

@app.route('/community/<slug>/join', methods=['POST'])
def join_community(slug):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    community_item = get_community_by_slug(slug)
    if not community_item:
        return "Community not found.", 404

    try:
        existing = get_viewer_membership(community_item['id'], viewer['id'])
        if not existing:
            supabase.table('community_members').insert({
                'community_id': community_item['id'],
                'user_id': viewer['id'],
                'role': 'member'
            }).execute()
        flash("Joined community.", "success")
    except Exception:
        flash(community_tables_message(), "error")
    return redirect(url_for('community_detail', slug=slug))

@app.route('/community/<slug>/leave', methods=['POST'])
def leave_community(slug):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    community_item = get_community_by_slug(slug)
    if not community_item:
        return "Community not found.", 404

    if community_item.get('owner_id') == viewer['id']:
        flash("Owners cannot leave their own community.", "error")
        return redirect(url_for('community_detail', slug=slug))

    try:
        supabase.table('community_members').delete().eq('community_id', community_item['id']).eq('user_id', viewer['id']).execute()
        flash("Left community.", "success")
    except Exception:
        flash(community_tables_message(), "error")
    return redirect(url_for('community_detail', slug=slug))

@app.route('/search')
def search():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    query = request.args.get('q', '').strip()
    tab = request.args.get('f', 'top')
    page = parse_positive_int(request.args.get('page'), default=1, maximum=500)

    users = []
    posts = []
    suggested_users = []
    recent_posts = []
    highlights = get_community_highlights()

    try:
        select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
        if query:
            if tab == 'people':
                safe_query = query.replace('%', '').replace(',', ' ')
                offset = (page - 1) * POSTS_PER_PAGE
                res = supabase.table('users').select('*').or_(f"display_name.ilike.%{safe_query}%,username.ilike.%{safe_query}%,nickname.ilike.%{safe_query}%").range(offset, offset + POSTS_PER_PAGE - 1).execute()
                users = res.data if res.data else []
                users = filter_blocked_users(users, viewer['id'], include_mutes=False)
                users = mark_following_state(users, viewer['id'])
            else:
                order_desc = True
                offset = (page - 1) * POSTS_PER_PAGE
                res = supabase.table('posts').select(select_query).ilike('content', f"%{query}%").is_('deleted_at', 'null').order('created_at', desc=order_desc).range(offset, offset + POSTS_PER_PAGE - 1).execute()
                posts = res.data if res.data else []
                posts = enrich_posts(visible_post_filter(posts, viewer['id']), viewer['id'])
        else:
            discovery = get_search_discovery_context(viewer)
            suggested_users = discovery['suggested_users']
            recent_posts = discovery['recent_posts']
    except Exception as e:
        flash(handle_db_error(e), "error")

    return render_template('search.html',
                           viewer=viewer,
                           query=query,
                           tab=tab,
                           users=users,
                           posts=posts,
                           suggested_users=suggested_users,
                           recent_posts=recent_posts,
                           page=page,
                           has_next=(len(users) if tab == 'people' else len(posts)) == POSTS_PER_PAGE,
                           highlights=highlights)

@app.route('/post/<int:id>')
def post(id):
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    try:
        select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
        post_res = supabase.table('posts').select(select_query).eq('id', id).is_('deleted_at', 'null').execute()
        if not post_res.data:
            return render_template('post.html', viewer=viewer, post=None)
        if interaction_blocked(viewer['id'], post_res.data[0].get('user_id')):
            return render_template('post.html', viewer=viewer, post=None)

        post_data = enrich_posts(post_res.data, viewer['id'])[0]

        com_res = supabase.table('comments').select('*, user:users(*)').eq('post_id', id).order('created_at', desc=False).execute()
        comments = apply_forced_user_levels(com_res.data if com_res and com_res.data else [])
        hidden_commenter_ids = blocked_user_ids_for_viewer(viewer['id'], [comment.get('user_id') for comment in comments], include_mutes=False)
        comments = [comment for comment in comments if comment.get('user_id') not in hidden_commenter_ids]

        return render_template('post.html', viewer=viewer, post=post_data, comments=comments)
    except Exception as e:
        flash(handle_db_error(e), "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
