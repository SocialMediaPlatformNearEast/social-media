<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

$viewer = require_auth();

render_head('Edit Profile');
render_shell_start($viewer, 'settings');
?>
<div class="settings-container">
  <header class="page-header">
    <div class="header-content">
      <h1>Edit profile</h1>
      <p>Update how your account appears to others on XApp.</p>
    </div>
  </header>

  <div class="settings-content">
    <form class="premium-form" action="actions.php" method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="update_profile">
      
      <div class="form-section">
        <h3>Public Information</h3>
        <div class="form-grid">
          <label class="form-group">
            <span>First Name</span>
            <input name="first_name" maxlength="60" value="<?= h($viewer['first_name'] ?? '') ?>" placeholder="e.g. John" required>
          </label>
          <label class="form-group">
            <span>Last Name</span>
            <input name="last_name" maxlength="60" value="<?= h($viewer['last_name'] ?? '') ?>" placeholder="e.g. Doe" required>
          </label>
        </div>
        
        <label class="form-group" data-guide-target="username-area">
          <span>Username / Nickname</span>
          <div class="input-prefix-wrapper">
            <span class="input-prefix">@</span>
            <input name="nickname" maxlength="24" pattern="[a-z0-9_]{3,24}" value="<?= h($viewer['nickname'] ?? $viewer['username']) ?>" required>
          </div>
          <small>3-24 characters, lowercase, numbers, underscores.</small>
        </label>

        <label class="form-group" data-guide-target="bio-area">
          <span>Bio</span>
          <textarea name="bio" maxlength="180" rows="3" placeholder="Tell us about yourself..."><?= h($viewer['bio']) ?></textarea>
          <div class="char-counter">0 / 180</div>
        </label>
      </div>

      <div class="form-section">
        <h3>Details</h3>
        <div class="form-grid">
          <label class="form-group">
            <span>Location</span>
            <input name="location" maxlength="80" value="<?= h($viewer['location'] ?? '') ?>" placeholder="City, Country">
          </label>
          <label class="form-group">
            <span>Website</span>
            <input type="url" name="website" maxlength="255" value="<?= h($viewer['website'] ?? '') ?>" placeholder="https://yourwebsite.com">
          </label>
        </div>
        
        <div class="form-grid">
          <label class="form-group">
            <span>Gender</span>
            <select name="gender">
              <option value="Not specified" <?= ($viewer['gender'] ?? '') === 'Not specified' ? 'selected' : '' ?>>Not specified</option>
              <option value="Male" <?= ($viewer['gender'] ?? '') === 'Male' ? 'selected' : '' ?>>Male</option>
              <option value="Female" <?= ($viewer['gender'] ?? '') === 'Female' ? 'selected' : '' ?>>Female</option>
              <option value="Non-binary" <?= ($viewer['gender'] ?? '') === 'Non-binary' ? 'selected' : '' ?>>Non-binary</option>
              <option value="Other" <?= ($viewer['gender'] ?? '') === 'Other' ? 'selected' : '' ?>>Other</option>
            </select>
          </label>
          <label class="form-group">
            <span>Birthday</span>
            <input type="date" name="birthday" value="<?= h($viewer['birthday'] ?? '') ?>">
          </label>
        </div>
      </div>

      <div class="form-section">
        <h3>Appearance</h3>
        <label class="form-group" data-guide-target="profile-picture-area">
          <span>Profile Theme Color</span>
          <div class="color-picker-wrapper">
            <input type="color" name="profile_pic" value="<?= h($viewer['avatar_color'] ?? '#1d9bf0') ?>">
            <input type="text" class="hex-value" value="<?= h($viewer['avatar_color'] ?? '#1d9bf0') ?>" maxlength="7">
          </div>
        </label>
      </div>

      <div class="form-actions">
        <a href="profile.php" class="outline-button">Cancel</a>
        <button type="submit" class="primary-button">Save Changes</button>
      </div>
    </form>
  </div>
</div>

<script>
  // Sync color picker with text input
  const colorPicker = document.querySelector('input[type="color"]');
  const hexInput = document.querySelector('.hex-value');
  if (colorPicker && hexInput) {
    colorPicker.addEventListener('input', (e) => {
      hexInput.value = e.target.value.toUpperCase();
    });
    hexInput.addEventListener('input', (e) => {
      if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
        colorPicker.value = e.target.value;
      }
    });
  }
</script>
<?php render_shell_end($viewer); ?>
