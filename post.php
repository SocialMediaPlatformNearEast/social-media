<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();
$postId = (int) ($_GET['id'] ?? 0);
$post = fetch_post((int) $viewer['id'], $postId);

render_head('Post');
render_shell_start($viewer, 'home');

if (!$post): ?>
  <div class="empty-state">
    <h1>Post not found</h1>
    <p>The post was deleted or never existed.</p>
  </div>
<?php else:
    $comments = fetch_comments((int) $post['id']);
    ?>
    <header class="page-header compact">
      <div>
        <h1>Post</h1>
        <p>Read the conversation and add your comment.</p>
      </div>
    </header>
    <section class="feed thread-root">
      <?php render_post($post, $viewer); ?>
    </section>
    <?php render_comment_form($viewer, (int) $post['id']); ?>
    <section class="feed">
      <?php if (!$comments): ?>
        <div class="empty-state">
          <h2>No comments yet</h2>
          <p>Start the conversation with a comment.</p>
        </div>
      <?php endif; ?>
      <?php foreach ($comments as $comment): ?>
        <?php render_comment($comment); ?>
      <?php endforeach; ?>
    </section>
<?php endif; ?>
<?php render_shell_end($viewer); ?>
