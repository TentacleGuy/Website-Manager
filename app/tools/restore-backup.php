<?php
// Run only inside the project's PHP container; credentials arrive on stdin.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
$input = json_decode(stream_get_contents(STDIN), true);
$root = getcwd();
$installation = $root . '/installation';
$info = $input['database'];
$url = $input['url'];
try {
    if (is_file($installation . '/cli.php') && is_file($installation . '/src/Framework/Cli/InstallationQueue.php')) {
        // Generate the defaults with the installer bundled in this backup first.
        $autoload = require $installation . '/vendor/autoload.php';
        $autoload->setPsr4('Akeeba\\BRS\\', [$installation . '/src']);
        $autoload->setPsr4('Akeeba\\BRS\\Platform\\', [$installation . '/platform/src']);
        define('_AKEEBA', 1);
        $file = $installation . '/config.yml.php';
        $config = Symfony\Component\Yaml\Yaml::parse(file_get_contents($file));
        if (count($config['database'] ?? []) !== 1) throw new RuntimeException('Backups mit mehreren Datenbanken benötigen eine separate Zuordnung.');
        foreach ($config['database'] as &$database) {
            $database['dbhost'] = $info['host'];
            $database['dbport'] = 3306;
            $database['dbsocket'] = null;
            $database['dbencryption'] = false;
            $database['dbname'] = $info['database'];
            $database['dbuser'] = $info['user'];
            $database['dbpass'] = $info['password'];
            $database['dbtype'] = 'mysqli';
            $database['existing'] = 'dropall';
        }
        unset($database);
        foreach (['offsitedirs', 'publicfolder'] as $key) {
            if (!empty($config[$key])) throw new RuntimeException('Backup enthält externe Verzeichnisse. Automatische Wiederherstellung ist nur für ein einzelnes Website-Verzeichnis möglich.');
        }
        $config['setup']['siteurl'] = $url;
        $config['setup']['homeurl'] = $url;
        $config['setup']['live_site'] = '';
        $config['setup']['force_ssl'] = 0;
        $config['setup']['mailonline'] = false;
        file_put_contents($file, "#<?php die(); ?>\n" . Symfony\Component\Yaml\Yaml::dump($config, 6, 2));
        chmod($file, 0600);
        echo "VMM_CONFIGURED\n";
        exit;
    }
    // ANGIE (Akeeba Backup 3–9): use its own multipart SQL restoration engine.
    define('_AKEEBA', 1); define('_JEXEC', 1); define('_QQ_', '"');
    require $installation . '/defines.php';
    if (is_file($installation . '/platform/defines.php')) require $installation . '/platform/defines.php';
    if (!defined('JPATH_PLATFORM')) define('JPATH_PLATFORM', APATH_LIBRARIES);
    require $installation . '/angie/helpers/ini.php';
    require $installation . '/framework/autoloader.php';
    if (is_file($installation . '/framework/Autoloader/Autoloader.php')) require $installation . '/framework/Autoloader/Autoloader.php';
    require $installation . '/angie/autoloader.php';
    $container = new AContainer(['application_name' => 'angie']);
    $application = $container->application;
    $application->initialise();
    $model = AModel::getAnInstance('Database', 'AngieModel', [], $container);
    $keys = $model->getDatabaseNames();
    if (count($keys) !== 1) throw new RuntimeException('Backups mit mehreren Datenbanken benötigen eine separate Zuordnung.');
    $key = array_values($keys)[0];
    $data = (array) $model->getDatabaseInfo($key);
    $data = array_merge($data, ['dbhost'=>$info['host'], 'dbport'=>3306, 'dbsocket'=>'', 'dbencryption'=>false, 'dbname'=>$info['database'], 'dbuser'=>$info['user'], 'dbpass'=>$info['password'], 'dbtype'=>'mysqli', 'existing'=>'dropall']);
    $model->setDatabaseInfo($key, $data);
    $engine = ADatabaseRestore::getInstance($key, $data, $container);
    $engine->removeInformationFromStorage();
    $engine->removeLog();
    do {
        $engine->getTimer()->resetTime();
        $result = $engine->stepRestoration();
        if (!empty($result['error'])) throw new RuntimeException(strip_tags($result['error']));
    } while (empty($result['done']));
    echo "VMM_DATABASE_RESTORED\n";
} catch (Throwable $e) {
    // Do not echo original database details from an installer exception.
    fwrite(STDERR, str_replace($info['password'], '[redacted]', $e->getMessage()) . "\n");
    exit(1);
}
