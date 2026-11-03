<?php
// Read one manager-initiated backup record; never modify Akeeba's records.
if (PHP_SAPI !== 'cli') exit(1);
try {
    $input = json_decode(stream_get_contents(STDIN), true);
    $root = getenv('VMM_PROJECT_ROOT') ?: getcwd();
    if (is_file($root . '/configuration.php')) {
        require_once $root . '/configuration.php';
        $config = new JConfig;
        $host=$config->host; $user=$config->user; $password=$config->password; $database=$config->db; $prefix=$config->dbprefix;
        $table=is_dir($root.'/administrator/components/com_akeebabackup') ? 'akeebabackup_backups' : 'ak_stats';
    } else {
        require_once $root . '/wp-load.php';
        global $wpdb;
        $host=DB_HOST; $user=DB_USER; $password=DB_PASSWORD; $database=DB_NAME; $prefix=$wpdb->prefix; $table='ak_stats';
    }
    if (!preg_match('/^[a-zA-Z0-9_]+$/D', $prefix)) throw new RuntimeException('Ungültiges Tabellenpräfix.');
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db=new mysqli($host,$user,$password,$database); $db->set_charset('utf8mb4');
    $query=$db->prepare('SELECT id,description,status,multipart,archivename,absolute_path,type FROM `'.$prefix.$table.'` WHERE description=? AND profile_id=? ORDER BY id DESC LIMIT 1');
    $description=$input['description']; $profile=(int)$input['profile'];
    if (!preg_match('/^(?:VMM|TENTACLE)-[a-f0-9]{24}$/D',$description)) throw new RuntimeException('Ungültige Backup-Kennung.');
    $query->bind_param('si',$description,$profile); $query->execute();
    $query->bind_result($id,$desc,$status,$parts,$name,$path,$type); $rows=[];
    if ($query->fetch()) $rows[]=['id'=>$id,'description'=>$desc,'status'=>$status,'multipart'=>$parts,'archivename'=>$name,'absolute_path'=>$path,'type'=>$type];
    echo json_encode($rows);
} catch (Throwable $e) {
    fwrite(STDERR,"Akeebas vorhandener Backup-Eintrag konnte nicht gelesen werden.\n");
    exit(1);
}
