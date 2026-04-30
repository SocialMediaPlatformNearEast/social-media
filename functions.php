<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';

function h(?string $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function redirect(string $path): never
{
    header('Location: ' . $path);
    exit;
}

function flash(?string $message = null, string $type = 'info'): ?array
{
    if ($message !== null) {
        $_SESSION['flash'] = ['message' => $message, 'type' => $type];
        return null;
    }

    $flash = $_SESSION['flash'] ?? null;
    unset($_SESSION['flash']);
    return $flash;
}

function csrf_token(): string
{
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }

    return $_SESSION['csrf_token'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf_token" value="' . h(csrf_token()) . '">';
}

function require_valid_csrf(): void
{
    $token = $_POST['csrf_token'] ?? '';
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $token)) {
        flash('Security check failed. Please try again.', 'error');
        redirect('index.php');
    }
}

function current_user(): ?array
{
    if (empty($_SESSION['user_id'])) {
        return null;
    }

    static $user = null;
    if ($user !== null && (int) $user['id'] === (int) $_SESSION['user_id']) {
        return $user;
    }

    $stmt = db()->prepare(
        'SELECT
            u.*,
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.bio, u.bio, "") AS bio,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color,
            COALESCE(pr.updated_at, u.updated_at) AS profile_updated_at
         FROM users u
         LEFT JOIN profiles pr ON pr.user_id = u.id
         WHERE u.id = ?
         LIMIT 1'
    );
    $stmt->execute([$_SESSION['user_id']]);
    $user = $stmt->fetch() ?: null;
    return $user;
}

function require_auth(): array
{
    $user = current_user();
    if (!$user) {
        flash('Log in to continue.', 'error');
        redirect('auth.php');
    }

    return $user;
}

function time_ago(string $datetime): string
{
    $seconds = max(1, time() - strtotime($datetime));
    $units = [
        31536000 => 'y',
        2592000 => 'mo',
        604800 => 'w',
        86400 => 'd',
        3600 => 'h',
        60 => 'm',
    ];

    foreach ($units as $unitSeconds => $label) {
        if ($seconds >= $unitSeconds) {
            return (string) floor($seconds / $unitSeconds) . $label;
        }
    }

    return $seconds . 's';
}

function ensure_profile(int $userId, string $displayName, string $avatarColor): void
{
    $stmt = db()->prepare('INSERT IGNORE INTO profiles (user_id, display_name, profile_pic) VALUES (?, ?, ?)');
    $stmt->execute([$userId, $displayName, $avatarColor]);
}

function notify_user(int $userId, int $actorId, string $type, ?int $postId = null, ?int $messageId = null): void
{
    if ($userId === $actorId) {
        return;
    }

    $stmt = db()->prepare(
        'INSERT INTO notifications (user_id, actor_id, type, post_id, message_id) VALUES (?, ?, ?, ?, ?)'
    );
    $stmt->execute([$userId, $actorId, $type, $postId, $messageId]);
}

function post_owner_id(int $postId): ?int
{
    $stmt = db()->prepare('SELECT user_id FROM posts WHERE id = ? AND deleted_at IS NULL LIMIT 1');
    $stmt->execute([$postId]);
    $owner = $stmt->fetchColumn();
    return $owner === false ? null : (int) $owner;
}

function user_stats(int $userId): array
{
    $stmt = db()->prepare(
        'SELECT
            (SELECT COUNT(*) FROM posts WHERE user_id = ? AND deleted_at IS NULL) AS posts,
            (SELECT COUNT(*) FROM follows WHERE follower_id = ?) AS following,
            (SELECT COUNT(*) FROM follows WHERE following_id = ?) AS followers,
            (SELECT COUNT(*) FROM comments WHERE user_id = ?) AS comments,
            (SELECT COUNT(*) FROM friendships WHERE (user_1 = ? OR user_2 = ?) AND status = "accepted") AS friends'
    );
    $stmt->execute([$userId, $userId, $userId, $userId, $userId, $userId]);
    return $stmt->fetch() ?: ['posts' => 0, 'following' => 0, 'followers' => 0, 'comments' => 0, 'friends' => 0];
}

