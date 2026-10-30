<?php
// Avoid optional administrator emails for backups initiated by the local manager.
if (!defined('AKEEBA_BACKUP_ORIGIN')) define('AKEEBA_BACKUP_ORIGIN', 'backend');
spl_autoload_register(function ($class) {
    if (strcasecmp(ltrim($class, '\\'), 'Akeeba\\Engine\\Archiver\\Vmmjpa') === 0) {
        require_once __DIR__ . '/akeeba-originals-archiver.php';
    }
}, true, true);
