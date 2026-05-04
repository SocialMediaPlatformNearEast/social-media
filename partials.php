<?php
declare(strict_types=1);

require_once __DIR__ . '/functions.php';

function render_head(string $title): void
{
    ?>
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title><?= h($title) ?> - <?= h(APP_NAME) ?></title>
      <link rel="stylesheet" href="styles.css">
      <link rel="stylesheet" href="gender.css">
      <script src="script.js" defer></script>
    </head>
    <body>
    <?php
}

function render_flash(): void
{
    $flash = flash();
    if (!$flash) {
        return;
    }
    ?>
    <div class="flash <?= h($flash['type']) ?>" role="status"><?= h($flash['message']) ?></div>
    <?php
}

function render_xp_toasts(): void
{
    $toasts = take_xp_toasts();
    if (!$toasts) {
        return;
    }
    ?>
    <script type="application/json" id="xp-toast-data"><?= json_encode($toasts, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?></script>
    <?php
}

function render_shell_start(array $viewer, string $active = 'home'): void
{
    $stats = user_stats((int) $viewer['id']);
    ?>
    <div class="app-shell">
      <aside class="left-rail">
        <div class="sidebar-top">
          <button id="sidebar-toggle" class="sidebar-toggle-btn" aria-label="Toggle Sidebar">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="24" height="24" fill="currentColor"><g><path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z"></path></g></svg>
          </button>
          <a class="brand" href="index.php" aria-label="<?= h(APP_NAME) ?> home">
            <span class="brand-mark">X</span>
            <span class="brand-text"><?= h(APP_NAME) ?></span>
          </a>
        </div>
        <nav class="nav-list" aria-label="Primary">
          <a class="<?= $active === 'home' ? 'active' : '' ?>" href="index.php"><span>H</span> <span class="nav-label">Home</span></a>
          <a class="<?= $active === 'search' ? 'active' : '' ?>" href="search.php"><span>S</span> <span class="nav-label">Search</span></a>
          <a class="<?= $active === 'messages' ? 'active' : '' ?>" href="messages.php"><span>M</span> <span class="nav-label">Messages</span></a>
          <a class="<?= $active === 'notifications' ? 'active' : '' ?>" href="notifications.php"><span>N</span> <span class="nav-label">Alerts</span></a>
          <a class="<?= $active === 'profile' ? 'active' : '' ?>" href="profile.php?u=<?= h($viewer['username']) ?>"><span>P</span> <span class="nav-label">Profile</span></a>
        </nav>
        <a class="compose-link" href="index.php?compose=1">Post</a>
        <a class="mini-profile" href="profile.php?u=<?= h($viewer['username']) ?>">
          <?php render_avatar($viewer, 'small'); ?>
          <div>
            <strong><?= h($viewer['display_name']) ?></strong>
            <span>@<?= h($viewer['username']) ?> <?php render_level_badge($viewer); ?></span>
          </div>
        </a>
        <a class="logout-link" href="logout.php">Log out</a>
      </aside>
      <main class="timeline">
        <?php render_flash(); ?>
        <?php render_xp_toasts(); ?>
    <?php
}

function render_support_chat_widget(): void
{
    ?>
    <section class="support-chat" aria-label="Live support chat">
      <button class="support-chat-toggle" type="button" aria-label="Open support chat" aria-expanded="false">
        <span aria-hidden="true">?</span>
      </button>
      <div class="support-chat-window" aria-live="polite" hidden>
        <header class="support-chat-header">
          <div>
            <strong>Support chat</strong>
            <span>Quick answers</span>
          </div>
          <button class="support-chat-close" type="button" aria-label="Close support chat">x</button>
        </header>
        <div class="support-chat-body">
          <div class="support-message bot">
            Hi. Pick a question and I will show you the steps.
          </div>
          <div class="support-question-list" aria-label="Common support questions"></div>
          <div class="support-answer-list" aria-label="Support chat answers"></div>
        </div>
        <footer class="support-chat-footer">
          <button class="support-contact-button" type="button">Still need help?</button>
        </footer>
      </div>
    </section>
    <div class="guide-tooltip" role="status" hidden></div>
    <?php
}

function render_shell_end(array $viewer): void
{
    $stats = user_stats((int) $viewer['id']);
    $metrics = app_metrics();
    ?>
      </main>
      <aside class="right-rail">
        <form class="search-box" action="search.php" method="get" data-guide-target="search-area">
          <input type="search" name="q" placeholder="Search posts and people" value="<?= h($_GET['q'] ?? '') ?>">
        </form>
        <section class="side-panel" data-guide-target="account-area">
          <h2>Your account</h2>
          <div class="metric-row"><span>Posts</span><strong><?= (int) $stats['posts'] ?></strong></div>
          <div class="metric-row"><span>Comments</span><strong><?= (int) $stats['comments'] ?></strong></div>
          <div class="metric-row"><span>Friends</span><strong><?= (int) $stats['friends'] ?></strong></div>
          <div class="metric-row"><span>Following</span><strong><?= (int) $stats['following'] ?></strong></div>
          <div class="metric-row"><span>Followers</span><strong><?= (int) $stats['followers'] ?></strong></div>
        </section>
        <section class="side-panel">
          <h2>App totals</h2>
          <div class="metric-row"><span>Users</span><strong><?= (int) $metrics['users'] ?></strong></div>
          <div class="metric-row"><span>Profiles</span><strong><?= (int) $metrics['profiles'] ?></strong></div>
          <div class="metric-row"><span>Posts</span><strong><?= (int) $metrics['posts'] ?></strong></div>
          <div class="metric-row"><span>Comments</span><strong><?= (int) $metrics['comments'] ?></strong></div>
          <div class="metric-row"><span>Likes</span><strong><?= (int) $metrics['likes'] ?></strong></div>
          <div class="metric-row"><span>Follows</span><strong><?= (int) $metrics['follows'] ?></strong></div>
          <div class="metric-row"><span>Messages</span><strong><?= (int) $metrics['messages'] ?></strong></div>
          <div class="metric-row"><span>Notifications</span><strong><?= (int) $metrics['notifications'] ?></strong></div>
        </section>
      </aside>
    </div>
    <?php render_support_chat_widget(); ?>
    </body>
    </html>
    <?php
}

function render_composer(array $viewer): void
{
    ?>
    <form id="composer" class="composer premium-composer" action="actions.php" method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="create_post">
      <div class="composer-avatar-column">
        <?php render_avatar($viewer, '', 'profile.php?u=' . urlencode((string) $viewer['username'])); ?>
      </div>
      <div class="composer-main">
        <textarea name="content" maxlength="280" placeholder="What's happening?" required></textarea>
        <div class="composer-options" data-guide-target="photo-upload-area">
          <input type="url" name="image_url" placeholder="Image URL (optional)" class="image-url-input">
        </div>
        <div class="composer-footer">
          <div class="composer-tools">
            <!-- Space for more tools like emoji, image upload etc -->
          </div>
          <div class="composer-actions">
            <span class="char-count">280</span>
            <button type="submit" class="post-submit-btn">Post</button>
          </div>
        </div>
      </div>
    </form>
    <?php
}

function render_comment_form(array $viewer, int $postId): void
{
    ?>
    <form id="composer" class="composer" action="actions.php" method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="add_comment">
      <input type="hidden" name="post_id" value="<?= $postId ?>">
      <?php render_avatar($viewer); ?>
      <div class="composer-fields">
        <textarea name="comment" maxlength="280" rows="4" placeholder="Write a comment" required></textarea>
        <div class="composer-actions">
          <span class="char-count">280</span>
          <button type="submit">Comment</button>
        </div>
      </div>
    </form>
    <?php
}
