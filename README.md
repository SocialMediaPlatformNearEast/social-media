# XApp

XApp is a PHP/MySQL X-style social app built for XAMPP and Visual Studio Code.

## Features

- Register and log in with PHP sessions
- Registration asks for first name, last name, nickname, email, age, and password
- Passwords stored with `password_hash`
- CSRF protection on all write actions
- Create posts up to 280 characters
- Optional image URL on posts
- Comment threads backed by a separate `comments` table
- Likes and reposts
- Follow and unfollow users
- Friend request records
- Direct messages
- Notifications for likes, reposts, comments, follows, friend requests, and messages
- User profile pages and editable profile details
- Search posts and people with `search_history` logging
- JSON API in `api.php`
- SQL totals in the right sidebar

## XAMPP Setup

1. Copy this folder into XAMPP's web root:

   - macOS: `/Applications/XAMPP/xamppfiles/htdocs/xapp`
   - Windows: `C:\xampp\htdocs\xapp`

2. Start Apache and MySQL from the XAMPP control panel.

3. Open phpMyAdmin:

   `http://localhost/phpmyadmin`

4. Import [schema.sql](/Applications/XAMPP/xamppfiles/htdocs/xapp/schema.sql).

   This creates the `xapp` database and these tables:

   - `users`
   - `profiles`
   - `posts`
   - `comments`
   - `search_history`
   - `follows`
   - `likes`
   - `reposts`
   - `messages`
   - `notifications`
   - `friendships`

5. Check database credentials in [config.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/config.php).

   XAMPP defaults are already configured:

   ```php
   const DB_HOST = '127.0.0.1';
   const DB_NAME = 'xapp';
   const DB_USER = 'root';
   const DB_PASS = '';
   ```

6. Open the app:

   `http://localhost/xapp`

## Demo Login

After importing `schema.sql`, you can log in with:

- Username: `demo`
- Password: `password123`

You can also create a new account from the Register tab.

## Main Files

- [index.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/index.php): home feed and composer
- [auth.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/auth.php): login and registration UI
- [actions.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/actions.php): form actions for auth, posts, comments, likes, reposts, follows, friend requests, messages, notifications, profile updates, and deletes
- [api.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/api.php): JSON API for app data
- [profile.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/profile.php): public profile page
- [post.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/post.php): post and comments page
- [search.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/search.php): search page
- [messages.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/messages.php): direct messages page
- [notifications.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/notifications.php): notifications page
- [settings.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/settings.php): edit profile page
- [functions.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/functions.php): shared helpers and SQL queries
- [schema.sql](/Applications/XAMPP/xamppfiles/htdocs/xapp/schema.sql): MySQL database schema

## SQL Details

The relational model is:

- `users.id` is the auto-increment primary key.
- `users` stores first name, last name, nickname, email, password hash, age, account credentials, demographics, and relationships.
- `profiles.user_id` references `users.id` for display name, bio, and profile color.
- `posts.user_id` references `users.id`.
- `posts.repost_of_id` references `posts.id` for repost feed copies.
- `comments.post_id` references `posts.id`; `comments.user_id` references `users.id`.
- `search_history.user_id` references `users.id`.
- `follows.follower_id` and `follows.following_id` reference `users.id`.
- `likes.user_id` references `users.id`; `likes.post_id` references `posts.id`.
- `reposts.user_id` references `users.id`; `reposts.post_id` references `posts.id`.
- `messages.sender_id` and `messages.receiver_id` reference `users.id`.
- `notifications.user_id` and `notifications.actor_id` reference `users.id`; optional `post_id` and `message_id` point to the related record.
- `friendships.user_1`, `friendships.user_2`, and `friendships.action_user_id` reference `users.id`.

All foreign keys use InnoDB and cascade deletes where appropriate.

## API

The API file follows the same beginner flow as the transcript: connect to MySQL, fetch rows, add rows into an array, and print the response as JSON with a `Content-Type: application/json` header.

Base URL:

`http://localhost/xapp/api.php`

Examples:

```text
GET http://localhost/xapp/api.php
GET http://localhost/xapp/api.php?resource=users
GET http://localhost/xapp/api.php?resource=posts
GET http://localhost/xapp/api.php?resource=posts&id=1
GET http://localhost/xapp/api.php?resource=comments
```

Create a user with JSON:

```bash
curl -X POST http://localhost/xapp/api.php?resource=users \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Jane","last_name":"Doe","nickname":"janedoe","email":"jane@example.com","age":22,"password":"password123"}'
```

Create a post:

```bash
curl -X POST http://localhost/xapp/api.php?resource=posts \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"content":"Hello from the API"}'
```

Create a comment:

```bash
curl -X POST http://localhost/xapp/api.php?resource=comments \
  -H "Content-Type: application/json" \
  -d '{"post_id":1,"user_id":1,"comment":"API comment"}'
```

For safety, the API never returns `password_hash`.
