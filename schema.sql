CREATE DATABASE IF NOT EXISTS xapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE xapp;

CREATE TABLE IF NOT EXISTS users (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  first_name VARCHAR(60) NOT NULL DEFAULT '',
  last_name VARCHAR(60) NOT NULL DEFAULT '',
  nickname VARCHAR(24) NOT NULL UNIQUE,
  username VARCHAR(24) NOT NULL UNIQUE,
  display_name VARCHAR(80) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  gender VARCHAR(40) NULL,
  age INT UNSIGNED NULL,
  birthday DATE NULL,
  bio VARCHAR(180) DEFAULT '',
  location VARCHAR(80) DEFAULT '',
  website VARCHAR(255) DEFAULT '',
  avatar_color CHAR(7) NOT NULL DEFAULT '#111111',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(60) NOT NULL DEFAULT '' AFTER id;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(60) NOT NULL DEFAULT '' AFTER first_name;
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(24) NULL AFTER last_name;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(40) NULL AFTER password_hash;
ALTER TABLE users ADD COLUMN IF NOT EXISTS age INT UNSIGNED NULL AFTER gender;
ALTER TABLE users ADD COLUMN IF NOT EXISTS birthday DATE NULL AFTER age;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(80) NOT NULL DEFAULT '' AFTER username;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio VARCHAR(180) DEFAULT '' AFTER birthday;
ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(80) DEFAULT '' AFTER bio;
ALTER TABLE users ADD COLUMN IF NOT EXISTS website VARCHAR(255) DEFAULT '' AFTER location;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_color CHAR(7) NOT NULL DEFAULT '#111111' AFTER website;
UPDATE users SET nickname = username WHERE nickname IS NULL OR nickname = '';
ALTER TABLE users MODIFY nickname VARCHAR(24) NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_nickname ON users (nickname);

CREATE TABLE IF NOT EXISTS profiles (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL UNIQUE,
  display_name VARCHAR(80) NOT NULL,
  bio VARCHAR(180) DEFAULT '',
  profile_pic CHAR(7) NOT NULL DEFAULT '#111111',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS posts (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  parent_id INT UNSIGNED NULL,
  repost_of_id INT UNSIGNED NULL,
  content VARCHAR(280) NOT NULL,
  image_url VARCHAR(600) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_posts_parent FOREIGN KEY (parent_id) REFERENCES posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_posts_repost FOREIGN KEY (repost_of_id) REFERENCES posts(id) ON DELETE SET NULL,
  INDEX idx_posts_created (created_at),
  INDEX idx_posts_parent (parent_id),
  FULLTEXT INDEX ft_posts_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comments (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  post_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  comment VARCHAR(280) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_comments_post (post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS search_history (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  searched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_search_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_search_history_user (user_id, searched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS follows (
  id INT UNSIGNED AUTO_INCREMENT UNIQUE,
  follower_id INT UNSIGNED NOT NULL,
  following_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (follower_id, following_id),
  CONSTRAINT fk_follows_follower FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_follows_following FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS likes (
  id INT UNSIGNED AUTO_INCREMENT UNIQUE,
  user_id INT UNSIGNED NOT NULL,
  post_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, post_id),
  CONSTRAINT fk_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reposts (
  user_id INT UNSIGNED NOT NULL,
  post_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, post_id),
  CONSTRAINT fk_reposts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_reposts_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS messages (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  sender_id INT UNSIGNED NOT NULL,
  receiver_id INT UNSIGNED NOT NULL,
  content VARCHAR(1000) NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_messages_receiver FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_messages_pair (sender_id, receiver_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNSIGNED NOT NULL,
  actor_id INT UNSIGNED NOT NULL,
  type VARCHAR(40) NOT NULL,
  post_id INT UNSIGNED NULL,
  message_id INT UNSIGNED NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_notifications_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_notifications_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE SET NULL,
  CONSTRAINT fk_notifications_message FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
  INDEX idx_notifications_user (user_id, is_read, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS friendships (
  id INT UNSIGNED AUTO_INCREMENT UNIQUE,
  user_1 INT UNSIGNED NOT NULL,
  user_2 INT UNSIGNED NOT NULL,
  action_user_id INT UNSIGNED NOT NULL,
  status ENUM('pending', 'accepted', 'blocked') NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_1, user_2),
  CONSTRAINT fk_friendships_user_1 FOREIGN KEY (user_1) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_friendships_user_2 FOREIGN KEY (user_2) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_friendships_action FOREIGN KEY (action_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO users (first_name, last_name, nickname, username, display_name, email, password_hash, gender, age, birthday, bio, avatar_color)
VALUES
  ('Demo', 'User', 'demo', 'demo', 'Demo User', 'demo@example.com', '$2y$10$lSbMGgQsoi/J02bDB40NM.sq4JEe9CTurh8jrOdzCZg1CfmTB5MdW', 'Not specified', 21, NULL, 'Local XApp demo account. Password: password123', '#111111')
ON DUPLICATE KEY UPDATE
  first_name = IF(first_name = '', VALUES(first_name), first_name),
  last_name = IF(last_name = '', VALUES(last_name), last_name),
  nickname = IF(nickname IS NULL OR nickname = '', VALUES(nickname), nickname);

INSERT INTO profiles (user_id, display_name, bio, profile_pic)
SELECT id, COALESCE(NULLIF(display_name, ''), username), COALESCE(bio, ''), COALESCE(avatar_color, '#111111')
FROM users
ON DUPLICATE KEY UPDATE
  display_name = VALUES(display_name),
  bio = VALUES(bio),
  profile_pic = VALUES(profile_pic);

INSERT INTO posts (user_id, content)
SELECT id, 'Welcome to XApp. Import schema.sql, log in as demo / password123, then create your own account.'
FROM users
WHERE username = 'demo'
  AND NOT EXISTS (
    SELECT 1 FROM posts
    WHERE content = 'Welcome to XApp. Import schema.sql, log in as demo / password123, then create your own account.'
  );
