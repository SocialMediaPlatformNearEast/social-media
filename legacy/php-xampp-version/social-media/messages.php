<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();
$targetUsername = (string) ($_GET['u'] ?? '');
$targetUser = $targetUsername ? fetch_user_by_username($targetUsername) : null;

$conversations = fetch_conversations((int) $viewer['id']);
$messages = [];
if ($targetUser) {
    $messages = fetch_messages_between((int) $viewer['id'], (int) $targetUser['id']);
    mark_messages_as_read((int) $viewer['id'], (int) $targetUser['id']);
}

render_head('Messages');
render_shell_start($viewer, 'messages');
?>
<div class="messages-container">
  <aside class="conversations-sidebar">
    <header class="sidebar-header">
      <h2>Messages</h2>
      <a href="#new-chat" class="new-message-btn" title="New Message">＋</a>
    </header>
    <div class="conversations-list">
      <?php if (!$conversations): ?>
        <div class="empty-conversations">
          <p>Nothing yet, maybe message someone first?</p>
        </div>
      <?php endif; ?>
      <?php foreach ($conversations as $conv): ?>
        <a href="messages.php?u=<?= h($conv['username']) ?>" class="conversation-item <?= $targetUsername === $conv['username'] ? 'active' : '' ?> <?= !$conv['is_read'] && $conv['id'] !== $viewer['id'] ? 'unread' : '' ?>">
          <?php render_avatar($conv); ?>
          <div class="conv-info">
            <div class="conv-header">
              <strong><?= h($conv['display_name']) ?></strong>
              <span class="time"><?= h(time_ago($conv['last_message_at'])) ?></span>
            </div>
            <p class="last-message"><?= h($conv['last_message']) ?></p>
          </div>
        </a>
      <?php endforeach; ?>
    </div>
  </aside>

  <main class="chat-window">
    <?php if ($targetUser): ?>
      <header class="chat-header" style="--chat-color: <?= h(profile_theme_color($targetUser)) ?>">
        <a href="profile.php?u=<?= h($targetUser['username']) ?>" class="chat-user-info">
          <?php render_avatar($targetUser, 'small'); ?>
          <div>
            <strong><?= h($targetUser['display_name']) ?></strong>
            <p>@<?= h($targetUser['username']) ?></p>
          </div>
        </a>
      </header>
      
      <div class="messages-feed" id="messages-feed">
        <?php if (!$messages): ?>
          <div class="chat-empty-state">
            <?php render_avatar($targetUser, 'large'); ?>
            <h3><?= h($targetUser['display_name']) ?></h3>
            <p>@<?= h($targetUser['username']) ?></p>
            <p class="hint">This is the beginning of your direct message history with @<?= h($targetUser['username']) ?>.</p>
          </div>
        <?php endif; ?>
        
        <?php foreach ($messages as $msg): ?>
          <div class="message-bubble-wrapper <?= (int) $msg['sender_id'] === (int) $viewer['id'] ? 'own' : '' ?>">
            <div class="message-bubble" title="<?= h($msg['created_at']) ?>">
              <?= nl2br(h($msg['content'])) ?>
            </div>
            <span class="message-time"><?= h(date('H:i', strtotime($msg['created_at']))) ?></span>
          </div>
        <?php endforeach; ?>
      </div>

      <footer class="chat-footer">
        <form action="actions.php" method="post" class="chat-input-form">
          <?= csrf_field() ?>
          <input type="hidden" name="action" value="send_message">
          <input type="hidden" name="receiver_id" value="<?= (int) $targetUser['id'] ?>">
          <input type="hidden" name="redirect" value="messages.php?u=<?= h($targetUser['username']) ?>">
          <textarea name="content" placeholder="Start a new message" required maxlength="1000" rows="1"></textarea>
          <button type="submit" class="send-btn">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20" fill="currentColor"><g><path d="M2.504 21.866l.526-2.108C3.04 19.719 4 15.823 4 12s-.96-7.719-.97-7.757l-.526-2.109L22.247 12 2.504 21.866zM5.981 13c-.072 1.962-.34 3.833-.583 5.183L17.584 12 5.398 5.817c.243 1.35.511 3.221.583 5.183H12v2H5.981z"></path></g></svg>
          </button>
        </form>
      </footer>
    <?php else: ?>
      <div class="chat-unselected">
        <h2>Select a message</h2>
        <p>Choose from your existing conversations, or start a new one from the list below.</p>
        
        <div class="new-chat-section" id="new-chat">
          <h3>Start a new conversation</h3>
          <div class="user-selection-list">
            <?php 
            $allUsers = fetch_users_for_message((int) $viewer['id']);
            foreach ($allUsers as $u): 
            ?>
              <a href="messages.php?u=<?= h($u['username']) ?>" class="user-select-item">
                <?php render_avatar($u, 'small'); ?>
                <div class="user-select-info">
                  <strong><?= h($u['display_name']) ?></strong>
                  <span>@<?= h($u['username']) ?></span>
                </div>
                <span class="select-arrow">→</span>
              </a>
            <?php endforeach; ?>
          </div>
        </div>
      </div>
    <?php endif; ?>
  </main>
</div>

<script>
  // Auto-scroll to bottom of messages
  const feed = document.getElementById('messages-feed');
  if (feed) {
    feed.scrollTop = feed.scrollHeight;
  }
  
  // Auto-resize textarea
  const tx = document.querySelector('.chat-input-form textarea');
  if (tx) {
    tx.addEventListener("input", OnInput, false);
  }

  function OnInput() {
    this.style.height = "auto";
    this.style.height = (this.scrollHeight) + "px";
  }
</script>
<?php render_shell_end($viewer); ?>
