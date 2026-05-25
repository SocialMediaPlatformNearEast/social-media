<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();

$stmt = db()->prepare(
    'SELECT
        n.*,
        actor.username AS actor_username,
        COALESCE(ap.display_name, actor.display_name, actor.username) AS actor_name,
        p.content AS post_content,
        f.status AS friendship_status,
        f.action_user_id AS friendship_action_user_id
     FROM notifications n
     INNER JOIN users actor ON actor.id = n.actor_id
     LEFT JOIN profiles ap ON ap.user_id = actor.id
     LEFT JOIN posts p ON p.id = n.post_id
     LEFT JOIN friendships f ON f.user_1 = LEAST(n.user_id, n.actor_id) AND f.user_2 = GREATEST(n.user_id, n.actor_id)
     WHERE n.user_id = ?
     ORDER BY n.created_at DESC
     LIMIT 100'
);
$stmt->execute([(int) $viewer['id']]);
$notifications = $stmt->fetchAll();

$labels = [
    'like' => 'liked your post',
    'repost' => 'reposted your post',
    'comment' => 'commented on your post',
    'follow' => 'followed you',
    'friend_request' => 'sent you a friend request',
    'friend_accept' => 'accepted your friend request',
    'message' => 'sent you a message',
];

render_head('Notifications');
render_shell_start($viewer, 'notifications');
?>
<header class="page-header">
  <div>
    <h1>Notifications</h1>
    <p>Alerts generated from likes, reposts, comments, follows, friend requests, and messages.</p>
  </div>
  <form action="actions.php" method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="mark_notifications_read">
    <button class="outline-button" type="submit">Mark read</button>
  </form>
</header>
<section class="feed" data-guide-target="notifications-area">
  <?php if (!$notifications): ?>
    <div class="empty-state">
      <h2>No notifications yet</h2>
      <p>When people interact with you or your posts, you'll see it here.</p>
    </div>
  <?php endif; ?>
  <?php foreach ($notifications as $notification): ?>
    <div class="notification-item <?= (int) $notification['is_read'] === 0 ? 'unread' : '' ?>">
      <div class="notification-icon type-<?= h($notification['type']) ?>">
        <?php if ($notification['type'] === 'like'): ?>❤️<?php endif; ?>
        <?php if ($notification['type'] === 'follow'): ?>👤<?php endif; ?>
        <?php if ($notification['type'] === 'repost'): ?>🔁<?php endif; ?>
        <?php if ($notification['type'] === 'comment'): ?>💬<?php endif; ?>
        <?php if ($notification['type'] === 'message'): ?>✉️<?php endif; ?>
        <?php if ($notification['type'] === 'friend_request'): ?>🤝<?php endif; ?>
        <?php if ($notification['type'] === 'friend_accept'): ?>✓<?php endif; ?>
      </div>
      <div class="notification-body">
        <div class="notification-header">
          <a href="profile.php?u=<?= h($notification['actor_username']) ?>" class="actor-link">
            <strong><?= h($notification['actor_name']) ?></strong>
          </a>
          <span class="notification-text"><?= h($labels[$notification['type']] ?? $notification['type']) ?></span>
          <span class="time">· <?= h(time_ago($notification['created_at'])) ?></span>
        </div>
        <?php if (!empty($notification['post_id'])): ?>
          <a href="post.php?id=<?= (int) $notification['post_id'] ?>" class="notification-preview">
            <?= h(mb_strimwidth((string) $notification['post_content'], 0, 140, '...')) ?>
          </a>
        <?php elseif ($notification['type'] === 'message'): ?>
          <a href="messages.php?u=<?= h($notification['actor_username']) ?>" class="notification-action">View message</a>
        <?php elseif ($notification['type'] === 'friend_request' && ($notification['friendship_status'] ?? '') === 'pending' && (int) ($notification['friendship_action_user_id'] ?? 0) !== (int) $viewer['id']): ?>
          <div class="notification-actions">
            <form action="actions.php" method="post">
              <?= csrf_field() ?>
              <input type="hidden" name="action" value="respond_friend_request">
              <input type="hidden" name="target_id" value="<?= (int) $notification['actor_id'] ?>">
              <input type="hidden" name="decision" value="accept">
              <button type="submit" class="primary-button small">Accept</button>
            </form>
            <form action="actions.php" method="post">
              <?= csrf_field() ?>
              <input type="hidden" name="action" value="respond_friend_request">
              <input type="hidden" name="target_id" value="<?= (int) $notification['actor_id'] ?>">
              <input type="hidden" name="decision" value="decline">
              <button type="submit" class="outline-button small">Decline</button>
            </form>
          </div>
        <?php endif; ?>
      </div>
    </div>
  <?php endforeach; ?>
</section>
<?php render_shell_end($viewer); ?>
