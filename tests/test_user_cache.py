import os,sys,tempfile,unittest,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import project_workspace as workspace
class UserCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for p in (patch.object(workspace,'DATA',self.root),patch.object(workspace,'project',return_value={'cms':'wordpress'})):
            p.start();self.addCleanup(p.stop)
    def test_repeated_views_use_one_initial_cms_query(self):
        with patch('project_service.user_action',return_value=[{'ID':1,'user_login':'fixture'}]) as query:
            first=workspace.users('fixture');second=workspace.users('fixture')
        query.assert_called_once_with('fixture',{'action':'list'});self.assertEqual(first,second)
    def test_explicit_refresh_replaces_persisted_users(self):
        with patch('project_service.user_action',side_effect=[[{'ID':1}],[{'ID':2}]]) as query:
            workspace.users('fixture');updated=workspace.users('fixture',refresh=True);cached=workspace.users('fixture')
        self.assertEqual(query.call_count,2);self.assertEqual(updated['users'],[{'ID':2}]);self.assertEqual(cached,updated)
    def test_default_change_does_not_query_cms(self):
        with patch('project_service.user_action',return_value=[{'ID':1}]) as query:
            workspace.users('fixture');(self.root/'projects/fixture/manager-user.json').write_text('{"id":1}')
            value=workspace.users('fixture')
        self.assertEqual(query.call_count,1);self.assertEqual(value['defaultUser']['id'],1)
    def test_parallel_initial_views_share_the_initial_query(self):
        def query(*args):time.sleep(.03);return [{'ID':1}]
        with patch('project_service.user_action',side_effect=query) as read,ThreadPoolExecutor(max_workers=3) as pool:
            result=list(pool.map(lambda _:workspace.users('parallel'),range(3)))
        self.assertEqual(read.call_count,1);self.assertEqual(result[0],result[2])
