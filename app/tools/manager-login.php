<?php
// Short-lived, single-use local manager login. No passwords or permanent bypass.
$token=$_GET['token']??'';if(!preg_match('/^[A-Za-z0-9_-]{40,60}$/D',$token)){http_response_code(403);exit;}
$file=dirname(__DIR__).'/tools/login-'.hash('sha256',$token).'.json';
$claim=@rename($file,$file.'.used');if(!$claim){http_response_code(403);exit;}
$v=json_decode(file_get_contents($file.'.used'),true);unlink($file.'.used');
if(!$v || $v['expires']<time()){http_response_code(403);exit;}
header('Cache-Control: no-store');header('Referrer-Policy: no-referrer');
if($v['cms']==='wordpress') {require __DIR__.'/wp-load.php';$u=get_user_by('id',(int)$v['id']);if(!$u || !user_can($u,'read')){http_response_code(403);exit;}wp_set_current_user($u->ID);wp_set_auth_cookie($u->ID,false);wp_safe_redirect(admin_url());exit;}
try {
$stage='bootstrap';define('_JEXEC',1);define('JPATH_BASE',__DIR__.'/administrator');require JPATH_BASE.'/includes/defines.php';require JPATH_BASE.'/includes/framework.php';
if(method_exists(\Joomla\CMS\Factory::class,'getContainer')){$c=\Joomla\CMS\Factory::getContainer();$c->alias('session.web','session.web.administrator')->alias('session','session.web.administrator')->alias('JSession','session.web.administrator')->alias(\Joomla\CMS\Session\Session::class,'session.web.administrator')->alias(\Joomla\Session\Session::class,'session.web.administrator')->alias(\Joomla\Session\SessionInterface::class,'session.web.administrator');$app=$c->get(\Joomla\CMS\Application\AdministratorApplication::class);\Joomla\CMS\Factory::$application=$app;$app->createExtensionNamespaceMap();$stage='user';$u=$c->get(\Joomla\CMS\User\UserFactoryInterface::class)->loadUserById((int)$v['id']);}
else{$app=JFactory::getApplication('administrator');$u=JFactory::getUser((int)$v['id']);}
if(!$u->id || $u->block || !$u->authorise('core.login.admin')){http_response_code(403);echo 'Dieses Konto darf sich nicht im Backend anmelden.';exit;}
$stage='session';$u->guest=0;$app->loadIdentity($u);$session=$app->getSession();$session->start();$session->fork();$session->set('user',$u);$session->set('com_users.mfa_checked',0);if(method_exists($app,'checkSession'))$app->checkSession();$session->close();header('Location: /administrator/');exit;

} catch (Throwable $e) { file_put_contents(dirname(__DIR__).'/tools/manager-login-error.json',json_encode(['stage'=>$stage,'type'=>get_class($e),'message'=>$e->getMessage()]));http_response_code(500);echo 'Joomla-Login fehlgeschlagen. Details im lokalen Manager-Projektordner unter tools/manager-login-error.json.';exit;}
