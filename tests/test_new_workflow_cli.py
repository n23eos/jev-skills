"""Installed-example and decision paths without live provider calls."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jev_skills import cli
from jev_skills.core import QUESTIONS, Client, MODEL

NEW = ('citation', 'ci', 'review', 'tool', 'issue', 'value', 'eval-gap')


class WorkflowCliTests(unittest.TestCase):
    def call(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(list(args)), 0)
        return json.loads(output.getvalue())

    def test_all_packaged_examples_preview_offline(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'JEV_SKILLS_HOME': directory, 'JEV_SKILLS_CHILD': ''}), patch.object(cli, 'Client', side_effect=AssertionError('network')):
            for workflow in NEW:
                with self.subTest(workflow=workflow):
                    self.assertIn(workflow, QUESTIONS)
                    example = self.call('example', workflow)
                    path = Path(directory) / (workflow + '.json')
                    path.write_text(json.dumps(example))
                    result = self.call('decide', workflow, '--input', str(path))
                    self.assertEqual(result['mode'], 'dry_run')
                    self.assertIs(result['network'], False)
                    self.assertIn('none', result['requests'][0]['questions']['selection']['criteria'])
            self.assertFalse((Path(directory) / 'usage.jsonl').exists())

    def test_private_and_disabled_new_workflows_do_not_read_input(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'JEV_SKILLS_HOME': directory, 'JEV_SKILLS_CHILD': ''}), patch.object(cli, 'read_text', side_effect=AssertionError('input read')), patch.object(cli, 'Client', side_effect=AssertionError('network')):
            for workflow in NEW:
                self.assertEqual(self.call('decide', workflow, '--input', 'absent', '--private', '--live')['reason'], 'private')
                self.assertEqual(self.call('decide', workflow, '--input', 'absent', '--automatic')['reason'], 'disabled')

    def test_nonshrinking_group_preview_matches_live_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'JEV_SKILLS_HOME': directory, 'JEV_SKILLS_CHILD': ''}), patch.object(cli, 'Client', side_effect=AssertionError('network')):
            path = Path(directory) / 'large.json'
            path.write_text(json.dumps({'request': 'x' * 96000, 'candidates': [
                {'id': 'one', 'description': 'x' * 1800},
                {'id': 'two', 'description': 'y' * 1800}]}))
            result = self.call('decide', 'skill', '--input', str(path))
            self.assertEqual((result['route'], result['reason']), ('fallback', 'payload_too_large'))
            self.assertNotIn('requests', result)

    def test_live_path_retains_local_evidence_and_private_metrics(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'JEV_SKILLS_HOME': directory, 'JEV_SKILLS_CHILD': ''}):
            for workflow in NEW:
                with self.subTest(workflow=workflow):
                    sample = self.call('example', workflow)
                    path = Path(directory) / 'input.json'
                    path.write_text(json.dumps(sample))
                    def transport(payload, timeout):
                        options = payload['questions']['selection']['criteria']
                        choice = next(key for key in options if key != 'none')
                        return {'model': MODEL, 'usage': {'input_tokens': 10, 'output_tokens': 1},
                            'answers': {'selection': {'type': 'choice', 'choice': choice, 'confidence': .95,
                            'probabilities': {key: float(key == choice) for key in options}}}}
                    with patch.object(cli, 'Client', return_value=Client(transport)):
                        result = self.call('decide', workflow, '--input', str(path), '--live')
                    self.assertEqual(result['route'], 'recommendation')
                    self.assertEqual(result['calls'], 1)
                    if workflow == 'citation':
                        self.assertEqual(result['citation_evidence']['excerpt'], sample['source']['excerpt'])
                    if workflow == 'value':
                        selected = result['selected_value']
                        self.assertEqual(selected['value'], sample['source'][selected['start']:selected['end']])
            events = [json.loads(line) for line in (Path(directory) / 'usage.jsonl').read_text().splitlines()]
            self.assertEqual(len(events), len(NEW))
            self.assertTrue(all(not ({'request', 'selected', 'citation_evidence', 'selected_value'} & event.keys()) for event in events))
