<?php
if(PHP_SAPI!=='cli')exit(1);
$root=getenv('VMM_PROJECT_ROOT')?:getcwd();
if(is_file($root.'/configuration.php')){require $root.'/configuration.php';$c=new JConfig;$db=new mysqli($c->host,$c->user,$c->password,$c->db);$prefix=$c->dbprefix;$table=is_dir($root.'/administrator/components/com_akeebabackup')?'akeebabackup_profiles':'ak_profiles';}
else {require $root.'/wp-load.php';global $wpdb;$db=new mysqli(DB_HOST,DB_USER,DB_PASSWORD,DB_NAME);$prefix=$wpdb->prefix;$table='ak_profiles';}
if(!preg_match('/^[a-zA-Z0-9_]+$/D',$prefix))exit(1);
$r=$db->query('SELECT id,description AS name FROM `'.$prefix.$table.'` ORDER BY id');echo json_encode($r->fetch_all(MYSQLI_ASSOC));
