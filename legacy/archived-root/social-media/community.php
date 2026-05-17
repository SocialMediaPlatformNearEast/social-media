<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();
$metrics = app_metrics();
$recentMembers = db()->query(
    'SELECT
        u.username,
        COALESCE(pr.display_name, u.display_name, u.username) AS display_name,
        COALESCE(pr.profile_pic, u.theme_color, u.avatar_color, "#111111") AS avatar_color,
        COALESCE(pr.profile_photo_url, u.profile_photo_url, "") AS profile_photo_url,
        u.gender,
        u.created_at
     FROM users u
     LEFT JOIN profiles pr ON pr.user_id = u.id
     ORDER BY u.created_at DESC
     LIMIT 5'
)->fetchAll();

render_head('Community');
render_shell_start($viewer, 'community');
?>
<header class="page-header community-header">
  <div>
    <h1>Community</h1>
    <p>Live activity across LvL.</p>
  </div>
</header>

<section class="community-page">
  <div class="community-hero">
    <span class="panel-kicker">LvL network</span>
    <h2>Our Community</h2>
    <p><?= (int) $metrics['users'] ?> members are building conversations here.</p>
  </div>

  <div class="community-metrics-grid">
    <article><span>Users</span><strong><?= (int) $metrics['users'] ?></strong></article>
    <article><span>Profiles</span><strong><?= (int) $metrics['profiles'] ?></strong></article>
    <article><span>Posts</span><strong><?= (int) $metrics['posts'] ?></strong></article>
    <article><span>Comments</span><strong><?= (int) $metrics['comments'] ?></strong></article>
    <article><span>Likes</span><strong><?= (int) $metrics['likes'] ?></strong></article>
    <article><span>Follows</span><strong><?= (int) $metrics['follows'] ?></strong></article>
    <article><span>Messages</span><strong><?= (int) $metrics['messages'] ?></strong></article>
    <article><span>Notifications</span><strong><?= (int) $metrics['notifications'] ?></strong></article>
  </div>

  <section class="recent-members">
    <h3>Newest members</h3>
    <?php foreach ($recentMembers as $member): ?>
      <a class="recent-member" href="profile.php?u=<?= h($member['username']) ?>">
        <?php render_avatar($member, 'small'); ?>
        <span>
          <strong><?= h($member['display_name']) ?></strong>
          <small>@<?= h($member['username']) ?> joined <?= h(time_ago($member['created_at'])) ?></small>
        </span>
      </a>
    <?php endforeach; ?>
  </section>
</section>
<?php render_shell_end($viewer); ?>
