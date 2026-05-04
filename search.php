<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();
$query = trim((string) ($_GET['q'] ?? ''));
$tab = (string) ($_GET['f'] ?? 'top');

if ($query !== '') {
    $historyStmt = db()->prepare('INSERT INTO search_history (user_id, keyword) VALUES (?, ?)');
    $historyStmt->execute([(int) $viewer['id'], $query]);
}

$posts = [];
$users = [];

if ($query !== '') {
    if ($tab === 'people') {
        $stmt = db()->prepare(
            'SELECT u.*, 
                    COALESCE(pr.display_name, u.display_name, u.username) AS display_name, 
                    COALESCE(pr.profile_pic, u.theme_color, u.avatar_color, "#111111") AS avatar_color,
                    COALESCE(pr.profile_photo_url, u.profile_photo_url, "") AS profile_photo_url,
                    COALESCE(pr.bio, u.bio, "") AS bio,
                    EXISTS(SELECT 1 FROM follows WHERE follower_id = ? AND following_id = u.id) AS is_following
             FROM users u
             LEFT JOIN profiles pr ON pr.user_id = u.id
             WHERE u.username LIKE ? OR COALESCE(pr.display_name, u.display_name) LIKE ?
             ORDER BY u.created_at DESC
             LIMIT 40'
        );
        $term = '%' . $query . '%';
        $stmt->execute([(int) $viewer['id'], $term, $term]);
        $users = $stmt->fetchAll();
    } else {
        $posts = fetch_posts((int) $viewer['id'], 'all', null, $query);
    }
}

render_head('Search');
render_shell_start($viewer, 'search');
?>
<div class="search-page-container">
  <header class="page-header search-header">
    <div class="search-input-wrapper">
      <form action="search.php" method="get" class="search-page-form">
        <svg viewBox="0 0 24 24" aria-hidden="true" class="search-icon"><g><path d="M10.25 3.75c-3.59 0-6.5 2.91-6.5 6.5s2.91 6.5 6.5 6.5c1.795 0 3.419-.726 4.596-1.904 1.178-1.177 1.904-2.801 1.904-4.596 0-3.59-2.91-6.5-6.5-6.5zm-8.5 6.5c0-4.694 3.806-8.5 8.5-8.5s8.5 3.806 8.5 8.5c0 1.986-.682 3.815-1.824 5.262l4.781 4.781-1.414 1.414-4.781-4.781c-1.447 1.142-3.276 1.824-5.262 1.824-4.694 0-8.5-3.806-8.5-8.5z"></path></g></svg>
        <input type="search" name="q" value="<?= h($query) ?>" placeholder="Search XApp" autofocus>
      </form>
    </div>
    <div class="segmented search-tabs">
      <a class="<?= $tab === 'top' ? 'active' : '' ?>" href="search.php?q=<?= urlencode($query) ?>&f=top">Top</a>
      <a class="<?= $tab === 'latest' ? 'active' : '' ?>" href="search.php?q=<?= urlencode($query) ?>&f=latest">Latest</a>
      <a class="<?= $tab === 'people' ? 'active' : '' ?>" href="search.php?q=<?= urlencode($query) ?>&f=people">People</a>
    </div>
  </header>

  <?php if ($query === ''): ?>
    <div class="search-empty-state">
      <h2>Search for anything</h2>
      <p>Find people, posts, and more on XApp.</p>
    </div>
  <?php else: ?>
    <section class="search-results">
      <?php if ($tab === 'people'): ?>
        <div class="people-results">
          <?php if (!$users): ?>
            <div class="empty-state">
              <p>No results for "<?= h($query) ?>"</p>
            </div>
          <?php endif; ?>
          <?php foreach ($users as $user): ?>
            <div class="user-result-card">
              <?php render_avatar($user, '', 'profile.php?u=' . urlencode((string) $user['username'])); ?>
              <div class="user-result-info">
                <div class="user-result-header">
                  <div class="user-names">
                    <a href="profile.php?u=<?= h($user['username']) ?>"><strong><?= h($user['display_name']) ?></strong></a>
                    <span>@<?= h($user['username']) ?></span>
                  </div>
                  <?php if ((int)$user['id'] !== (int)$viewer['id']): ?>
                    <form action="actions.php" method="post">
                      <?= csrf_field() ?>
                      <input type="hidden" name="action" value="toggle_follow">
                      <input type="hidden" name="target_id" value="<?= (int) $user['id'] ?>">
                      <button class="outline-button <?= $user['is_following'] ? 'active' : '' ?>" type="submit">
                        <?= $user['is_following'] ? 'Following' : 'Follow' ?>
                      </button>
                    </form>
                  <?php endif; ?>
                </div>
                <p class="user-result-bio"><?= h($user['bio']) ?></p>
              </div>
            </div>
          <?php endforeach; ?>
        </div>
      <?php else: ?>
        <div class="post-results feed">
          <?php if (!$posts): ?>
            <div class="empty-state">
              <p>No results for "<?= h($query) ?>"</p>
            </div>
          <?php endif; ?>
          <?php foreach ($posts as $post): ?>
            <?php render_post($post, $viewer); ?>
          <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </section>
  <?php endif; ?>
</div>
<?php render_shell_end($viewer); ?>
