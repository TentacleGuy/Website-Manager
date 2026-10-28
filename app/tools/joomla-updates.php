<?php
/** Bridge to Joomla's native installer model; no parallel update implementation. */
define('_JEXEC', 1);
define('JPATH_BASE', getenv('VMM_PROJECT_ROOT') ?: '/var/www/html');
if (!is_file(JPATH_BASE.'/configuration.php') || !is_file(JPATH_BASE.'/cli/joomla.php')) {
    fwrite(STDERR, "Zuerst Joomla installieren. Diese Aktion benötigt Joomla 4 oder neuer.\n"); exit(2);
}
require_once JPATH_BASE.'/includes/defines.php';
require_once JPATH_BASE.'/includes/framework.php';
$container = \Joomla\CMS\Factory::getContainer();
$container->alias('session','session.cli')
    ->alias('JSession','session.cli')
    ->alias(\Joomla\CMS\Session\Session::class,'session.cli')
    ->alias(\Joomla\Session\Session::class,'session.cli')
    ->alias(\Joomla\Session\SessionInterface::class,'session.cli');
$app = $container->get(\Joomla\Console\Application::class);
\Joomla\CMS\Factory::$application = $app;
$app->addCommand(new class extends \Joomla\Console\Command\AbstractCommand {
    protected static $defaultName = 'vmm:updates';
    protected function configure(): void {
        $this->addOption('extension',null,\Symfony\Component\Console\Input\InputOption::VALUE_REQUIRED,'Extension ID');
        $this->setDescription('Use the native Joomla extension updater');
        $this->addOption('apply',null,\Symfony\Component\Console\Input\InputOption::VALUE_NONE,'Install available updates');
    }
    protected function doExecute(\Symfony\Component\Console\Input\InputInterface $input, \Symfony\Component\Console\Output\OutputInterface $output): int {
        $this->getApplication()->getLanguage()->load('lib_joomla');
        $this->getApplication()->getLanguage()->load('com_installer',JPATH_ADMINISTRATOR);
        $model=$this->getApplication()->bootComponent('com_installer')->getMVCFactory()->createModel('Update','Administrator',['ignore_request'=>true]);
        $model->purge();
        $model->findUpdates();
        $model->setState('list.limit',0);
        $items=$model->getItems();
        $ids=[];
        foreach($items as $item) {
            if ($input->getOption('extension') && (int)$item->extension_id !== (int)$input->getOption('extension')) continue;
            $ids[]=(int)$item->update_id;
            $output->writeln($item->name.': '.$item->current_version.' → '.$item->version);
        }
        if (!$ids) { $output->writeln('Keine Erweiterungsupdates verfügbar.'); return 0; }
        if ($input->getOption('apply')) {
            $model->update($ids);
            if (!$model->getState('result')) {
                // CMS messages may contain download tokens; do not forward them.
                $output->writeln('Mindestens ein CMS-Update ist fehlgeschlagen. Details in der Joomla-Verwaltung prüfen.');
                return 2;
            }
            $output->writeln('Erweiterungsupdates installiert.');
        }
        return 0;
    }
});
$app->execute();
