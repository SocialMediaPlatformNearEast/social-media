<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = current_user();
if (!$viewer) {
    redirect('auth.php');
}

$mode = ($_GET['feed'] ?? 'all') === 'following' ? 'following' : 'all';
$posts = fetch_posts((int) $viewer['id'], $mode);

render_head('Home');
render_shell_start($viewer, 'home');
?>
<header class="page-header home-header">
  <div class="header-top">
    <h1>Home</h1>
  </div>
  <div class="segmented feed-tabs">
    <a class="<?= $mode === 'all' ? 'active' : '' ?>" href="index.php?feed=all">
      <span>For you</span>
    </a>
    <a class="<?= $mode === 'following' ? 'active' : '' ?>" href="index.php?feed=following">
      <span>Following</span>
    </a>
  </div>
</header>
<?php render_composer($viewer); ?>
<section class="feed" aria-label="Timeline">
  <?php if (!$posts): ?>
    <div class="empty-state">
      <h2>No posts yet</h2>
      <p>Create the first post or follow another user to populate this feed.</p>
    </div>
  <?php endif; ?>
  <?php foreach ($posts as $post): ?>
    <?php render_post($post, $viewer); ?>
  <?php endforeach; ?>
</section>
<?php render_shell_end($viewer); ?>
