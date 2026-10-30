<?php
/** Read native update metadata; downloads never install or reactivate a plugin. */
if (PHP_SAPI !== 'cli') exit(1);
ini_set('display_errors', 'stderr');
$input = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
$action = $input['action'] ?? 'list';
function vmm_library_output($value) { echo 'VMM_LIBRARY_JSON:' . json_encode($value, JSON_THROW_ON_ERROR); }
function vmm_library_https($url) {
    $p = parse_url($url);
    if (($p['scheme'] ?? '') !== 'https' || empty($p['host']) || isset($p['user']) || isset($p['pass']) || (isset($p['port']) && $p['port'] !== 443)) throw new RuntimeException('Keine unterstützte HTTPS-Downloadquelle.');
    return $url;
}
try {
    if (function_exists('get_plugins') || defined('ABSPATH')) {
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
        require_once ABSPATH . 'wp-admin/includes/file.php';
        // Refresh through the site's own updater, including active premium integrations.
        $plugins = get_site_transient('update_plugins');
        if (is_object($plugins)) { $plugins->last_checked=0;set_site_transient('update_plugins',$plugins); }
        wp_update_plugins();
        $themes = get_site_transient('update_themes');
        if (is_object($themes)) { $themes->last_checked=0;set_site_transient('update_themes',$themes); }
        wp_update_themes();
        $cache=['plugin'=>get_site_transient('update_plugins'), 'theme'=>get_site_transient('update_themes')];
        $rows=[];
        foreach (get_plugins() as $file=>$data) {
            $slug=dirname($file)==='.' ? basename($file,'.php') : dirname($file);
            $u=(array)($cache['plugin']->response[$file] ?? $cache['plugin']->no_update[$file] ?? []);
            $rows[]=['key'=>'plugin:'.$file,'name'=>$data['Name'],'cms'=>'wordpress','kind'=>'plugin','element'=>$slug,'version'=>$data['Version'],'latest'=>$u['new_version'] ?? '', 'url'=>$u['package'] ?? '', 'hint'=>$data['UpdateURI'] ?? ''];
        }
        foreach (wp_get_themes() as $slug=>$theme) {
            $u=(array)($cache['theme']->response[$slug] ?? $cache['theme']->no_update[$slug] ?? []);
            $rows[]=['key'=>'theme:'.$slug,'name'=>$theme->get('Name'),'cms'=>'wordpress','kind'=>'theme','element'=>$slug,'version'=>$theme->get('Version'),'latest'=>$u['new_version'] ?? '', 'url'=>$u['package'] ?? '', 'hint'=>$theme->get('UpdateURI')];
        }
        // OTGS also exposes original packages when the installed version is current.
        $otgs=function_exists('WP_Installer') ? WP_Installer() : null;
        if ($otgs && $action!=='list' && method_exists($otgs,'refresh_repositories_data')) $otgs->refresh_repositories_data();
        foreach ($rows as &$row) {
            $row['can_download']=!empty($row['url']);
            if ($otgs && $row['kind']==='plugin') {
                foreach (($otgs->get_settings()['repositories'] ?? []) as $repo=>$settings) {
                    foreach (($settings['data']['downloads']['plugins'] ?? []) as $slug=>$download) {
                        if ($slug===$row['element'] || ($download['name'] ?? '')===$row['name']) {
                            $row['can_download']=true;
                            $row['otgs']=true;
                            $row['origin']='OTGS Installer · '.$repo;
                            $row['license_key']=method_exists($otgs,'get_repository_site_key') ? (string)$otgs->get_repository_site_key($repo) : '';
                        }
                    }
                }
            }
            if (empty($row['origin'])) $row['origin']=parse_url($row['url'] ?: $row['hint'],PHP_URL_HOST) ?: 'Quelle noch ungeklärt';
            $row['has_key']=!empty($row['license_key']);
        }
        unset($row);
        if ($action==='list') { vmm_library_output($rows);exit; }
        $selected=null;foreach ($rows as $row) if ($row['key']===($input['key'] ?? '')) $selected=$row;
        if (!$selected) throw new RuntimeException('Erweiterung nicht mehr installiert.');
        if ((empty($selected['url']) || !empty($selected['otgs'])) && $selected['kind']==='plugin') {
            $info=plugins_api('plugin_information',(object)['slug'=>$selected['element'],'fields'=>['sections'=>false]]);
            if (!is_wp_error($info) && strcasecmp(wp_strip_all_tags($info->name ?? ''),wp_strip_all_tags($selected['name']))===0) {
                $selected['url']=$info->download_link ?? '';$selected['latest']=$info->version ?? '';
            }
        }
        if (empty($selected['url']) || empty($selected['latest'])) throw new RuntimeException('Kein Originalpaket verfügbar. Lizenz und Updateanbindung im CMS prüfen.');
        $url=vmm_library_https($selected['url']);
        if (!empty($input['download_key'])) {
            parse_str(parse_url($url,PHP_URL_QUERY) ?: '',$params);
            foreach (['site_key','dlid','download_id','downloadid','apikey','api_key','key'] as $parameter) {
                if (array_key_exists($parameter,$params)) { $url=add_query_arg($parameter,$input['download_key'],$url);break; }
            }
        }
        if ($action==='download') {
            $token=$input['token'] ?? '';
            if (!preg_match('/^[a-f0-9]{24}$/D',$token)) throw new RuntimeException('Ungültiges Downloadziel.');
            $tmp=download_url($url,180);
            if (is_wp_error($tmp)) throw new RuntimeException('Das CMS konnte das Originalpaket nicht herunterladen. Lizenz und Verbindung prüfen.');
            $target=__DIR__.'/library-'.$token.'.zip';
            try {
                if (filesize($tmp)>1073741824 || !copy($tmp,$target)) throw new RuntimeException('Download zu groß oder nicht speicherbar.');
                chmod($target,0600);
            } finally { @unlink($tmp); }
            vmm_library_output(['latest'=>$selected['latest'],'token'=>$token]);exit;
        }
        vmm_library_output(['latest'=>$selected['latest']]);exit;
    }
    define('_JEXEC',1);
    define('JPATH_BASE',getenv('VMM_PROJECT_ROOT') ?: getcwd());
    require JPATH_BASE.'/includes/defines.php';
    require JPATH_BASE.'/includes/framework.php';
    $container=\Joomla\CMS\Factory::getContainer();
    $container->alias('session','session.cli')->alias('JSession','session.cli')->alias(\Joomla\CMS\Session\Session::class,'session.cli')->alias(\Joomla\Session\Session::class,'session.cli')->alias(\Joomla\Session\SessionInterface::class,'session.cli');
    $app=$container->get(\Joomla\Console\Application::class);
    \Joomla\CMS\Factory::$application=$app;
    $db=$container->get(\Joomla\Database\DatabaseInterface::class);
    $db->setQuery("SELECT e.extension_id,e.name,e.element,e.type,e.manifest_cache,s.location,s.extra_query FROM #__extensions e LEFT JOIN #__update_sites_extensions x ON x.extension_id=e.extension_id LEFT JOIN #__update_sites s ON s.update_site_id=x.update_site_id AND s.enabled=1 WHERE e.protected=0 AND e.type IN ('component','package','plugin','template') ORDER BY e.name");
    $rows=[];
    foreach ($db->loadAssocList() as $r) {
        $key='joomla:'.$r['extension_id'];
        if (isset($rows[$key]) && !empty($rows[$key]['url'])) continue;
        $manifest=json_decode($r['manifest_cache'],true) ?: [];
        parse_str($r['extra_query'] ?? '',$params);$license='';
        foreach (['dlid','download_id','downloadid','apikey','api_key','key'] as $parameter) if (!empty($params[$parameter]) && is_string($params[$parameter])) {$license=$params[$parameter];break;}
        $rows[$key]=['key'=>$key,'name'=>$r['name'],'cms'=>'joomla','kind'=>$r['type']==='template'?'theme':($r['type']==='plugin'?'plugin':'package'),'element'=>$r['element'],'version'=>$manifest['version'] ?? '', 'latest'=>'','url'=>$r['location'] ?? '', 'extra_query'=>$r['extra_query'] ?? '', 'origin'=>parse_url($r['location'] ?? '',PHP_URL_HOST) ?: 'Quelle noch ungeklärt', 'has_key'=>$license!=='','license_key'=>$license,'can_download'=>strpos($r['location'] ?? '','https://')===0];
    }
    if ($action==='list') {vmm_library_output(array_values($rows));exit;}
    $row=$rows[$input['key'] ?? ''] ?? null;
    if (!$row || !$row['can_download']) throw new RuntimeException('Keine unterstützte Updatequelle für diese Erweiterung gefunden.');
    vmm_library_output($row);
} catch (Throwable $e) {
    // Store only structural diagnostics; vendor messages may contain signed URLs.
    @file_put_contents(__DIR__.'/library-error.json',json_encode(['class'=>get_class($e),'file'=>basename($e->getFile()),'line'=>$e->getLine()]));
    @chmod(__DIR__.'/library-error.json',0600);
    fwrite(STDERR,"Paketquelle konnte nicht gelesen werden. Projektstatus, CMS-Version und Lizenz im CMS prüfen.\n");
    exit(1);
}
