<?php
namespace Akeeba\Engine\Archiver;

/** Remap archive entries only; never change the running website's files. */
trait VmmOriginalEntries
{
    protected function _addFile($isVirtual, &$sourceNameOrData, $targetName)
    {
        $mapped = false;
        if (!$isVirtual && is_string($sourceNameOrData)) {
            $root = realpath(getenv('VMM_PROJECT_ROOT') ?: getcwd());
            $source = realpath($sourceNameOrData);
            if ($root !== false && $source !== false && strpos($source, $root . DIRECTORY_SEPARATOR) === 0) {
                $name = str_replace(DIRECTORY_SEPARATOR, '/', substr($source, strlen($root) + 1));
                $map = json_decode(file_get_contents(__DIR__ . '/akeeba-originals.json'), true);
                if (!is_array($map)) throw new \RuntimeException('Serverdatei-Zuordnung ist ungültig.');
                if (array_key_exists($name, $map)) {
                    $archiveName = str_replace('\\', '/', $targetName);
                    if (substr($archiveName, 0, 2) === './') $archiveName = substr($archiveName, 2);
                    if ($archiveName !== $name) return parent::_addFile($isVirtual, $sourceNameOrData, $targetName);
                    if ($map[$name] === null) return true;
                    $targetName = $map[$name];
                    $mapped = true;
                }
            }
        }
        $result = parent::_addFile($isVirtual, $sourceNameOrData, $targetName);
        if ($mapped && $result === true) {
            $report = __DIR__ . '/akeeba-originals-report.json';
            $seen = is_file($report) ? json_decode(file_get_contents($report), true) : [];
            if (!is_array($seen)) $seen = [];
            $seen[$targetName] = true;
            if (file_put_contents($report, json_encode($seen)) === false) throw new \RuntimeException('Serverdatei-Sicherungsnachweis konnte nicht geschrieben werden.');
        }
        return $result;
    }
}

class Vmmjpa extends Jpa { use VmmOriginalEntries; }
if (class_exists(__NAMESPACE__ . '\\Zip')) {
    class Vmmzip extends Zip { use VmmOriginalEntries; }
}
