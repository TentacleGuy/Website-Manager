<?php
/** Read the installed Akeeba command's option definition without taking a backup. */
if (PHP_SAPI !== 'cli') exit(1);
define('_JEXEC', 1);
define('JPATH_BASE', getenv('VMM_PROJECT_ROOT') ?: getcwd());
require_once JPATH_BASE.'/includes/defines.php';
require_once JPATH_BASE.'/includes/framework.php';
$container=\Joomla\CMS\Factory::getContainer();
$container->alias('session','session.cli')
    ->alias('JSession','session.cli')
    ->alias(\Joomla\CMS\Session\Session::class,'session.cli')
    ->alias(\Joomla\Session\Session::class,'session.cli')
    ->alias(\Joomla\Session\SessionInterface::class,'session.cli');
$app=$container->get(\Joomla\Console\Application::class);
\Joomla\CMS\Factory::$application=$app;
$app->addCommand(new class extends \Joomla\Console\Command\AbstractCommand {
    protected static $defaultName='vmm:akeeba-options';
    protected function configure(): void {$this->setDescription('Read Akeeba backup option types');}
    protected function doExecute(\Symfony\Component\Console\Input\InputInterface $input,\Symfony\Component\Console\Output\OutputInterface $output): int {
        $option=$this->getApplication()->getCommand('akeeba:backup:take')->getDefinition()->getOption('overrides');
        $output->writeln(json_encode(['definition'=>['options'=>['overrides'=>['is_multiple'=>$option->isArray(),'accept_value'=>$option->acceptValue()]]]]));
        return 0;
    }
});
$app->execute();
