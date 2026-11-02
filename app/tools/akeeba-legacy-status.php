<?php
// Joomla 3 / Akeeba 8: query only the native record for this unique backup.
if (PHP_SAPI !== 'cli') exit(1);
try {
    $input = json_decode(stream_get_contents(STDIN), true);
    $root = getenv('VMM_PROJECT_ROOT') ?: getcwd();
    require_once $root . '/configuration.php';
    $config = new JConfig;
    if (!preg_match('/^[a-zA-Z0-9_]+$/D', $config->dbprefix)) throw new RuntimeException('Ungültiges Tabellenpräfix.');
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db = new mysqli($config->host, $config->user, $config->password, $config->db);
    $db->set_charset('utf8mb4');
    $query = $db->prepare('SELECT id,description,status,multipart FROM `' . $config->dbprefix . 'ak_stats` WHERE description=? AND profile_id=? ORDER BY id DESC LIMIT 1');
    $description = $input['description']; $profile = (int)$input['profile'];
    $query->bind_param('si', $description, $profile); $query->execute();
    $query->bind_result($id, $desc, $status, $parts); $rows=[];
    if ($query->fetch()) $rows[]=['id'=>$id,'description'=>$desc,'status'=>$status,'multipart'=>$parts];
    echo json_encode($rows);
} catch (Throwable $e) {
    fwrite(STDERR, "Der native Akeeba-Sicherungsstatus für Joomla 3 konnte nicht gelesen werden.\n");
    exit(1);
}
