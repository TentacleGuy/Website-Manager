import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import changelog

class ChangelogTests(unittest.TestCase):
    def fixture(self,unpublished='Noch keine Änderungen.',version='1.2.3'):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);(root/'app').mkdir()
        (root/'app/release.json').write_text(json.dumps({'version':version}))
        (root/'CHANGELOG.md').write_text('# Änderungsprotokoll\n\n## [Unveröffentlicht]\n\n'+unpublished+'\n\n## [1.2.3] - 2026-10-30\n\n### Behoben\n\n- Ordnerzugriff korrigiert.\n\n## [1.2.2] - 2026-10-30\n\n- Ältere Änderung.\n',encoding='utf-8')
        return root
    def test_notes_match_only_the_released_version(self):
        root=self.fixture();text=changelog.notes(root,tag='v1.2.3')
        self.assertIn('Ordnerzugriff korrigiert.',text);self.assertNotIn('Ältere Änderung.',text);self.assertNotIn('Unveröffentlicht',text)
    def test_development_changes_are_valid_but_block_tagged_releases(self):
        root=self.fixture('### Neu\n\n- Neue Funktion.');changelog.validate(root)
        with self.assertRaisesRegex(ValueError,'offenen Änderungen'):changelog.validate(root,tag='v1.2.3')
    def test_missing_current_entry_and_wrong_tag_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'fehlt'):changelog.validate(self.fixture(version='1.2.4'))
        with self.assertRaisesRegex(ValueError,'dieselbe Version'):changelog.validate(self.fixture(),tag='v1.2.4')
    def test_duplicate_versions_wrong_order_and_invalid_dates_are_rejected(self):
        original=(self.fixture()/'CHANGELOG.md').read_text(encoding='utf-8')
        for text in (original.replace('[1.2.2]','[1.2.3]'),original.replace('[1.2.2]','[1.2.4]'),original.replace('2026-10-30','2026-02-30')):
            with self.assertRaises(ValueError):changelog.sections(text)
    def test_program_change_requires_changelog_in_same_comparison(self):
        with patch.object(changelog.subprocess,'run',return_value=SimpleNamespace(stdout='app/server.py\n')):
            with self.assertRaisesRegex(ValueError,'benötigen einen Eintrag'):changelog.check_changes(Path('.'),'a'*40)
        with patch.object(changelog.subprocess,'run',return_value=SimpleNamespace(stdout='app/server.py\nCHANGELOG.md\n')):changelog.check_changes(Path('.'),'a'*40)
    def test_first_push_and_docs_only_changes_are_allowed(self):
        with patch.object(changelog.subprocess,'run',return_value=SimpleNamespace(stdout='README.md\n')) as run:
            changelog.check_changes(Path('.'),'0'*40);run.assert_not_called();changelog.check_changes(Path('.'),'a'*40)
    def test_repository_history_validates_without_claiming_an_unreleased_version(self):
        entries,current=changelog.validate();self.assertIn(current,entries);self.assertIn('Unveröffentlicht',entries)
