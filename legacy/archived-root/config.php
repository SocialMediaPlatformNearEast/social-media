<?php
declare(strict_types=1);

const DB_HOST = '127.0.0.1';
const DB_NAME = 'xapp';
const DB_USER = 'root';
const DB_PASS = '';
const DB_CHARSET = 'utf8mb4';

const APP_NAME = 'LvL';
const APP_BASE_URL = '';

session_name('xapp_session');
session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_start();
