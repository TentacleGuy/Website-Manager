<?php
/** Inventory and licence configuration, executed only from the CLI. */
if (PHP_SAPI !== 'cli') exit(1);
// Legacy CMS deprecations must not corrupt the JSON inventory protocol.
ini_set('display_errors','stderr');
error_reporting(E_ERROR | E_PARSE);
$action = $argv[1] ?? 'inventory';
if (!function_exists('get_option')) {
    ob_start();
    define('_JEXEC', 1);
    define('JPATH_BASE', getenv('VMM_PROJECT_ROOT') ?: '/var/www/html');
    require_once JPATH_BASE.'/includes/defines.php';
    require_once JPATH_BASE.'/includes/framework.php';
    ob_end_clean();
    ini_set('display_errors','stderr');
    error_reporting(E_ERROR | E_PARSE);
    $db = class_exists('Joomla\\CMS\\Factory') && method_exists('Joomla\\CMS\\Factory', 'getContainer')
        ? \Joomla\CMS\Factory::getContainer()->get(\Joomla\Database\DatabaseInterface::class) : \JFactory::getDbo();
    if ($action === 'license-scan') {
        $db->setQuery('SELECT e.element,s.name AS label,s.extra_query,s.location FROM #__update_sites s JOIN #__update_sites_extensions x ON x.update_site_id=s.update_site_id JOIN #__extensions e ON e.extension_id=x.extension_id');$out=[];
        foreach($db->loadAssocList() as $row){parse_str($row['extra_query']??'',$params);foreach(['key','dlid','downloadid','download_id','apikey','api_key'] as $k)if(!empty($params[$k])&&is_string($params[$k]))$out[]=['element'=>$row['element'],'label'=>$row['label'],'url'=>$row['location'],'key'=>$params[$k]];}
        $db->setQuery("SELECT element,name,params FROM #__extensions WHERE folder='installer'");foreach($db->loadAssocList() as $row){$params=json_decode($row['params'],true)?:[];foreach(['key','dlid','downloadid','download_id','apikey','api_key'] as $k)if(!empty($params[$k])&&is_string($params[$k]))$out[]=['element'=>$row['element'],'label'=>$row['name'],'url'=>'','key'=>$params[$k]];}
        echo json_encode($out);exit;
    }
    if ($action === 'inventory') {
        $db->setQuery('SELECT extension_id,name,element,type AS kind,folder,enabled,protected,manifest_cache FROM #__extensions ORDER BY name');$rows=$db->loadAssocList();
        $db->setQuery('SELECT extension_id,version FROM #__updates');$updates=[];foreach($db->loadAssocList() as $u){$id=$u['extension_id'];if(!isset($updates[$id]) || version_compare($u['version'],$updates[$id],'>'))$updates[$id]=$u['version'];}
        $items=[];
        foreach ($rows as $r) {
            $manifest=json_decode($r['manifest_cache'],true) ?: [];

            if(isset($updates[$r['extension_id']]) && !version_compare($updates[$r['extension_id']],$manifest['version'] ?? '0','>'))unset($updates[$r['extension_id']]);
            $items[]=['id'=>(int)$r['extension_id'],'name'=>$r['name'],'element'=>$r['element'],'kind'=>$r['kind'],'folder'=>$r['folder'],'version'=>$manifest['version'] ?? '', 'enabled'=>(bool)$r['enabled'],'update'=>isset($updates[$r['extension_id']])?'available':'unknown','available'=>$updates[$r['extension_id']] ?? ''];
        }
        echo json_encode($items);exit;
    }
    $data=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
    $s=$data['source'];$cred=$data['credentials'];$element=$s['element'];
    if (!$element) throw new RuntimeException('CMS-Kennung fehlt. In der Erweiterungsquelle ergänzen.');
    $db->setQuery('SELECT extension_id,params,element,type,folder,package_id FROM #__extensions WHERE element='.$db->quote($element));
    $extensions=$db->loadAssocList();
    if (!$extensions) throw new RuntimeException('Installierte Erweiterung passt nicht zur konfigurierten CMS-Kennung.');
    $ids=array_unique(array_merge(array_column($extensions,'extension_id'),array_filter(array_column($extensions,'package_id'))));$query=$cred['extra'] ?? [];
    if (($s['auth_type'] ?? '') === 'query') $query[$s['auth_parameter']]=$cred['key'] ?? '';
    $changed=0;
    if ($query) {
        $db->setQuery('SELECT update_site_id FROM #__update_sites_extensions WHERE extension_id IN ('.implode(',',array_map('intval',$ids)).')');
        $sites=$db->loadColumn();
        foreach ($sites as $id) {
            $db->setQuery('SELECT extra_query FROM #__update_sites WHERE update_site_id='.(int)$id);parse_str((string)$db->loadResult(),$existing);
            $db->setQuery('UPDATE #__update_sites SET extra_query='.$db->quote(http_build_query(array_merge($existing,$query))).',enabled=1 WHERE update_site_id='.(int)$id)->execute();$changed++;
        }
    }
    // Optional, explicit vendor parameter mapping. Existing settings remain intact.
    foreach (($s['cms_config']['joomla_params'] ?? []) as $target=>$fields) {
        $db->setQuery('SELECT extension_id,params FROM #__extensions WHERE element='.$db->quote($target));
        foreach ($db->loadAssocList() as $row) {
            $params=json_decode($row['params'],true) ?: [];
            foreach ($fields as $key=>$credential) $params[$key]=$cred[$credential] ?? ($cred['extra'][$credential] ?? '');
            $db->setQuery('UPDATE #__extensions SET params='.$db->quote(json_encode($params)).' WHERE extension_id='.(int)$row['extension_id'])->execute();$changed++;
        }
    }
    if (!$changed) throw new RuntimeException('Paket installiert, aber keine passende Updatequelle/Lizenzzuordnung gefunden. CMS-Konfiguration in der Quelle ergänzen und erneut versuchen.');
    echo 'Lizenz in Joomla-Updatekonfiguration hinterlegt.';exit;
}
// WordPress is already bootstrapped by wp eval-file.
$data=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$s=$data['source'];$cred=$data['credentials'];
if (empty($s['element'])) throw new RuntimeException('WordPress-Slug in der Erweiterungsquelle ergänzen.');
foreach (($s['cms_config']['wordpress_options'] ?? []) as $name=>$fields) {
    if (is_string($fields)) update_option($name,$cred[$fields] ?? ($cred['extra'][$fields] ?? ''),false);
    else {
        $value=get_option($name,[]);if (!is_array($value)) $value=[];
        foreach ($fields as $key=>$field) $value[$key]=$cred[$field] ?? ($cred['extra'][$field] ?? '');
        update_option($name,$value,false);
    }
}
$all=get_option('vmm_extension_sources',[]);$all[$s['id']]=$data;update_option('vmm_extension_sources',$all,false);
$dir=WPMU_PLUGIN_DIR;if (!is_dir($dir)) wp_mkdir_p($dir);
if (!copy(__DIR__.'/wordpress-extension-updates.php',$dir.'/vmm-extension-updates.php')) throw new RuntimeException('WordPress-Updateanbindung konnte nicht geschrieben werden.');
delete_site_transient('update_plugins');delete_site_transient('update_themes');
echo 'Lizenz und native WordPress-Updateanbindung hinterlegt.';
