import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from supabase import create_client, Client
import bcrypt
import logging

from app_utils import birthday_date_limits, normalize_username, profile_banner_for_level, validate_birthday

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-default-key")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production"
)
logging.basicConfig(level=logging.INFO)

url: str = os.getenv("SUPABASE_URL", "")
key: str = os.getenv("SUPABASE_SECRET", os.getenv("SUPABASE_KEY", ""))
supabase: Client = create_client(url, key) if url and key else None
LOGIN_ATTEMPTS = {}
LOGIN_WINDOW = timedelta(minutes=10)
LOGIN_MAX_ATTEMPTS = 5
POSTS_PER_PAGE = 10
MAX_IMAGE_BYTES = 50 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "lvl-media")
LOCAL_IMAGE_UPLOAD_FALLBACK = os.getenv("LOCAL_IMAGE_UPLOAD_FALLBACK", "true").lower() not in {"0", "false", "no"}
IMAGE_CONTENT_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

GENDER_OPTIONS = {
    'Male': {
        'theme_color': '#1D9BF0',
        'avatar': 'assets/default-male-avatar.svg'
    },
    'Female': {
        'theme_color': '#F91880',
        'avatar': 'assets/default-female-avatar.svg'
    }
}

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
    if not supabase and request.endpoint == 'auth':
        flash("Supabase connection failed. Add SUPABASE_URL and SUPABASE_SECRET to your .env file.", "error")
    elif not supabase and request.endpoint not in {'static', 'service_worker', 'auth'}:
        flash("Database connection error.", "error")
        return redirect(url_for('auth'))

@app.context_processor
def inject_helpers():
    return {
        'csrf_token': get_csrf_token,
        'level_title': activity_title_for_level,
        'birthday_limits': birthday_date_limits,
    }

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

def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

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
    if level >= 30: return '#F5C542'
    if level >= 20: return '#F97316'
    if level >= 10: return '#8B5CF6'
    if level >= 5: return '#1D9BF0'
    return '#71767B'

def activity_title_for_level(level):
    if level >= 30: return 'Mythic Legend'
    if level >= 20: return 'Elite Champion'
    if level >= 10: return 'Rising Hero'
    if level >= 5: return 'Quest Regular'
    return 'New Adventurer'

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
                return res.data[0]
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
    return send_from_directory(app.static_folder, 'service-worker.js')

def normalize_gender(value):
    value = (value or '').strip().title()
    return value if value in GENDER_OPTIONS else ''

def gender_defaults(gender):
    return GENDER_OPTIONS.get(gender, GENDER_OPTIONS['Male'])

def normalize_hex_color(value, fallback='#1D9BF0'):
    value = (value or '').strip()
    return value.upper() if re.match(r'^#[0-9A-Fa-f]{6}$', value) else fallback

def normalize_website(value):
    value = (value or '').strip()
    if not value:
        return ''
    return value if re.match(r'^https?://', value) else ''

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def ensure_storage_bucket(bucket_name):
    if not supabase:
        raise RuntimeError("Supabase is not configured.")
    try:
        supabase.storage.get_bucket(bucket_name)
    except Exception:
        supabase.storage.create_bucket(bucket_name, options={
            "public": True,
            "file_size_limit": MAX_IMAGE_BYTES,
            "allowed_mime_types": [
                "image/jpeg",
                "image/png",
                "image/gif",
                "image/webp"
            ]
        })

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

def get_user_safety_state(viewer_id, target_user_id):
    state = {'blocked': False, 'muted': False}
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
    return state

def visible_post_filter(posts, viewer_id):
    if not posts:
        return []
    author_ids = {post.get('user_id') for post in posts if post.get('user_id') and post.get('user_id') != viewer_id}
    hidden_ids = set()
    if author_ids:
        try:
            safety_res = supabase.table('user_safety_actions').select('target_user_id').eq('actor_id', viewer_id).in_('target_user_id', list(author_ids)).in_('action_type', ['block', 'mute']).execute()
            hidden_ids = {row['target_user_id'] for row in safety_res.data or []}
        except Exception:
            hidden_ids = set()
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
    post_ids = [p['id'] for p in posts]
    
    likes_res = supabase.table('likes').select('post_id').eq('user_id', viewer_id).in_('post_id', post_ids).execute()
    viewer_liked_ids = {l['post_id'] for l in likes_res.data} if likes_res.data else set()
    
    reposts_res = supabase.table('reposts').select('post_id').eq('user_id', viewer_id).in_('post_id', post_ids).execute()
    viewer_reposted_ids = {r['post_id'] for r in reposts_res.data} if reposts_res.data else set()

    for p in posts:
        p['like_count'] = p.get('likes', [{}])[0].get('count', 0) if p.get('likes') else 0
        p['reply_count'] = p.get('comments', [{}])[0].get('count', 0) if p.get('comments') else 0
        p['repost_count'] = p.get('reposts', [{}])[0].get('count', 0) if p.get('reposts') else 0
        p['viewer_liked'] = p['id'] in viewer_liked_ids
        p['viewer_reposted'] = p['id'] in viewer_reposted_ids
    return posts