function app_metrics(): array
{
    $stmt = db()->query(
        'SELECT
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM profiles) AS profiles,
            (SELECT COUNT(*) FROM posts WHERE deleted_at IS NULL) AS posts,
            (SELECT COUNT(*) FROM comments) AS comments,
            (SELECT COUNT(*) FROM likes) AS likes,
            (SELECT COUNT(*) FROM follows) AS follows,
            (SELECT COUNT(*) FROM messages) AS messages,
            (SELECT COUNT(*) FROM notifications) AS notifications'
    );

    return $stmt->fetch() ?: [];
}

function fetch_posts(int $viewerId, string $mode = 'all', ?int $profileId = null, string $search = ''): array
{
    $where = ['p.deleted_at IS NULL'];
    $params = [$viewerId, $viewerId];
    $joinFollowing = '';
    $joinLikes = '';

    if ($mode === 'following') {
        $joinFollowing = 'INNER JOIN follows feed_follows ON feed_follows.following_id = p.user_id AND feed_follows.follower_id = ?';
        $params[] = $viewerId;
    }

    if ($mode === 'liked' && $profileId !== null) {
        $joinLikes = 'INNER JOIN likes l_mode ON l_mode.post_id = p.id AND l_mode.user_id = ?';
        $params[] = $profileId;
    } elseif ($profileId !== null) {
        $where[] = 'p.user_id = ?';
        $params[] = $profileId;
    }

    if ($search !== '') {
        $where[] = '(p.content LIKE ? OR u.username LIKE ? OR COALESCE(pr.display_name, u.display_name) LIKE ?)';
        $term = '%' . $search . '%';
        $params[] = $term;
        $params[] = $term;
        $params[] = $term;
    }

    $sql = "SELECT
            p.*,
            u.username,
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.profile_pic, u.avatar_color, '#111111') AS avatar_color,
            COALESCE(pr.bio, u.bio, '') AS bio,
            rp.content AS repost_content,
            ru.username AS repost_username,
            COALESCE(rpr.display_name, ru.display_name, ru.username) AS repost_display_name,
            (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS like_count,
            (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id) AS repost_count,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS reply_count,
            EXISTS(SELECT 1 FROM likes viewer_likes WHERE viewer_likes.post_id = p.id AND viewer_likes.user_id = ?) AS viewer_liked,
            EXISTS(SELECT 1 FROM reposts viewer_reposts WHERE viewer_reposts.post_id = p.id AND viewer_reposts.user_id = ?) AS viewer_reposted
        FROM posts p
        INNER JOIN users u ON u.id = p.user_id
        LEFT JOIN profiles pr ON pr.user_id = u.id
        LEFT JOIN posts rp ON rp.id = p.repost_of_id
        LEFT JOIN users ru ON ru.id = rp.user_id
        LEFT JOIN profiles rpr ON rpr.user_id = ru.id
        $joinFollowing
        $joinLikes
        WHERE " . implode(' AND ', $where) . '
        ORDER BY p.created_at DESC
        LIMIT 80';

    $stmt = db()->prepare($sql);
    $stmt->execute($params);
    return $stmt->fetchAll();
}

