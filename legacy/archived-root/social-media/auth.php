<?php
declare(strict_types=1);

require_once __DIR__ . '/partials.php';

if (current_user()) {
    redirect('index.php');
}

render_head('Login');
?>
<main class="auth-layout">
  <?php render_flash(); ?>
  <?php render_xp_toasts(); ?>
  <section class="auth-hero">
    <div class="brand-lockup">
      <span class="brand-mark large">LvL</span>
      <span><?= h(APP_NAME) ?></span>
    </div>
    <h1>Run your own social app on XAMPP.</h1>
    <p>PHP sessions, MySQL authentication, hashed passwords, profiles, follows, friendships, comments, messages, notifications, likes, reposts, and SQL reporting are wired in.</p>
    <div class="auth-metrics">
      <span>PDO MySQL</span>
      <span>CSRF forms</span>
      <span>Password hashing</span>
    </div>
  </section>
  <section class="auth-panel">
    <div class="auth-tabs" role="tablist">
      <button class="active" type="button" data-auth-tab="login">Login</button>
      <button type="button" data-auth-tab="register">Register</button>
    </div>
    <form class="auth-form active" data-auth-panel="login" action="actions.php" method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="login">
      <label>
        Nickname or email
        <input name="identity" autocomplete="username" required>
      </label>
      <label data-guide-target="password-reset-area">
        Password
        <input type="password" name="password" autocomplete="current-password" required>
      </label>
      <button type="submit">Login</button>
    </form>
    <form class="auth-form" data-auth-panel="register" action="actions.php" method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="register">
      <label>
        First name
        <input name="first_name" maxlength="60" autocomplete="given-name" required>
      </label>
      <label>
        Last name
        <input name="last_name" maxlength="60" autocomplete="family-name" required>
      </label>
      <label>
        Nickname
        <input name="nickname" pattern="[a-z0-9_]{3,24}" autocomplete="username" required>
      </label>
      <label>
        Email
        <input type="email" name="email" autocomplete="email" required>
      </label>
      <label>
        Age
        <input type="number" name="age" min="13" max="120" required>
      </label>
      <fieldset class="gender-field">
        <legend>Gender</legend>
        <div class="gender-options">
          <?php foreach (GENDER_PROFILE_DEFAULTS as $genderName => $defaults): ?>
            <label class="gender-option">
              <input
                type="radio"
                name="gender"
                value="<?= h($genderName) ?>"
                data-avatar-url="<?= h($defaults['profile_photo_url']) ?>"
                data-theme-color="<?= h($defaults['theme_color']) ?>"
                required
              >
              <span><?= h($genderName) ?></span>
            </label>
          <?php endforeach; ?>
        </div>
        <div class="gender-preview" data-gender-preview hidden>
          <img data-gender-avatar src="" alt="">
          <span data-gender-swatch></span>
        </div>
      </fieldset>
      <label>
        Birthday
        <input type="date" name="birthday">
      </label>
      <label>
        Password
        <input type="password" name="password" minlength="8" autocomplete="new-password" required>
      </label>
      <button type="submit">Create account</button>
    </form>
  </section>
</main>
<?php render_support_chat_widget(); ?>
</body>
</html>