def mark_following_state(users, viewer_id):
    if not users:
        return []
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
        rows = supabase.table('friendships').select('user_1,user_2').or_(f"user_1.eq.{profile_id},user_2.eq.{profile_id}").eq('status', 'accepted').execute()
        user_ids = []
        for row in rows.data or []:
            user_ids.append(row['user_2'] if row.get('user_1') == profile_id else row.get('user_1'))
    else:
        user_ids = []

    user_ids = [user_id for user_id in dict.fromkeys(user_ids) if user_id]
    if not user_ids:
        return title, []
    users_res = supabase.table('users').select('*').in_('id', user_ids).execute()
    users = users_res.data if users_res and users_res.data else []
    return title, mark_following_state(users, viewer_id)

def get_following_feed_posts(viewer_id, limit=POSTS_PER_PAGE, page=1):
    follows_res = supabase.table('follows').select('following_id').eq('follower_id', viewer_id).execute()
    following_ids = [f['following_id'] for f in follows_res.data] if follows_res and follows_res.data else []
    if not following_ids:
        return []
    select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(select_query).in_('user_id', following_ids).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    posts = posts_res.data if posts_res and posts_res.data else []
    return enrich_posts(visible_post_filter(posts, viewer_id), viewer_id)

def get_feed_posts(viewer_id, limit=POSTS_PER_PAGE, page=1):
    select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(select_query).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    direct_posts = posts_res.data if posts_res and posts_res.data else []

    reposts_res = supabase.table('reposts').select('user_id, post_id, created_at').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    repost_rows = reposts_res.data if reposts_res and reposts_res.data else []
    repost_post_ids = [row['post_id'] for row in repost_rows if row.get('post_id')]
    reposter_ids = list({row['user_id'] for row in repost_rows if row.get('user_id')})

    repost_posts_by_id = {}
    if repost_post_ids:
        repost_posts_res = supabase.table('posts').select(select_query).in_('id', repost_post_ids).is_('deleted_at', 'null').execute()
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
    return enrich_posts(visible_post_filter(timeline[:limit], viewer_id), viewer_id)

def get_profile_posts(profile_user, viewer_id, limit=POSTS_PER_PAGE, page=1):
    select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
    offset = (page - 1) * limit
    posts_res = supabase.table('posts').select(select_query).eq('user_id', profile_user['id']).is_('deleted_at', 'null').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    direct_posts = posts_res.data if posts_res and posts_res.data else []

    reposts_res = supabase.table('reposts').select('post_id, created_at').eq('user_id', profile_user['id']).order('created_at', desc=True).range(offset, offset + limit - 1).execute()
    repost_rows = reposts_res.data if reposts_res and reposts_res.data else []
    repost_post_ids = [row['post_id'] for row in repost_rows if row.get('post_id')]

    repost_posts_by_id = {}
    if repost_post_ids:
        repost_posts_res = supabase.table('posts').select(select_query).in_('id', repost_post_ids).is_('deleted_at', 'null').execute()
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
    return enrich_posts(visible_post_filter(timeline[:limit], viewer_id), viewer_id)

def get_community_highlights():
    try:
        res = supabase.table('users').select('*').order('level', desc=True).limit(3).execute()
        return res.data if res.data else []
    except Exception:
        return []

def get_communities(limit=6):
    try:
        res = supabase.table('communities').select('*, owner:users!communities_owner_id_fkey(*)').order('created_at', desc=True).limit(limit).execute()
        communities = res.data if res and res.data else []
        for item in communities:
            item['member_count'] = item.get('member_count', 0)
        return communities
    except Exception:
        return []

