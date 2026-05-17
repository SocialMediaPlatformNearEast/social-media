<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();
$username = (string) ($_GET['u'] ?? $viewer['username']);
$profile = fetch_user_by_username($username);
$mode = (string) ($_GET['m'] ?? 'posts');

if (!$profile) {
    render_head('Profile not found');
    render_shell_start($viewer, 'profile');
    ?>
    <div class="empty-state">
      <h1>Profile not found</h1>
      <p>No user exists with that username.</p>
    </div>
    <?php
    render_shell_end($viewer);
    exit;
}

$stats = user_stats((int) $profile['id']);
$isOwnProfile = (int) $profile['id'] === (int) $viewer['id'];
$followStmt = db()->prepare('SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?');
$followStmt->execute([(int) $viewer['id'], (int) $profile['id']]);
$isFollowing = (bool) $followStmt->fetch();

$friendStmt = db()->prepare('SELECT status, action_user_id FROM friendships WHERE user_1 = LEAST(?, ?) AND user_2 = GREATEST(?, ?) LIMIT 1');
$friendStmt->execute([(int) $viewer['id'], (int) $profile['id'], (int) $viewer['id'], (int) $profile['id']]);
$friendship = $friendStmt->fetch() ?: null;
$friendStatus = $friendship['status'] ?? null;
$friendActionUserId = (int) ($friendship['action_user_id'] ?? 0);

$posts = fetch_posts((int) $viewer['id'], $mode === 'liked' ? 'liked' : 'all', (int) $profile['id']);

render_head($profile['display_name']);
render_shell_start($viewer, 'profile');
?>
<section class="profile-header">
  <div class="profile-banner" data-guide-target="cover-photo-area" style="background-color: <?= h($profile['avatar_color']) ?>; opacity: 0.3;"></div>
  <div class="profile-info-container">
    <div class="profile-top-row">
      <div data-guide-target="profile-picture-area">
        <?php render_avatar($profile, 'profile-avatar-large'); ?>
      </div>
      <div class="profile-actions">
        <?php if ($isOwnProfile): ?>
          <a class="outline-button" href="settings.php">Edit profile</a>
        <?php else: ?>
          <form action="actions.php" method="post" class="ajax-action-form" data-action="follow">
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="toggle_follow">
            <input type="hidden" name="target_id" value="<?= (int) $profile['id'] ?>">
            <button class="outline-button <?= $isFollowing ? 'active' : '' ?>" type="submit"><?= $isFollowing ? 'Following' : 'Follow' ?></button>
          </form>
          <a class="outline-button" href="messages.php?u=<?= h($profile['username']) ?>">Message</a>
          <form action="actions.php" method="post">
            <?= csrf_field() ?>
            <?php if ($friendStatus === 'pending' && $friendActionUserId !== (int) $viewer['id']): ?>
              <input type="hidden" name="action" value="respond_friend_request">
              <input type="hidden" name="decision" value="accept">
            <?php else: ?>
              <input type="hidden" name="action" value="request_friend">
            <?php endif; ?>
            <input type="hidden" name="target_id" value="<?= (int) $profile['id'] ?>">
            <button class="outline-button <?= $friendStatus ? 'active' : '' ?>" type="submit">
              <?= $friendStatus === 'accepted' ? 'Friend' : ($friendStatus === 'pending' ? ($friendActionUserId === (int) $viewer['id'] ? 'Requested' : 'Accept friend') : 'Add friend') ?>
            </button>
          </form>
        <?php endif; ?>
      </div>
    </div>
    
    <div class="profile-names">
      <h1><?= h($profile['display_name']) ?> <?php render_level_badge($profile); ?></h1>
      <p class="handle" data-guide-target="username-area">@<?= h($profile['username']) ?></p>
    </div>

    <?php if (!empty($profile['bio'])): ?>
      <p class="bio" data-guide-target="bio-area"><?= nl2br(h($profile['bio'])) ?></p>
    <?php else: ?>
      <p class="bio empty-bio" data-guide-target="bio-area">No bio yet.</p>
    <?php endif; ?>

    <div class="profile-meta-grid">
      <?php if (!empty($profile['location'])): ?>
        <span title="Location">📍 <?= h($profile['location']) ?></span>
      <?php endif; ?>
      <?php if (!empty($profile['website'])): ?>
        <span title="Website">🔗 <a href="<?= h($profile['website']) ?>" target="_blank" rel="nofollow noreferrer"><?= h(parse_url($profile['website'], PHP_URL_HOST) ?: $profile['website']) ?></a></span>
      <?php endif; ?>
      <?php if (!empty($profile['gender'])): ?>
        <span title="Gender">👤 <?= h($profile['gender']) ?></span>
      <?php endif; ?>
      <span>📅 Joined <?= h(date('M Y', strtotime($profile['created_at']))) ?></span>
    </div>

    <div class="profile-stats">
      <span><strong><?= (int) $stats['following'] ?></strong> Following</span>
      <span><strong><?= (int) $stats['followers'] ?></strong> Followers</span>
      <span><strong><?= (int) $stats['friends'] ?></strong> Friends</span>
    </div>
    <section class="profile-account-card" aria-label="Profile activity stats">
      <div>
        <span>Posts</span>
        <strong><?= (int) $stats['posts'] ?></strong>
      </div>
      <div>
        <span>Comments</span>
        <strong><?= (int) $stats['comments'] ?></strong>
      </div>
      <div>
        <span>Friends</span>
        <strong><?= (int) $stats['friends'] ?></strong>
      </div>
      <div>
        <span>Following</span>
        <strong><?= (int) $stats['following'] ?></strong>
      </div>
      <div>
        <span>Followers</span>
        <strong><?= (int) $stats['followers'] ?></strong>
      </div>
    </section>
    <?php render_profile_xp_panel($profile); ?>
  </div>

  <div class="segmented">
    <a href="profile.php?u=<?= h($profile['username']) ?>&m=posts" class="<?= $mode === 'posts' ? 'active' : '' ?>">Posts</a>
    <a href="profile.php?u=<?= h($profile['username']) ?>&m=liked" class="<?= $mode === 'liked' ? 'active' : '' ?>">Likes</a>
  </div>
</section>

<section class="feed">
  <?php if (!$posts): ?>
    <div class="empty-state">
      <h2>No <?= $mode === 'liked' ? 'liked posts' : 'posts' ?></h2>
      <p><?= $mode === 'liked' ? 'This user hasn\'t liked any posts yet.' : 'This profile has not posted yet.' ?></p>
    </div>
  <?php endif; ?>
  <?php foreach ($posts as $post): ?>
    <?php render_post($post, $viewer); ?>
  <?php endforeach; ?>
</section>
<?php render_shell_end($viewer); ?>
