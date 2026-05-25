# LvL

LvL is a PHP/MySQL social app built for XAMPP. It includes accounts, profiles, posts, comments, likes, reposts, follows, friend requests, direct messages, notifications, search, and lightweight XP/level progress.

## Features

- Register and log in with PHP sessions
- Passwords stored with `password_hash`
- CSRF protection on write actions
- Create text posts up to 280 characters
- Comment threads
- Likes and reposts
- Follow and unfollow users
- Send, accept, and decline friend requests
- Direct messages
- Notifications for likes, reposts, comments, follows, friend requests, friend accepts, and messages
- Search posts and people
- User profile pages with editable profile details
- Default illustrated avatars and theme colors
- Community totals in the menu drawer
- XP, levels, and profile completion progress

## XAMPP Setup

1. Copy this folder into XAMPP's web root:

   - macOS: `/Applications/XAMPP/xamppfiles/htdocs/xapp`
   - Windows: `C:\xampp\htdocs\xapp`

2. Start Apache and MySQL from XAMPP.

3. Open phpMyAdmin:

   `http://localhost/phpmyadmin`

4. Import [schema.sql](/Applications/XAMPP/xamppfiles/htdocs/xapp/schema.sql).

5. Check database credentials in [config.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/config.php).

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
- [profile.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/profile.php): public profile page
- [post.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/post.php): post and comments page
- [search.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/search.php): search page
- [messages.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/messages.php): direct messages page
- [notifications.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/notifications.php): notifications and friend request actions
- [community.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/community.php): community metrics and newest members
- [settings.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/settings.php): edit profile page
- [partials.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/partials.php): shared layout, nav, composer, and support widget
- [functions.php](/Applications/XAMPP/xamppfiles/htdocs/xapp/functions.php): shared helpers and SQL queries
- [script.js](/Applications/XAMPP/xamppfiles/htdocs/xapp/script.js): interactive UI behavior
- [styles.css](/Applications/XAMPP/xamppfiles/htdocs/xapp/styles.css): app styling
- [schema.sql](/Applications/XAMPP/xamppfiles/htdocs/xapp/schema.sql): MySQL database schema

## Notes

- `api.php` is not part of the current app.
- Image posting is not exposed in the current UI.
- Community totals now live on the dedicated Community page.
