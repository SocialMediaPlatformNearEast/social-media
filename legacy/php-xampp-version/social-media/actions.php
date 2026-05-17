<?php
declare(strict_types=1);

require_once __DIR__ . '/functions.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    redirect('index.php');
}

require_valid_csrf();

$action = $_POST['action'] ?? '';

try {
    ensure_profile_defaults_schema();

    if ($action === 'register') {
        $firstName = trim((string) ($_POST['first_name'] ?? ''));
        $lastName = trim((string) ($_POST['last_name'] ?? ''));
        $nickname = strtolower(trim((string) ($_POST['nickname'] ?? '')));
        $username = $nickname;
        $displayName = trim($firstName . ' ' . $lastName);
        $email = strtolower(trim((string) ($_POST['email'] ?? '')));
        $password = (string) ($_POST['password'] ?? '');
        $gender = trim((string) ($_POST['gender'] ?? ''));
        $profileDefaults = profile_defaults_for_gender($gender);
        $birthday = trim((string) ($_POST['birthday'] ?? ''));
        $ageInput = trim((string) ($_POST['age'] ?? ''));
        $age = $ageInput !== '' ? (int) $ageInput : ($birthday !== '' ? max(0, (int) floor((time() - strtotime($birthday)) / 31557600)) : null);

        if ($firstName === '' || $lastName === '' || $nickname === '' || $email === '' || strlen($password) < 8) {
            flash('Use first name, last name, nickname, email, age, and an 8+ character password.', 'error');
            redirect('auth.php');
        }

        if ($profileDefaults === null) {
            flash('Please choose Male or Female for gender.', 'error');
            redirect('auth.php');
        }

        if (!preg_match('/^[a-z0-9_]{3,24}$/', $nickname)) {
            flash('Nicknames must be 3-24 characters: lowercase letters, numbers, and underscores only.', 'error');
            redirect('auth.php');
        }

        if ($age === null || $age < 13 || $age > 120) {
            flash('Age must be a number between 13 and 120.', 'error');
            redirect('auth.php');
        }

        $profilePhotoUrl = $profileDefaults['profile_photo_url'];
        $themeColor = $profileDefaults['theme_color'];
        $avatarColor = $themeColor;
        $stmt = db()->prepare(
            'INSERT INTO users (first_name, last_name, nickname, username, display_name, email, password_hash, gender, profile_photo_url, theme_color, age, birthday, avatar_color)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        );
        $stmt->execute([
            $firstName,
            $lastName,
            $nickname,
            $username,
            $displayName,
            $email,
            password_hash($password, PASSWORD_DEFAULT),
            $gender,
            $profilePhotoUrl,
            $themeColor,
            $age,
            $birthday ?: null,
            $avatarColor,
        ]);

        $userId = (int) db()->lastInsertId();
        ensure_profile($userId, $displayName, $avatarColor, $profilePhotoUrl);

        $_SESSION['user_id'] = $userId;
        session_regenerate_id(true);
        flash('Account created. Welcome in.', 'success');
        redirect('index.php');
    }

    if ($action === 'login') {
        $identity = strtolower(trim((string) ($_POST['identity'] ?? '')));
        $password = (string) ($_POST['password'] ?? '');
        $attempts = $_SESSION['login_attempts'] ?? ['count' => 0, 'last' => 0];

        if (($attempts['count'] ?? 0) >= 5 && time() - (int) ($attempts['last'] ?? 0) < 60) {
            flash('Too many login attempts. Please wait a minute and try again.', 'error');
            redirect('auth.php');
        }

        $stmt = db()->prepare('SELECT * FROM users WHERE email = ? OR username = ? OR nickname = ? LIMIT 1');
        $stmt->execute([$identity, $identity, $identity]);
        $user = $stmt->fetch();

        if (!$user || !password_verify($password, $user['password_hash'])) {
            $_SESSION['login_attempts'] = [
                'count' => (int) ($attempts['count'] ?? 0) + 1,
                'last' => time(),
            ];
            flash('Invalid username/email or password.', 'error');
            redirect('auth.php');
        }

        unset($_SESSION['login_attempts']);
        ensure_profile(
            (int) $user['id'],
            $user['display_name'] ?: $user['username'],
            $user['avatar_color'] ?: ($user['theme_color'] ?? '#111111'),
            $user['profile_photo_url'] ?? ''
        );
        $_SESSION['user_id'] = (int) $user['id'];
        session_regenerate_id(true);
        award_xp((int) $user['id'], 'daily_login', 5, date('Y-m-d'));
        flash('Logged in successfully.', 'success');
        redirect('index.php');
    }

    $viewer = require_auth();

    if ($action === 'create_post') {
        $content = trim((string) ($_POST['content'] ?? ''));

        if ($content === '' || mb_strlen($content) > 280) {
            flash('Posts must be between 1 and 280 characters.', 'error');
            redirect_back();
        }

        $stmt = db()->prepare('INSERT INTO posts (user_id, content) VALUES (?, ?)');
        $stmt->execute([(int) $viewer['id'], $content]);
        $contentKey = sha1(mb_strtolower(trim(preg_replace('/\s+/', ' ', $content))));
        award_xp((int) $viewer['id'], 'post_created', 10, $contentKey);
        flash('Post published.', 'success');
        redirect_back();
    }

    if ($action === 'add_comment') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $comment = trim((string) ($_POST['comment'] ?? ''));

        if ($comment === '' || mb_strlen($comment) > 280) {
            flash('Comments must be between 1 and 280 characters.', 'error');
            redirect_back();
        }

        $stmt = db()->prepare('INSERT INTO comments (post_id, user_id, comment) VALUES (?, ?, ?)');
        $stmt->execute([$postId, (int) $viewer['id'], $comment]);
        $commentId = (int) db()->lastInsertId();
        award_xp((int) $viewer['id'], 'comment_created', 6, (string) $commentId);

        $ownerId = post_owner_id($postId);
        if ($ownerId !== null) {
            notify_user($ownerId, (int) $viewer['id'], 'comment', $postId);
            if ($ownerId !== (int) $viewer['id']) {
                award_xp($ownerId, 'comment_received', 4, (string) $commentId);
            }
        }

        flash('Comment posted.', 'success');
        redirect('post.php?id=' . $postId);
    }

    if ($action === 'toggle_like') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $isAjax = ($_POST['ajax'] ?? '') === '1';
        
        $stmt = db()->prepare('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?');
        $stmt->execute([(int) $viewer['id'], $postId]);
        $liked = false;

        if ($stmt->fetch()) {
            $delete = db()->prepare('DELETE FROM likes WHERE user_id = ? AND post_id = ?');
            $delete->execute([(int) $viewer['id'], $postId]);
            $liked = false;
        } else {
            $insert = db()->prepare('INSERT IGNORE INTO likes (user_id, post_id) VALUES (?, ?)');
            $insert->execute([(int) $viewer['id'], $postId]);
            $ownerId = post_owner_id($postId);
            if ($ownerId !== null) {
                notify_user($ownerId, (int) $viewer['id'], 'like', $postId);
                if ($ownerId !== (int) $viewer['id']) {
                    award_xp((int) $viewer['id'], 'like_given', 1, (string) $postId);
                    award_xp($ownerId, 'like_received', 2, $postId . ':' . (int) $viewer['id']);
                }
            }
            $liked = true;
        }

        if ($isAjax) {
            $countStmt = db()->prepare('SELECT COUNT(*) FROM likes WHERE post_id = ?');
            $countStmt->execute([$postId]);
            $count = (int) $countStmt->fetchColumn();
            
            header('Content-Type: application/json');
            echo json_encode(['success' => true, 'liked' => $liked, 'count' => $count, 'xp_toasts' => take_xp_toasts()]);
            exit;
        }

        redirect_back();
    }

    if ($action === 'toggle_repost') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $isAjax = ($_POST['ajax'] ?? '') === '1';
        
        $stmt = db()->prepare('SELECT 1 FROM reposts WHERE user_id = ? AND post_id = ?');
        $stmt->execute([(int) $viewer['id'], $postId]);
        $reposted = false;

        if ($stmt->fetch()) {
            $delete = db()->prepare('DELETE FROM reposts WHERE user_id = ? AND post_id = ?');
            $delete->execute([(int) $viewer['id'], $postId]);
            $deletePost = db()->prepare('UPDATE posts SET deleted_at = NOW() WHERE user_id = ? AND repost_of_id = ?');
            $deletePost->execute([(int) $viewer['id'], $postId]);
            $reposted = false;
        } else {
            $insert = db()->prepare('INSERT IGNORE INTO reposts (user_id, post_id) VALUES (?, ?)');
            $insert->execute([(int) $viewer['id'], $postId]);
            $copy = db()->prepare('INSERT INTO posts (user_id, content, repost_of_id) VALUES (?, ?, ?)');
            $copy->execute([(int) $viewer['id'], 'Reposted', $postId]);
            $ownerId = post_owner_id($postId);
            if ($ownerId !== null) {
                notify_user($ownerId, (int) $viewer['id'], 'repost', $postId);
            }
            $reposted = true;
        }

        if ($isAjax) {
            $countStmt = db()->prepare('SELECT COUNT(*) FROM reposts WHERE post_id = ?');
            $countStmt->execute([$postId]);
            $count = (int) $countStmt->fetchColumn();
            
            header('Content-Type: application/json');
            echo json_encode(['success' => true, 'reposted' => $reposted, 'count' => $count]);
            exit;
        }

        redirect_back();
    }

    if ($action === 'toggle_follow') {
        $targetId = (int) ($_POST['target_id'] ?? 0);
        $isAjax = ($_POST['ajax'] ?? '') === '1';

        if ($targetId <= 0 || $targetId === (int) $viewer['id']) {
            if ($isAjax) {
                header('Content-Type: application/json');
                echo json_encode(['success' => false, 'error' => 'Invalid target.']);
                exit;
            }
            redirect_back();
        }

        $stmt = db()->prepare('SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?');
        $stmt->execute([(int) $viewer['id'], $targetId]);
        $following = false;

        if ($stmt->fetch()) {
            $delete = db()->prepare('DELETE FROM follows WHERE follower_id = ? AND following_id = ?');
            $delete->execute([(int) $viewer['id'], $targetId]);
            $following = false;
        } else {
            $insert = db()->prepare('INSERT IGNORE INTO follows (follower_id, following_id) VALUES (?, ?)');
            $insert->execute([(int) $viewer['id'], $targetId]);
            notify_user($targetId, (int) $viewer['id'], 'follow');
            $following = true;
        }

        if ($isAjax) {
            header('Content-Type: application/json');
            echo json_encode(['success' => true, 'following' => $following]);
            exit;
        }

        redirect_back();
    }

    if ($action === 'request_friend') {
        $targetId = (int) ($_POST['target_id'] ?? 0);
        if ($targetId === (int) $viewer['id']) {
            redirect_back();
        }

        $first = min((int) $viewer['id'], $targetId);
        $second = max((int) $viewer['id'], $targetId);
        $stmt = db()->prepare('INSERT INTO friendships (user_1, user_2, action_user_id, status) VALUES (?, ?, ?, "pending") ON DUPLICATE KEY UPDATE action_user_id = VALUES(action_user_id), status = IF(status = "accepted", status, "pending")');
        $stmt->execute([$first, $second, (int) $viewer['id']]);
        notify_user($targetId, (int) $viewer['id'], 'friend_request');
        flash('Friend request sent.', 'success');
        redirect_back();
    }

    if ($action === 'respond_friend_request') {
        $targetId = (int) ($_POST['target_id'] ?? 0);
        $decision = (string) ($_POST['decision'] ?? '');
        $first = min((int) $viewer['id'], $targetId);
        $second = max((int) $viewer['id'], $targetId);

        $stmt = db()->prepare('SELECT action_user_id, status FROM friendships WHERE user_1 = ? AND user_2 = ? LIMIT 1');
        $stmt->execute([$first, $second]);
        $friendship = $stmt->fetch();

        if (!$friendship || $targetId <= 0 || (int) $friendship['action_user_id'] === (int) $viewer['id'] || $friendship['status'] !== 'pending') {
            flash('That friend request is no longer available.', 'error');
            redirect('notifications.php');
        }

        if ($decision === 'accept') {
            $update = db()->prepare('UPDATE friendships SET status = "accepted", action_user_id = ? WHERE user_1 = ? AND user_2 = ?');
            $update->execute([(int) $viewer['id'], $first, $second]);
            notify_user($targetId, (int) $viewer['id'], 'friend_accept');
            flash('Friend request accepted.', 'success');
        } else {
            $delete = db()->prepare('DELETE FROM friendships WHERE user_1 = ? AND user_2 = ?');
            $delete->execute([$first, $second]);
            flash('Friend request declined.', 'success');
        }

        redirect('notifications.php');
    }

    if ($action === 'update_profile') {
        $firstName = trim((string) ($_POST['first_name'] ?? ''));
        $lastName = trim((string) ($_POST['last_name'] ?? ''));
        $nickname = strtolower(trim((string) ($_POST['nickname'] ?? '')));
        $displayName = trim($firstName . ' ' . $lastName);
        $bio = trim((string) ($_POST['bio'] ?? ''));
        $profilePic = trim((string) ($_POST['profile_pic'] ?? ''));
        $gender = trim((string) ($_POST['gender'] ?? ''));
        $birthday = trim((string) ($_POST['birthday'] ?? ''));
        $ageInput = trim((string) ($_POST['age'] ?? ''));
        $age = $ageInput !== '' ? (int) $ageInput : ($birthday !== '' ? max(0, (int) floor((time() - strtotime($birthday)) / 31557600)) : null);

        $location = trim((string) ($_POST['location'] ?? ''));
        $website = trim((string) ($_POST['website'] ?? ''));

        if ($firstName === '' || $lastName === '' || $nickname === '' || mb_strlen($displayName) > 80 || mb_strlen($bio) > 180) {
            flash('First name, last name, and nickname are required. Bio must stay under 180 characters.', 'error');
            redirect('settings.php');
        }

        if (!preg_match('/^[a-z0-9_]{3,24}$/', $nickname)) {
            flash('Nicknames must be 3-24 characters: lowercase letters, numbers, and underscores only.', 'error');
            redirect('settings.php');
        }

        if ($age === null || $age < 13 || $age > 120) {
            flash('Age must be a number between 13 and 120.', 'error');
            redirect('settings.php');
        }

        if (profile_defaults_for_gender($gender) === null) {
            flash('Please choose Male or Female for gender.', 'error');
            redirect('settings.php');
        }

        if ($profilePic !== '' && !preg_match('/^#[0-9a-fA-F]{6}$/', $profilePic)) {
            flash('Profile color must be a hex color like #1d9bf0.', 'error');
            redirect('settings.php');
        }

        $color = $profilePic ?: ($viewer['theme_color'] ?? $viewer['avatar_color'] ?? '#111111');
        $stmt = db()->prepare(
            'INSERT INTO profiles (user_id, display_name, bio, profile_pic, profile_photo_url)
             VALUES (?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), bio = VALUES(bio), profile_pic = VALUES(profile_pic), updated_at = CURRENT_TIMESTAMP'
        );
        $stmt->execute([(int) $viewer['id'], $displayName, $bio, $color, $viewer['profile_photo_url'] ?? null]);

        $userStmt = db()->prepare('UPDATE users SET first_name = ?, last_name = ?, nickname = ?, username = ?, display_name = ?, bio = ?, avatar_color = ?, theme_color = ?, gender = ?, age = ?, birthday = ?, location = ?, website = ? WHERE id = ?');
        $userStmt->execute([$firstName, $lastName, $nickname, $nickname, $displayName, $bio, $color, $color, $gender, $age, $birthday ?: null, $location, $website, (int) $viewer['id']]);

        $profileData = [
            'first_name' => $firstName,
            'last_name' => $lastName,
            'nickname' => $nickname,
            'bio' => $bio,
            'avatar_color' => $color,
        ];
        if (is_profile_complete($profileData)) {
            $xpResult = award_xp((int) $viewer['id'], 'profile_completed', 30, 'complete_profile');
            if (($xpResult['awarded'] ?? 0) > 0) {
                $completeStmt = db()->prepare('UPDATE users SET profile_completed_at = COALESCE(profile_completed_at, NOW()) WHERE id = ?');
                $completeStmt->execute([(int) $viewer['id']]);
            }
        }

        flash('Profile updated.', 'success');
        redirect('profile.php?u=' . urlencode($nickname));
    }

    if ($action === 'send_message') {
        $receiverId = (int) ($_POST['receiver_id'] ?? 0);
        $content = trim((string) ($_POST['content'] ?? ''));
        $redirect = internal_redirect_target((string) ($_POST['redirect'] ?? 'messages.php'), 'messages.php');
        $isAjax = ($_POST['ajax'] ?? '') === '1';

        if ($receiverId <= 0 || $receiverId === (int) $viewer['id'] || $content === '' || mb_strlen($content) > 1000) {
            if ($isAjax) {
                header('Content-Type: application/json');
                echo json_encode(['success' => false, 'error' => 'Choose a recipient and write a message under 1000 characters.']);
                exit;
            }
            flash('Choose a recipient and write a message under 1000 characters.', 'error');
            redirect($redirect);
        }

        $stmt = db()->prepare('INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)');
        $stmt->execute([(int) $viewer['id'], $receiverId, $content]);
        $messageId = (int) db()->lastInsertId();
        
        notify_user($receiverId, (int) $viewer['id'], 'message', null, $messageId);
        
        if ($isAjax) {
            header('Content-Type: application/json');
            echo json_encode([
                'success' => true,
                'message' => [
                    'id' => $messageId,
                    'content' => $content,
                    'created_at' => date('Y-m-d H:i:s'),
                    'sender_id' => $viewer['id']
                ]
            ]);
            exit;
        }
        
        redirect($redirect);
    }

    if ($action === 'mark_notifications_read') {
        $stmt = db()->prepare('UPDATE notifications SET is_read = 1 WHERE user_id = ?');
        $stmt->execute([(int) $viewer['id']]);
        redirect('notifications.php');
    }

    if ($action === 'delete_post') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('UPDATE posts SET deleted_at = NOW() WHERE id = ? AND user_id = ?');
        $stmt->execute([$postId, (int) $viewer['id']]);
        flash('Post deleted.', 'success');
        redirect_back();
    }
} catch (PDOException $exception) {
    if ($exception->getCode() === '23000') {
        flash('That record already exists or conflicts with existing data.', 'error');
    } else {
        error_log('LvL database error: ' . $exception->getMessage());
        flash('Something went wrong while saving. Please try again.', 'error');
    }
    redirect_back();
}

flash('Unknown action.', 'error');
redirect('index.php');
// 