function fetch_post(int $viewerId, int $postId): ?array
{
    $posts = fetch_posts($viewerId);
    foreach ($posts as $post) {
        if ((int) $post['id'] === $postId) {
            return $post;
        }
    }

    $stmt = db()->prepare(
        'SELECT
            p.*,
            u.username,
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color,
            COALESCE(pr.bio, u.bio, "") AS bio,
            rp.content AS repost_content,
            ru.username AS repost_username,
            COALESCE(rpr.display_name, ru.display_name, ru.username) AS repost_display_name,
            (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS like_count,
            (SELECT COUNT(*) FROM reposts r WHERE r.post_id = p.id) AS repost_count,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS reply_count,
            EXISTS(SELECT 1 FROM likes viewer_likes WHERE viewer_likes.post_id = p.id AND viewer_likes.user_id = ?) AS viewer_liked,
            EXISTS(SELECT 1 FROM reposts viewer_reposts WHERE viewer_reposts.post_id = p.id AND viewer_reposts.user_id = ?) AS viewer_reposted
         FROM posts p
         INNER JOIN users u ON u.id = p.user_id
         LEFT JOIN profiles pr ON pr.user_id = u.id
         LEFT JOIN posts rp ON rp.id = p.repost_of_id
         LEFT JOIN users ru ON ru.id = rp.user_id
         LEFT JOIN profiles rpr ON rpr.user_id = ru.id
         WHERE p.id = ? AND p.deleted_at IS NULL
         LIMIT 1'
    );
    $stmt->execute([$viewerId, $viewerId, $postId]);
    return $stmt->fetch() ?: null;
}

function fetch_comments(int $postId): array
{
    $stmt = db()->prepare(
        'SELECT
            c.*,
            u.username,
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color
         FROM comments c
         INNER JOIN users u ON u.id = c.user_id
         LEFT JOIN profiles pr ON pr.user_id = u.id
         WHERE c.post_id = ?
         ORDER BY c.created_at ASC'
    );
    $stmt->execute([$postId]);
    return $stmt->fetchAll();
}

function fetch_user_by_username(string $username): ?array
{
    $stmt = db()->prepare(
        'SELECT
            u.*,
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.bio, u.bio, "") AS bio,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color,
            pr.updated_at AS profile_updated_at
         FROM users u
         LEFT JOIN profiles pr ON pr.user_id = u.id
         WHERE u.username = ?
         LIMIT 1'
    );
    $stmt->execute([$username]);
    return $stmt->fetch() ?: null;
}

function fetch_users_for_message(int $viewerId): array
{
    $stmt = db()->prepare(
        'SELECT u.id, u.username, COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
                COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color
         FROM users u
         LEFT JOIN profiles pr ON pr.user_id = u.id
         WHERE u.id <> ?
         ORDER BY display_name ASC'
    );
    $stmt->execute([$viewerId]);
    return $stmt->fetchAll();
}

