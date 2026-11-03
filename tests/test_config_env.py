import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from config_env import config_env


class ConfigEnvironmentTests(unittest.TestCase):
    def test_precedence_legacy_fallback_and_default(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(config_env('HOST_DATA','default'),'default')
            os.environ['VMM_HOST_DATA']='/old'
            self.assertEqual(config_env('HOST_DATA'),'/old')
            os.environ['TENTACLE_HOST_DATA']='/new'
            self.assertEqual(config_env('HOST_DATA'),'/new')
            os.environ['TENTACLE_HOST_DATA']=''
            self.assertEqual(config_env('HOST_DATA'),'/old')

    def test_runtime_project_accepts_new_name(self):
        from shared_runtime import stack
        with patch.dict(os.environ,{'TENTACLE_RUNTIME_PROJECT':'custom-tentacle','VMM_RUNTIME_PROJECT':'legacy'}):
            self.assertEqual(stack('/host','test')['name'],'custom-tentacle')
