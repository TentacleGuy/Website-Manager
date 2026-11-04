<?php
// Avoid optional administrator emails for backups initiated by the local manager.
if (!defined('AKEEBA_BACKUP_ORIGIN')) define('AKEEBA_BACKUP_ORIGIN', 'backend');
spl_autoload_register(function ($class) {
    if (in_array(strtolower(ltrim($class, '\\')), ['akeeba\\engine\\archiver\\vmmjpa', 'akeeba\\engine\\archiver\\vmmzip'], true)) {
        require_once __DIR__ . '/akeeba-originals-archiver.php';
    }
}, true, true);
