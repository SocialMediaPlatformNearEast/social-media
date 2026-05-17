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
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
      <meta name="theme-color" content="#000000">
      <meta name="mobile-web-app-capable" content="yes">
      <meta name="apple-mobile-web-app-capable" content="yes">
      <meta name="apple-mobile-web-app-status-bar-style" content="black">
      <title><?= h($title) ?> - <?= h(APP_NAME) ?></title>
      <link rel="manifest" href="manifest.json">
      <link rel="icon" href="assets/default-male-avatar.svg" type="image/svg+xml">
      <link rel="apple-touch-icon" href="assets/default-male-avatar.svg">
      <link rel="stylesheet" href="styles.css?v=20260509-5">
      <link rel="stylesheet" href="gender.css?v=20260509-5">
      <script src="script.js?v=20260509-5" defer></script>
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
    $GLOBALS['shell_active'] = $active;
    $badges = nav_badges((int) $viewer['id']);
    $timelineClass = 'timeline timeline-' . preg_replace('/[^a-z0-9_-]/i', '', $active);
    ?>
    <div class="app-shell">
      <div class="left-rail-wrapper">
        <aside class="left-rail">
        <div class="sidebar-top desktop-only">
          <button id="sidebar-toggle" class="sidebar-toggle-btn" aria-label="Toggle Sidebar">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="24" height="24" fill="currentColor"><g><path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z"></path></g></svg>
          </button>
        </div>
        <nav class="nav-list" aria-label="Primary">
          <a class="<?= $active === 'home' ? 'active' : '' ?>" href="index.php">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3V10.5Zm2 1V19h2v-6h10v6h2v-7.5l-7-5.83-7 5.83Z"/></svg>
            </span>
            <span class="nav-label">Home</span>
          </a>
          <a class="<?= $active === 'search' ? 'active' : '' ?>" href="search.php">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M10.25 4a6.25 6.25 0 1 0 0 12.5 6.25 6.25 0 0 0 0-12.5ZM2 10.25a8.25 8.25 0 1 1 14.59 5.28l4.44 4.44-1.41 1.41-4.44-4.44A8.25 8.25 0 0 1 2 10.25Z"/></svg>
            </span>
            <span class="nav-label">Search</span>
          </a>
          <a class="<?= $active === 'messages' ? 'active' : '' ?>" href="messages.php">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M4 4h16v12H7.8L4 19.35V4Zm2 2v8.93L7.04 14H18V6H6Z"/></svg>
              <?php if ((int) $badges['messages'] > 0): ?><span class="nav-badge"><?= min(99, (int) $badges['messages']) ?></span><?php endif; ?>
            </span>
            <span class="nav-label">Messages</span>
          </a>
          <a class="<?= $active === 'notifications' ? 'active' : '' ?>" href="notifications.php">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 22a2.75 2.75 0 0 0 2.58-1.8H9.42A2.75 2.75 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Zm-2 .2.8.8H6.2l.8-.8V11a5 5 0 1 1 10 0v5.2Z"/></svg>
              <?php if ((int) $badges['notifications'] > 0): ?><span class="nav-badge"><?= min(99, (int) $badges['notifications']) ?></span><?php endif; ?>
            </span>
            <span class="nav-label">Alerts</span>
          </a>
          <a class="<?= $active === 'community' ? 'active' : '' ?>" href="community.php">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M7.5 11a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Zm9 0a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7ZM2 20c.38-3.35 2.63-6 5.5-6s5.12 2.65 5.5 6H2Zm9.75 0c.24-1.86 1.06-3.48 2.25-4.6.72-.88 1.57-1.4 2.5-1.4 2.87 0 5.12 2.65 5.5 6H11.75Z"/></svg>
            </span>
            <span class="nav-label">Community</span>
          </a>
          <a class="<?= $active === 'profile' ? 'active' : '' ?>" href="profile.php?u=<?= h($viewer['username']) ?>">
            <span class="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-4.42 0-8 2.24-8 5v2h16v-2c0-2.76-3.58-5-8-5Z"/></svg>
            </span>
            <span class="nav-label">Profile</span>
          </a>
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
      </div>
      <main class="<?= h($timelineClass) ?>">
        <div class="mobile-header">
          <button class="mobile-sidebar-toggle" aria-label="Toggle Sidebar">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z"/></svg>
          </button>
          <span class="mobile-brand">LvL</span>
        </div>
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
          <button class="support-back-button" type="button" hidden>Back to questions</button>
          <button class="support-contact-button" type="button">Still need help?</button>
        </footer>
      </div>
    </section>
    <div class="guide-tooltip" role="status" hidden></div>
    <?php
}

function render_shell_end(array $viewer, ?bool $showHighlights = null): void
{
    if ($showHighlights === null) {
        $active = (string) ($GLOBALS['shell_active'] ?? '');
        $showHighlights = $active !== 'messages';
    }
    ?>
      </main>
      <div class="right-rail-wrapper">
        <?php if ($showHighlights): ?>
          <?php render_community_highlights_panel($viewer); ?>
        <?php endif; ?>
      </div>
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
        <div class="composer-footer">
          <div class="composer-tools">
            <!-- Space for more tools like emoji, image upload etc -->
          </div>
          <div class="composer-actions">
            <span class="char-count">280 left</span>
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
          <span class="char-count">280 left</span>
          <button type="submit">Comment</button>
        </div>
      </div>
    </form>
    <?php
}