def get_community_by_slug(slug):
    try:
        res = supabase.table('communities').select('*, owner:users!communities_owner_id_fkey(*)').eq('slug', slug).execute()
        return res.data[0] if res and res.data else None
    except Exception:
        return None

def get_short_videos(limit=8, community_id=None):
    try:
        query = supabase.table('community_videos').select('*, author:users!community_videos_user_id_fkey(*), community:communities!community_videos_community_id_fkey(*)')
        if community_id:
            query = query.eq('community_id', community_id)
        res = query.order('created_at', desc=True).limit(limit).execute()
        return res.data if res and res.data else []
    except Exception:
        return []

def get_trending_posts(viewer_id, limit=5):
    try:
        select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
        posts_res = supabase.table('posts').select(select_query).is_('deleted_at', 'null').order('created_at', desc=True).limit(limit).execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        return enrich_posts(posts, viewer_id)
    except Exception:
        return []

def get_popular_users(viewer_id, limit=5):
    try:
        res = supabase.table('users').select('*').order('level', desc=True).limit(limit).execute()
        users = res.data if res and res.data else []
        return mark_following_state(users, viewer_id)
    except Exception:
        return []

def get_community_posts(community_id, viewer_id, limit=20):
    try:
        link_res = supabase.table('community_posts').select('post_id').eq('community_id', community_id).order('created_at', desc=True).limit(limit).execute()
        post_ids = [row['post_id'] for row in link_res.data] if link_res and link_res.data else []
        if not post_ids:
            return []
        select_query = '*, user:users!posts_user_id_fkey(*), likes(count), comments(count), reposts(count)'
        posts_res = supabase.table('posts').select(select_query).in_('id', post_ids).is_('deleted_at', 'null').execute()
        posts = posts_res.data if posts_res and posts_res.data else []
        posts_by_id = {post['id']: post for post in posts}
        ordered_posts = [posts_by_id[post_id] for post_id in post_ids if post_id in posts_by_id]
        return enrich_posts(ordered_posts, viewer_id)
    except Exception:
        return []

def get_community_members(community_id, limit=8):
    try:
        res = supabase.table('community_members').select('*, user:users!community_members_user_id_fkey(*)').eq('community_id', community_id).order('created_at', desc=True).limit(limit).execute()
        return res.data if res and res.data else []
    except Exception:
        return []

def get_viewer_membership(community_id, viewer_id):
    try:
        res = supabase.table('community_members').select('*').eq('community_id', community_id).eq('user_id', viewer_id).execute()
        return res.data[0] if res and res.data else None
    except Exception:
        return None

def get_explore_context(viewer):
    context = {
        'metrics': {'users': 0, 'profiles': 0, 'posts': 0, 'comments': 0, 'likes': 0, 'follows': 0, 'messages': 0, 'notifications': 0, 'communities': 0, 'videos': 0},
        'recent_members': [],
        'popular_users': [],
        'trending_posts': [],
        'communities': [],
        'short_videos': [],
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
        context['recent_members'] = recent_res.data if recent_res and recent_res.data else []
    except Exception:
        pass

    context['popular_users'] = get_popular_users(viewer['id'], 5)
    context['trending_posts'] = get_trending_posts(viewer['id'], 5)
    context['communities'] = get_communities(6)
    context['short_videos'] = get_short_videos(8)
    context['metrics']['communities'] = len(context['communities'])
    context['metrics']['videos'] = len(context['short_videos'])

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

    return render_template('index.html', viewer=viewer, posts=posts, mode=feed_mode, highlights=highlights, page=page, has_next=len(posts) == POSTS_PER_PAGE)


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
                flash("Username must contain only letters, numbers, and underscores.", "error")
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
                    'avatar_color': defaults['theme_color']
                }).execute()
                
                if new_user.data:
                    session['user_id'] = new_user.data[0]['id']
                    flash("Account created successfully!", "success")
                    return redirect(url_for('onboarding'))
            except Exception as e:
                flash(handle_db_error(e), "error")
    
    return render_template('auth.html')

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
    video_url = request.form.get('video_url', '').strip()
    video_caption = request.form.get('video_caption', '').strip()

    if content and len(content) > 280:
        flash("Post cannot exceed 280 characters.", "error")
        return redirect(url_for('community_detail', slug=slug))

    if video_url and not re.match(r'^https?://', video_url):
        flash("Video URL must start with http:// or https://.", "error")
        return redirect(url_for('community_detail', slug=slug))

    try:
        if content:
            res = supabase.table('posts').insert({
                'user_id': viewer['id'],
                'content': content
            }).execute()
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

        if content or video_url:
            flash("Shared to community.", "success")
        else:
            flash("Write a post or add a video URL first.", "error")
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
        target_id = request.form.get('target_user_id')
        if target_id:
            try:
                post_url = url_for('post', id=post_id, _external=True)
                supabase.table('messages').insert({
                    'sender_id': viewer['id'],
                    'receiver_id': int(target_id),
                    'content': f"Check out this post: {post_url}"
                }).execute()
                flash("Post shared via DM!", "success")
                return redirect(url_for('index'))
            except Exception as e:
                flash(handle_db_error(e, "Could not share post."), "error")
                
    try:
        all_users_res = supabase.table('users').select('*').neq('id', viewer['id']).order('display_name').execute()
        users = all_users_res.data if all_users_res.data else []
    except Exception:
        users = []
        
    return render_template('share_post.html', viewer=viewer, users=users, post_id=post_id)

