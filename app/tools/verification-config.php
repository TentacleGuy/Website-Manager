<?php
// Only run in the isolated verification container, never in an original project.
if (PHP_SAPI !== 'cli' || getenv('VMM_VERIFICATION') !== '1') exit(1);
$input=json_decode(stream_get_contents(STDIN),true);$root=getcwd();
if (is_file($root.'/configuration.php')) {
    $file=$root.'/configuration.php';$text=file_get_contents($file);
    foreach (['host'=>$input['host'],'user'=>$input['user'],'password'=>$input['password'],'db'=>$input['database'],'live_site'=>'','force_ssl'=>0,'offline'=>0,'mailonline'=>0,'log_path'=>$root.'/administrator/logs','tmp_path'=>$root.'/tmp','cookie_domain'=>'','cookie_path'=>''] as $key=>$value) {
        $replacement=var_export($value,true);
        $text=preg_replace_callback('/(public\s+\$'.preg_quote($key,'/').'\s*=\s*)(?:\'(?:[^\'\\\\]|\\\\.)*\'|"(?:[^"\\\\]|\\\\.)*"|[^;]+);/',function($m) use($replacement){return $m[1].$replacement.';';},$text);
    }
    file_put_contents($file,$text);
} elseif (is_file($root.'/wp-config.php')) {
    $file=$root.'/wp-config.php';$text=file_get_contents($file);
    foreach (['DB_HOST'=>$input['host'],'DB_NAME'=>$input['database'],'DB_USER'=>$input['user'],'DB_PASSWORD'=>$input['password'],'WP_HOME'=>($input['url']??'http://localhost'),'WP_SITEURL'=>($input['url']??'http://localhost'),'FORCE_SSL_ADMIN'=>false,'FORCE_SSL_LOGIN'=>false] as $key=>$value) {
        $pattern='/define\s*\(\s*[\'\"]'.preg_quote($key,'/').'[\'\"]\s*,\s*(?:\'(?:[^\'\\\\]|\\\\.)*\'|"(?:[^"\\\\]|\\\\.)*"|[^;]+?)\s*\)\s*;/s';
        $line='define('.var_export($key,true).','.var_export($value,true).');';
        $count=0;$text=preg_replace_callback($pattern,function()use($line){return $line;},$text,-1,$count);
        if (!$count)$text=preg_replace('/<\?php/',"<?php\n".$line,$text,1);
    }
    file_put_contents($file,$text);
} else throw new RuntimeException('Keine unterstützte CMS-Konfiguration gefunden.');
echo "VMM_ISOLATED_CONFIGURED\n";