function render_post(array $post, array $viewer): void
{
    $isOwnPost = (int) $post['user_id'] === (int) $viewer['id'];
    ?>
    <article class="post" data-post-id="<?= (int) $post['id'] ?>">
      <div class="post-avatar-col">
        <a class="avatar" style="--avatar: <?= h($post['avatar_color']) ?>" href="profile.php?u=<?= h($post['username']) ?>">
          <?= h(strtoupper(substr($post['display_name'], 0, 1))) ?>
        </a>
      </div>
      <div class="post-body">
        <header class="post-header">
          <div class="post-user-info">
            <a class="name" href="profile.php?u=<?= h($post['username']) ?>"><?= h($post['display_name']) ?></a>
            <a class="handle" href="profile.php?u=<?= h($post['username']) ?>">@<?= h($post['username']) ?></a>
            <a class="time" href="post.php?id=<?= (int) $post['id'] ?>"><?= h(time_ago($post['created_at'])) ?></a>
          </div>
          <button class="more-actions-btn">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor"><g><path d="M3 12c0-1.1.9-2 2-2s2 .9 2 2-.9 2-2 2-2-.9-2-2zm9 2c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm7 0c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"></path></g></svg>
          </button>
        </header>
        <?php if (!empty($post['repost_of_id'])): ?>
          <div class="repost-indicator">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16" fill="currentColor"><g><path d="M4.5 3.88l4.432 4.43-1.414 1.414L4.5 6.71V17H3V6.71L.082 9.624l-1.414-1.414L3.1 3.78c.39-.39 1.023-.39 1.4 0zM19 15.41V4h-1.5v11.41l-2.918-2.916-1.414 1.414 4.432 4.43c.39.39 1.023.39 1.414 0l4.432-4.43-1.414-1.414L19 15.41z"></path></g></svg>
            <span>Reposted from @<?= h($post['repost_username']) ?></span>
          </div>
        <?php endif; ?>
        <p class="post-copy"><?= nl2br(h($post['content'])) ?></p>
        <?php if (!empty($post['image_url'])): ?>
          <div class="post-media">
            <img class="post-image" src="<?= h($post['image_url']) ?>" alt="" loading="lazy">
          </div>
        <?php endif; ?>
        <footer class="post-actions">
          <a class="action-btn reply" href="post.php?id=<?= (int) $post['id'] ?>" title="Reply">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor"><g><path d="M1.751 10c0-4.42 3.584-8 8.005-8h4.243c4.42 0 8.005 3.58 8.005 8 0 4.41-3.585 8-8.005 8H11.25l-6.221 4.75c-.32.24-.715.31-1.096.19-.38-.13-.675-.45-.783-.85-.11-.39-.01-.81.259-1.12l1.378-1.63C2.882 15.75 1.751 12.99 1.751 10zm8.005-6c-3.317 0-6.005 2.69-6.005 6 0 2.29 1.303 4.45 3.395 5.48l.412.21-.295.34-1.077 1.28 4.29-3.27.35-.26h2.213c3.317 0 6.005-2.69 6.005-6s-2.688-6-6.005-6H9.756z"></path></g></svg>
            <span><?= (int) $post['reply_count'] ?: '' ?></span>
          </a>
          <form action="actions.php" method="post" class="ajax-action-form" data-action="repost">
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="toggle_repost">
            <input type="hidden" name="post_id" value="<?= (int) $post['id'] ?>">
            <button class="action-btn repost <?= $post['viewer_reposted'] ? 'active' : '' ?>" type="submit" title="Repost">
              <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor"><g><path d="M4.5 3.88l4.432 4.43-1.414 1.414L4.5 6.71V17H3V6.71L.082 9.624l-1.414-1.414L3.1 3.78c.39-.39 1.023-.39 1.4 0zM19 15.41V4h-1.5v11.41l-2.918-2.916-1.414 1.414 4.432 4.43c.39.39 1.023.39 1.414 0l4.432-4.43-1.414-1.414L19 15.41z"></path></g></svg>
              <span><?= (int) $post['repost_count'] ?: '' ?></span>
            </button>
          </form>
          <form action="actions.php" method="post" class="ajax-action-form" data-action="like">
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="toggle_like">
            <input type="hidden" name="post_id" value="<?= (int) $post['id'] ?>">
            <button class="action-btn like <?= $post['viewer_liked'] ? 'active' : '' ?>" type="submit" title="Like">
              <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor" class="icon-heart"><g><path d="M16.697 5.5c-1.222-.06-2.679.351-3.75 1.326-1.071-.975-2.528-1.387-3.75-1.326-2.737.134-4.561 2.184-4.417 4.392.152 2.274 1.639 4.453 3.581 6.301 3.04 2.899 6.562 4.521 7.738 5.026.269.117.574.117.843 0 1.176-.505 4.698-2.127 7.738-5.026 1.942-1.848 3.429-4.027 3.581-6.301.144-2.208-1.68-4.258-4.417-4.392zM12 18.232c-1.127-.514-4.321-2.072-6.915-4.544-1.848-1.761-3.08-3.64-3.21-5.58-.124-1.874 1.428-3.567 3.652-3.676.993-.049 2.128.324 2.921 1.054.496.457.828.981.996 1.488.169-.507.501-1.031.996-1.488.793-.73 1.928-1.103 2.921-1.054 2.224.109 3.776 1.802 3.652 3.676-.13 1.94-.13 1.94-3.21 5.58-2.594 2.472-5.788 4.03-6.915 4.544z"></path></g></svg>
              <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor" class="icon-heart-filled"><g><path d="M20.884 13.19c-1.351 1.264-4.383 3.723-8.147 5.345-.527.227-1.125.227-1.651 0-3.765-1.622-6.796-4.081-8.148-5.345-1.956-1.828-3.327-3.951-3.551-6.33-.314-3.33 2.144-6.337 5.507-6.5 1.543-.075 3.238.455 4.414 1.706 1.176-1.251 2.871-1.781 4.414-1.706 3.363.163 5.821 3.17 5.508 6.5-.224 2.379-1.595 4.502-3.551 6.33z"></path></g></svg>
              <span><?= (int) $post['like_count'] ?: '' ?></span>
            </button>
          </form>
          <?php if ($isOwnPost): ?>
            <form action="actions.php" method="post" onsubmit="return confirm('Delete this post?');">
              <?= csrf_field() ?>
              <input type="hidden" name="action" value="delete_post">
              <input type="hidden" name="post_id" value="<?= (int) $post['id'] ?>">
              <button class="action-btn delete" type="submit" title="Delete">
                <svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="currentColor"><g><path d="M16 6V4.5C16 3.12 14.88 2 13.5 2h-3C9.12 2 8 3.12 8 4.5V6H3v2h1.06l.81 12.12C4.97 21.39 6.09 22 7.31 22h9.38c1.22 0 2.34-.61 2.44-1.88L19.94 8H21V6h-5zM10 4.5c0-.28.22-.5.5-.5h3c.28 0 .5.22.5.5V6h-4V4.5zM17.13 20H6.87l-.75-12h11.76l-.75 12z"></path></g></svg>
              </button>
            </form>
          <?php endif; ?>
        </footer>
      </div>
    </article>
    <?php
}