@app.route('/add_comment', methods=['POST'])
def add_comment():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
        
    post_id = request.form.get('post_id')
    comment = request.form.get('comment', '').strip()
    
    if comment and post_id:
        if len(comment) > 280:
            flash("Comment cannot exceed 280 characters.", "error")
        else:
            try:
                res = supabase.table('comments').insert({
                    'post_id': int(post_id),
                    'user_id': viewer['id'],
                    'comment': comment
                }).execute()
                
                if res.data:
                    award_xp(viewer['id'], 'comment_created', 6, res.data[0]['id'])
                
                post_res = supabase.table('posts').select('user_id').eq('id', int(post_id)).execute()
                if post_res.data and post_res.data[0]['user_id'] != viewer['id']:
                    owner_id = post_res.data[0]['user_id']
                    supabase.table('notifications').insert({
                        'user_id': owner_id,
                        'actor_id': viewer['id'],
                        'type': 'comment',
                        'post_id': int(post_id)
                    }).execute()
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
            res = supabase.table('likes').select('*').eq('user_id', viewer['id']).eq('post_id', int(post_id)).execute()
            if res.data:
                supabase.table('likes').delete().eq('user_id', viewer['id']).eq('post_id', int(post_id)).execute()
                liked = False
            else:
                supabase.table('likes').insert({'user_id': viewer['id'], 'post_id': int(post_id)}).execute()
                liked = True
                award_xp(viewer['id'], 'like_given', 1, post_id)
                
                post_res = supabase.table('posts').select('user_id').eq('id', int(post_id)).execute()
                if post_res.data and post_res.data[0]['user_id'] != viewer['id']:
                    owner_id = post_res.data[0]['user_id']
                    supabase.table('notifications').insert({
                        'user_id': owner_id,
                        'actor_id': viewer['id'],
                        'type': 'like',
                        'post_id': int(post_id)
                    }).execute()
                    award_xp(owner_id, 'like_received', 2, f"{post_id}:{viewer['id']}")
            count_res = supabase.table('likes').select('post_id', count='exact').eq('post_id', int(post_id)).execute()
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
            res = supabase.table('reposts').select('*').eq('user_id', viewer['id']).eq('post_id', int(post_id)).execute()
            if res.data:
                supabase.table('reposts').delete().eq('user_id', viewer['id']).eq('post_id', int(post_id)).execute()
                reposted = False
            else:
                supabase.table('reposts').insert({'user_id': viewer['id'], 'post_id': int(post_id)}).execute()
                reposted = True
                award_xp(viewer['id'], 'post_reposted', 5, post_id)
                
                post_res = supabase.table('posts').select('user_id').eq('id', int(post_id)).execute()
                if post_res.data and post_res.data[0]['user_id'] != viewer['id']:
                    owner_id = post_res.data[0]['user_id']
                    supabase.table('notifications').insert({
                        'user_id': owner_id,
                        'actor_id': viewer['id'],
                        'type': 'repost',
                        'post_id': int(post_id)
                    }).execute()
            count_res = supabase.table('reposts').select('post_id', count='exact').eq('post_id', int(post_id)).execute()
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
            res = supabase.table('follows').select('*').eq('follower_id', viewer['id']).eq('following_id', target_user_id).execute()
            if res.data:
                supabase.table('follows').delete().eq('follower_id', viewer['id']).eq('following_id', target_user_id).execute()
                following = False
            else:
                supabase.table('follows').insert({'follower_id': viewer['id'], 'following_id': target_user_id}).execute()
                following = True
                supabase.table('notifications').insert({
                    'user_id': target_user_id,
                    'actor_id': viewer['id'],
                    'type': 'follow'
                }).execute()
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
        
    target_id = request.form.get('target_id')
    target_user_id = parse_int(target_id)
    if target_user_id and target_user_id != viewer['id']:
        try:
            first = min(viewer['id'], target_user_id)
            second = max(viewer['id'], target_user_id)
            
            res = supabase.table('friendships').select('*').eq('user_1', first).eq('user_2', second).execute()
            if not res.data:
                supabase.table('friendships').insert({
                    'user_1': first,
                    'user_2': second,
                    'action_user_id': viewer['id'],
                    'status': 'pending'
                }).execute()
                supabase.table('notifications').insert({
                    'user_id': target_user_id,
                    'actor_id': viewer['id'],
                    'type': 'friend_request'
                }).execute()
                flash("Friend request sent.", "success")
            elif res.data[0].get('status') == 'pending' and res.data[0].get('action_user_id') != viewer['id']:
                flash("This person already sent you a request. Accept it from notifications.", "info")
        except Exception as e:
            flash(handle_db_error(e), "error")
            
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
                supabase.table('friendships').update({'status': 'accepted', 'action_user_id': viewer['id']}).eq('user_1', first).eq('user_2', second).execute()
                supabase.table('notifications').insert({
                    'user_id': target_user_id,
                    'actor_id': viewer['id'],
                    'type': 'friend_accept'
                }).execute()
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
                    supabase.table('notifications').insert({
                        'user_id': receiver_id,
                        'actor_id': viewer['id'],
                        'type': 'message',
                        'message_id': res.data[0]['id']
                    }).execute()
                    if request.form.get('ajax') == '1':
                        return jsonify({'success': True, 'message': res.data[0]})
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
            profile_pic = normalize_hex_color(request.form.get('profile_pic'), viewer.get('theme_color') or viewer.get('avatar_color') or '#1D9BF0')
            remove_profile_photo = request.form.get('remove_profile_photo') == '1'
            
            if not all([first_name, last_name, nickname, gender]):
                flash("First name, last name, and username are required.", "error")
                return redirect(url_for('settings'))
            if not re.match(r'^[a-z0-9_]{3,24}$', nickname):
                flash("Username must be 3-24 characters and use letters, numbers, or underscores.", "error")
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
                
    return render_template('settings.html', viewer=viewer)

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
        suggested_users = suggested_res.data if suggested_res and suggested_res.data else []
    except Exception:
        suggested_users = []

    return render_template('onboarding.html', viewer=viewer, suggested_users=suggested_users)

