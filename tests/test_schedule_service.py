import os,sys,tempfile,unittest,sqlite3,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import schedule_service as tasks
class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        def db():
            c=sqlite3.connect(self.root/'fixture.db');c.row_factory=sqlite3.Row;return c
        self.db=db
        for p in (patch.object(tasks,'db',db),patch.object(tasks,'DATA',self.root),patch.object(tasks,'project',return_value={'slug':'fixture'})):
            p.start();self.addCleanup(p.stop)
        tasks.init()
        with db() as c:c.execute('DELETE FROM scheduled_tasks')
        self.value={'name':'Weekly fixture','kind':'snapshot','frequency':'weekly','weekday':6,'time':'09:00','timezone':'Europe/Berlin','projects':['fixture'],'enabled':False}
    def stamp(self,value):return dt.datetime.fromisoformat(value).timestamp()
    def test_weekly_time_respects_local_timezone(self):
        value=tasks.next_time(self.value,self.stamp('2026-10-30T08:00:00+00:00'))
        self.assertEqual(value,self.stamp('2026-11-01T08:00:00+00:00'))
    def test_spring_gap_is_normalized_to_valid_time(self):
        value={**self.value,'frequency':'daily','time':'02:30'}
        self.assertEqual(tasks.next_time(value,self.stamp('2026-03-28T23:30:00+00:00')),self.stamp('2026-03-29T01:30:00+00:00'))
    def test_fall_repeat_does_not_schedule_a_past_instant(self):
        value={**self.value,'frequency':'daily','time':'02:30'}
        self.assertEqual(tasks.next_time(value,self.stamp('2026-10-25T01:15:00+00:00')),self.stamp('2026-10-26T01:30:00+00:00'))
    def test_paused_tasks_persist_and_do_not_run(self):
        ident=tasks.save(self.value)['id']
        with self.db() as c:c.execute('UPDATE scheduled_tasks SET next_run=0')
        with patch.object(tasks,'start') as start:tasks.tick()
        start.assert_not_called();self.assertEqual(tasks.listing()[0]['id'],ident)
        self.assertFalse(tasks.listing()[0]['enabled'])
    def test_invalid_action_and_clock_are_rejected(self):
        for update in ({'kind':'shell'},{'time':'24:30'},{'timezone':'invalid/timezone'},{'weekday':8}):
            with self.subTest(update=update),self.assertRaises(ValueError):tasks.save({**self.value,**update})
    def test_edit_retains_identity_and_delete_does_not_reseed_defaults(self):
        ident=tasks.save(self.value)['id'];tasks.save({**self.value,'id':ident,'name':'Edited'})
        self.assertEqual(tasks.listing()[0]['name'],'Edited');tasks.delete(ident);self.assertEqual(tasks.listing(),[])
    def test_stopped_projects_are_reported_as_skipped_without_failed_job(self):
        import types
        with self.db() as c:c.execute('CREATE TABLE jobs(id TEXT,resource TEXT,kind TEXT,status TEXT,message TEXT,created INTEGER,finished INTEGER)')
        ident=tasks.save({**self.value,'projects':[]})['id']
        def thread(*args,**kwargs):return types.SimpleNamespace(start=lambda:kwargs['target']())
        with patch.object(tasks,'records',return_value=[{'slug':'offline','status':'stopped','restore':0}]),patch.object(tasks.threading,'Thread',side_effect=thread),patch.object(tasks,'job') as child:
            value=tasks.start(ident)
        child.assert_not_called()
        with self.db() as c:row=c.execute('SELECT status,message FROM jobs WHERE id=?',(value['job'],)).fetchone()
        self.assertEqual(row['status'],'done');self.assertIn('Übersprungen',row['message']);self.assertIn('offline',row['message'])