function render_comment(array $comment): void
{
    ?>
    <article class="comment">
      <a class="avatar small" style="--avatar: <?= h($comment['avatar_color']) ?>" href="profile.php?u=<?= h($comment['username']) ?>">
        <?= h(strtoupper(substr($comment['display_name'], 0, 1))) ?>
      </a>
      <div>
        <header class="post-header">
          <a class="name" href="profile.php?u=<?= h($comment['username']) ?>"><?= h($comment['display_name']) ?></a>
          <a class="handle" href="profile.php?u=<?= h($comment['username']) ?>">@<?= h($comment['username']) ?></a>
          <span class="time"><?= h(time_ago($comment['created_at'])) ?></span>
        </header>
        <p class="post-copy"><?= nl2br(h($comment['comment'])) ?></p>
      </div>
    </article>
    <?php
}
function fetch_conversations(int $viewerId): array
{
    $stmt = db()->prepare(
        'SELECT 
            u.id, 
            u.username, 
            COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color,
            m.content as last_message,
            m.created_at as last_message_at,
            m.is_read
         FROM (
            SELECT 
                IF(sender_id = ?, receiver_id, sender_id) as contact_id,
                MAX(id) as max_id
            FROM messages
            WHERE sender_id = ? OR receiver_id = ?
            GROUP BY contact_id
         ) last_msgs
         INNER JOIN messages m ON m.id = last_msgs.max_id
         INNER JOIN users u ON u.id = last_msgs.contact_id
         LEFT JOIN profiles pr ON pr.user_id = u.id
         ORDER BY m.created_at DESC'
    );
    $stmt->execute([$viewerId, $viewerId, $viewerId]);
    return $stmt->fetchAll();
}

function fetch_messages_between(int $viewerId, int $otherId): array
{
    $stmt = db()->prepare(
        'SELECT 
            m.*,
            u.username as sender_username,
            COALESCE(pr.display_name, u.display_name, u.username) AS sender_name,
            COALESCE(pr.profile_pic, u.avatar_color, "#111111") AS avatar_color
         FROM messages m
         INNER JOIN users u ON u.id = m.sender_id
         LEFT JOIN profiles pr ON pr.user_id = u.id
         WHERE (m.sender_id = ? AND m.receiver_id = ?) 
            OR (m.sender_id = ? AND m.receiver_id = ?)
         ORDER BY m.created_at ASC
         LIMIT 100'
    );
    $stmt->execute([$viewerId, $otherId, $otherId, $viewerId]);
    return $stmt->fetchAll();
}

function mark_messages_as_read(int $viewerId, int $senderId): void
{
    $stmt = db()->prepare('UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND sender_id = ? AND is_read = 0');
    $stmt->execute([$viewerId, $senderId]);
}