@app.route('/profile')
def own_profile():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
    return redirect(url_for('profile', username=viewer['username']))

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
            
        profile_user = res.data[0]
        is_own_profile = viewer['id'] == profile_user['id']
        safety_state = get_user_safety_state(viewer['id'], profile_user['id'])
        
        is_following = False
        friend_status = None
        friend_action_user_id = None
        
        if not is_own_profile:
            follow_res = supabase.table('follows').select('*').eq('follower_id', viewer['id']).eq('following_id', profile_user['id']).execute()
            is_following = len(follow_res.data) > 0
            
            first = min(viewer['id'], profile_user['id'])
            second = max(viewer['id'], profile_user['id'])
            friend_res = supabase.table('friendships').select('*').eq('user_1', first).eq('user_2', second).execute()
            if friend_res.data:
                friend_status = friend_res.data[0]['status']
                friend_action_user_id = friend_res.data[0]['action_user_id']
                
        posts_count = supabase.table('posts').select('id', count='exact').eq('user_id', profile_user['id']).is_('deleted_at', 'null').execute()
        comments_count = supabase.table('comments').select('id', count='exact').eq('user_id', profile_user['id']).execute()
        followers_count = supabase.table('follows').select('id', count='exact').eq('following_id', profile_user['id']).execute()
        following_count = supabase.table('follows').select('id', count='exact').eq('follower_id', profile_user['id']).execute()
        friends_count = supabase.table('friendships').select('user_1', count='exact').or_(f"user_1.eq.{profile_user['id']},user_2.eq.{profile_user['id']}").eq('status', 'accepted').execute()
        
        stats = {
            'following': following_count.count if following_count else 0, 
            'followers': followers_count.count if followers_count else 0, 
            'friends': friends_count.count if friends_count else 0,
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
                posts = posts_res.data if posts_res and posts_res.data else []
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
                           profile_xp_needed=next_xp_req - total_xp)

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
        profile_user = profile_res.data[0]
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
        return redirect(url_for('auth'))

    action_type = request.form.get('action_type')
    target_user_id = parse_int(request.form.get('target_user_id'))
    post_id = parse_int(request.form.get('post_id'))
    reason = request.form.get('reason', '').strip()[:280]

    if action_type not in {'report', 'block', 'mute'} or not target_user_id or target_user_id == viewer['id']:
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
        if existing_res.data and action_type in {'block', 'mute'}:
            supabase.table('user_safety_actions').delete().eq('id', existing_res.data[0]['id']).execute()
            label = {'block': 'unblocked', 'mute': 'unmuted'}[action_type]
            flash(f"User {label}.", "success")
            return redirect(safe_redirect_url())
        if not existing_res.data:
            supabase.table('user_safety_actions').insert(payload).execute()
        label = {'report': 'reported', 'block': 'blocked', 'mute': 'muted'}[action_type]
        flash(f"User {label}.", "success")
    except Exception as e:
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
            posts_by_id = {p['id']: p for p in p_res.data} if p_res and p_res.data else {}
            for msg in messages_list:
                match = re.search(r'/post/(\d+)', msg.get('content', ''))
                if match:
                    msg['shared_post'] = posts_by_id.get(int(match.group(1)))
        except Exception as e:
            app.logger.error(f"Error attaching shared posts: {e}")
    return messages_list

