<?php
if (PHP_SAPI!=='cli') exit;
ini_set('display_errors','stderr');error_reporting(E_ERROR|E_PARSE);
$v=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
define('_JEXEC',1);define('JPATH_BASE',getenv('VMM_PROJECT_ROOT')?:'/var/www/html');
ob_start();require JPATH_BASE.'/includes/defines.php';require JPATH_BASE.'/includes/framework.php';ob_end_clean();
$modern=method_exists(\Joomla\CMS\Factory::class,'getContainer');
$db=$modern?\Joomla\CMS\Factory::getContainer()->get(\Joomla\Database\DatabaseInterface::class):\JFactory::getDbo();
if ($v['action']==='list') {$db->setQuery('SELECT id AS ID,username AS user_login,email AS user_email,name AS display_name FROM #__users ORDER BY id');echo json_encode($db->loadAssocList());exit;}
if ($modern) {
 $c=\Joomla\CMS\Factory::getContainer();$c->alias('session','session.cli')->alias(\Joomla\Session\SessionInterface::class,'session.cli');
 \Joomla\CMS\Factory::$application=$c->get(\Joomla\Console\Application::class);
 \Joomla\CMS\Factory::$application->createExtensionNamespaceMap();
}
$user=new \Joomla\CMS\User\User($v['action']==='reset'?(int)$v['id']:0);
if ($v['action']==='reset') {if (!$user->id)throw new RuntimeException('Benutzer nicht gefunden.');$user->password=\Joomla\CMS\User\UserHelper::hashPassword($v['password']);}
else {
 $groups=['administrator'=>8,'editor'=>6,'author'=>3,'subscriber'=>2];if(!isset($groups[$v['role']]))throw new RuntimeException('Unbekannte Rolle.');
 $data=['name'=>$v['name'],'username'=>$v['username'],'email'=>$v['email'],'password'=>$v['password'],'password2'=>$v['password'],'groups'=>[$groups[$v['role']]],'block'=>0];
 if(!$user->bind($data))throw new RuntimeException('Benutzerdaten konnten nicht übernommen werden.');
}
if(!$user->save())throw new RuntimeException($user->getError()?:'Benutzer konnte nicht gespeichert werden.');
echo json_encode(['ok'=>true,'id'=>$user->id]);
