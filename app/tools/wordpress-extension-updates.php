<?php
/** Plugin Name: VMM Extension Updates
 * Description: Native update integration for the premium sources configured locally in VMM.
 */
if (!defined('ABSPATH')) exit;
function vmm_extension_request($url,$data,$auth=true) {
    $s=$data['source'];$c=$data['credentials'];$args=['timeout'=>30,'redirection'=>0];
    if ($auth) {
        switch ($s['auth_type'] ?? '') {
            case 'query': $url=add_query_arg(array_merge($c['extra'] ?? [],[$s['auth_parameter']=>$c['key'] ?? '']),$url);break;
            case 'bearer':$args['headers']['Authorization']='Bearer '.($c['key'] ?? '');break;
            case 'basic':$args['headers']['Authorization']='Basic '.base64_encode(($c['username'] ?? '').':'.($c['password'] ?? ''));break;
            case 'headers':$args['headers']=array_merge($c['extra'] ?? [],[($s['auth_parameter'] ?: 'X-API-Key')=>$c['key'] ?? '']);break;
        }
    }
    return [$url,$args];
}
function vmm_extension_release($id,$data) {
    $cache=get_transient('vmm_release_'.$id);if (is_array($cache)) return $cache;
    $s=$data['source'];if (($s['source_type'] ?? '') !== 'update_xml') return null;
    [$url,$args]=vmm_extension_request($s['url'],$data,!empty($s['auth_metadata']));
    $response=wp_remote_get($url,$args);if (is_wp_error($response) || wp_remote_retrieve_response_code($response)!==200) return null;
    $previous=libxml_use_internal_errors(true);$xml=simplexml_load_string(wp_remote_retrieve_body($response),'SimpleXMLElement',LIBXML_NONET);libxml_clear_errors();libxml_use_internal_errors($previous);
    if (!$xml) return null;$best=null;
    foreach ($xml->xpath('//update') ?: [] as $update) {
        $version=(string)$update->version;$package=(string)$update->downloads->downloadurl;
        if (!$version || !$package || parse_url($package,PHP_URL_SCHEME)!=='https') continue;
        if ((string)$update->stability && strtolower((string)$update->stability)!=='stable') continue;
        foreach ($update->targetplatform as $target) { if (strtolower((string)$target['name'])==='wordpress' && @preg_match('~'.str_replace('~','\\~',(string)$target['version']).'~',$GLOBALS['wp_version'])!==1) continue 2; }
        if ((string)$update->php_minimum && version_compare(PHP_VERSION,(string)$update->php_minimum,'<')) continue;
        if (!$best || version_compare($version,$best['version'],'>')) $best=['version'=>$version,'url'=>$package];
    }
    if ($best) set_transient('vmm_release_'.$id,$best,3600);return $best;
}
function vmm_extension_updates($transient,$kind) {
    if (!is_object($transient)) return $transient;
    foreach (get_option('vmm_extension_sources',[]) as $id=>$data) {
        $s=$data['source'];if (($s['kind'] ?? '')!==$kind || ($s['source_type'] ?? '')==='wordpress_org') continue;
        $release=vmm_extension_release($id,$data);if (!$release) continue;
        $slug=$s['element'];$key=$slug;$current='';
        if ($kind==='theme') {$theme=wp_get_theme($slug);if (!$theme->exists()) continue;$current=$theme->get('Version');}
        else {
            if (!function_exists('get_plugins')) require_once ABSPATH.'wp-admin/includes/plugin.php';
            foreach (get_plugins() as $file=>$plugin) if ($file===$slug || dirname($file)===$slug) {$key=$file;$current=$plugin['Version'];break;}
        }
        if (!$current || !version_compare($release['version'],$current,'>')) continue;
        [$url]=vmm_extension_request($release['url'],$data);
        $value=['slug'=>$slug,'new_version'=>$release['version'],'package'=>$url,'url'=>$s['url']];
        if ($kind==='theme') {$value['theme']=$slug;$transient->response[$key]=$value;}
        else {$value['plugin']=$key;$transient->response[$key]=(object)$value;}
    }
    return $transient;
}
add_filter('pre_set_site_transient_update_plugins',function($t){return vmm_extension_updates($t,'plugin');},9999);
add_filter('pre_set_site_transient_update_themes',function($t){return vmm_extension_updates($t,'theme');},9999);
add_filter('http_request_args',function($args,$url){
    foreach (get_option('vmm_extension_sources',[]) as $id=>$data) {
        $release=get_transient('vmm_release_'.$id);if (!is_array($release)) continue;
        $a=wp_parse_url($url);$b=wp_parse_url($release['url']);
        if (($a['scheme'] ?? '')==='https' && ($a['host'] ?? '')===($b['host'] ?? '') && ($a['path'] ?? '')===($b['path'] ?? '')) {
            [, $auth]=vmm_extension_request($url,$data);$args['headers']=array_merge((array)($args['headers'] ?? []),$auth['headers'] ?? []);$args['redirection']=0;
        }
    }
    return $args;
},10,2);