@app.route('/messages')
def messages():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
        
    target_username = request.args.get('u', '')
    target_user = None
    messages_list = []
    
    try:
        if target_username:
            res = supabase.table('users').select('*').eq('username', target_username).execute()
            if res.data:
                target_user = res.data[0]
                if target_user['id'] == viewer['id']:
                    flash("Choose someone else to message.", "error")
                    target_user = None
                else:
                    msg_res = supabase.table('messages').select('*').or_(f"and(sender_id.eq.{viewer['id']},receiver_id.eq.{target_user['id']}),and(sender_id.eq.{target_user['id']},receiver_id.eq.{viewer['id']})").order('created_at', desc=False).execute()
                    messages_list = msg_res.data if msg_res.data else []
                    messages_list = attach_shared_posts(messages_list)
                    supabase.table('messages').update({'is_read': True}).eq('sender_id', target_user['id']).eq('receiver_id', viewer['id']).execute()
                
        all_users_res = supabase.table('users').select('*').neq('id', viewer['id']).order('display_name').execute()
        all_users = all_users_res.data if all_users_res.data else []
        all_users_by_id = {user['id']: user for user in all_users}

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
            conversations.append(other_user)
            seen_users.add(other_id)
        
    except Exception as e:
        flash(handle_db_error(e), "error")
        conversations = []
        all_users = []

    explore = get_explore_context(viewer)

    return render_template('messages.html', 
                           viewer=viewer, 
                           target_username=target_username, 
                           target_user=target_user,
                           conversations=conversations,
                           all_users=all_users,
                           messages_list=messages_list,
                           suggested_communities=explore['communities'][:3],
                           message_trending_posts=explore['trending_posts'][:3],
                           message_people=explore['popular_users'][:4])

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
        target_user = target_res.data[0]
        if target_user['id'] == viewer['id']:
            return jsonify({'success': False, 'error': 'Choose someone else to message.'}), 400

        query = supabase.table('messages').select('*').or_(f"and(sender_id.eq.{viewer['id']},receiver_id.eq.{target_user['id']}),and(sender_id.eq.{target_user['id']},receiver_id.eq.{viewer['id']})")
        if since_id:
            query = query.gt('id', since_id)
        msg_res = query.order('created_at', desc=False).limit(50).execute()
        messages_list = msg_res.data if msg_res and msg_res.data else []
        messages_list = attach_shared_posts(messages_list)
        if messages_list:
            supabase.table('messages').update({'is_read': True}).eq('sender_id', target_user['id']).eq('receiver_id', viewer['id']).execute()
        return jsonify({'success': True, 'messages': messages_list, 'viewer_id': viewer['id']})
    except Exception as e:
        return jsonify({'success': False, 'error': handle_db_error(e)}), 400

@app.route('/notifications')
def notifications():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))
        
    try:
        notif_res = supabase.table('notifications').select('*, actor:users!actor_id(*)').eq('user_id', viewer['id']).order('created_at', desc=True).limit(50).execute()
        raw_notifications = notif_res.data if notif_res and notif_res.data else []
        
        formatted = []
        for n in raw_notifications:
            actor = n.get('actor', {})
            n['actor_username'] = actor.get('username', '')
            n['actor_name'] = actor.get('display_name', '')
            n['friendship_status'] = 'pending'
            n['friendship_action_user_id'] = actor.get('id')
            formatted.append(n)
        post_ids = [item['post_id'] for item in formatted if item.get('post_id')]
        if post_ids:
            posts_res = supabase.table('posts').select('id, content').in_('id', list(set(post_ids))).execute()
            posts_by_id = {post['id']: post.get('content', '') for post in posts_res.data} if posts_res and posts_res.data else {}
            for item in formatted:
                item['post_content'] = posts_by_id.get(item.get('post_id'), 'View post')
        for item in formatted:
            if item.get('type') == 'friend_request' and item.get('actor_id'):
                first = min(viewer['id'], item['actor_id'])
                second = max(viewer['id'], item['actor_id'])
                friend_res = supabase.table('friendships').select('status, action_user_id').eq('user_1', first).eq('user_2', second).execute()
                if friend_res.data:
                    item['friendship_status'] = friend_res.data[0].get('status')
                    item['friendship_action_user_id'] = friend_res.data[0].get('action_user_id')
            
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
    return render_template('community.html',
                           viewer=viewer,
                           metrics=explore['metrics'],
                           recent_members=explore['recent_members'],
                           popular_users=explore['popular_users'],
                           trending_posts=explore['trending_posts'],
                           communities=explore['communities'],
                           short_videos=explore['short_videos'],
                           activity_items=explore['activity_items'],
                           highlights=get_community_highlights())

@app.route('/communities/new', methods=['GET', 'POST'])
def create_community():
    viewer = get_current_user()
    if not viewer:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        accent_color = normalize_hex_color(request.form.get('accent_color'), viewer.get('theme_color') or '#1D9BF0')
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
    videos = get_short_videos(10, community_item['id'])
    members = get_community_members(community_item['id'])

    return render_template('community_detail.html',
                           viewer=viewer,
                           community=community_item,
                           membership=membership,
                           is_admin=is_admin,
                           posts=posts,
                           videos=videos,
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
        accent_color = normalize_hex_color(request.form.get('accent_color'), community_item.get('accent_color') or '#1D9BF0')

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
                users = mark_following_state(users, viewer['id'])
            else:
                order_desc = True
                offset = (page - 1) * POSTS_PER_PAGE
                res = supabase.table('posts').select(select_query).ilike('content', f"%{query}%").is_('deleted_at', 'null').order('created_at', desc=order_desc).range(offset, offset + POSTS_PER_PAGE - 1).execute()
                posts = res.data if res.data else []
                posts = enrich_posts(posts, viewer['id'])
        else:
            sug_res = supabase.table('users').select('*').neq('id', viewer['id']).limit(4).execute()
            suggested_users = sug_res.data if sug_res and sug_res.data else []
            suggested_users = mark_following_state(suggested_users, viewer['id'])
            
            rec_res = supabase.table('posts').select(select_query).is_('deleted_at', 'null').order('created_at', desc=True).limit(3).execute()
            recent_posts = rec_res.data if rec_res and rec_res.data else []
            recent_posts = enrich_posts(recent_posts, viewer['id'])
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
            
        post_data = enrich_posts(post_res.data, viewer['id'])[0]
        
        com_res = supabase.table('comments').select('*, user:users(*)').eq('post_id', id).order('created_at', desc=False).execute()
        comments = com_res.data if com_res and com_res.data else []
        
        return render_template('post.html', viewer=viewer, post=post_data, comments=comments)
    except Exception as e:
        flash(handle_db_error(e), "error")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
