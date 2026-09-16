"""Guard deployment ordering, artifact scope and fixed component versions."""
import re
import unittest
from support import ROOT, PARSED, pipeline_config

class PipelineTests(unittest.TestCase):
    def test_pipeline_rules_do_not_depend_on_disabled_variable_inheritance(self):
        for path in ROOT.glob('templates/*.yml'):
            body = PARSED[str(path)][-1]
            for name, job in body.items():
                if not isinstance(job, dict) or job.get('inherit', {}).get('variables') is not False:
                    continue
                unavailable = set(body.get('variables', {})) - set(job.get('variables', {}))
                for rule in job.get('rules', []):
                    referenced = set(re.findall(r'\$([A-Z][A-Z0-9_]*)', rule.get('if', '')))
                    with self.subTest(pipeline=path.name, job=name):
                        self.assertFalse(unavailable & referenced,
                                         f'Rule reads excluded variables: {unavailable & referenced}')

    def test_deployed_integration_suites_wait_for_every_deployable(self):
        for path in ('internal/java-deploy.yml', 'internal/java-release.yml'):
            body = pipeline_config(path, {'deployment-timeout': '8m'})
            for name in ('cucumber-dev', 'cucumber-ui'):
                needs = {need['job']: need for need in body[name]['needs']}
                self.assertEqual({'helm-deploy', 'helm-deploy-ui'}, set(needs))
                self.assertFalse(needs['helm-deploy'].get('optional', False))
            self.assertTrue(body['cucumber-dev']['needs'][1]['optional'])
            for include in body['include']:
                if include.get('component', '').endswith('/helm-deploy@1.2.0'):
                    self.assertEqual('8m', include['inputs']['timeout'])
        parent = pipeline_config(overrides={'deployment-timeout': '8m'})
        for include in parent['include']:
            if include.get('component', '').endswith(('/deployment-select@1.2.0', '/release-reserve@1.2.0')):
                self.assertIn("deployment-timeout: '8m'", include['inputs']['pipeline-config'])

    def test_standard_pipeline_fetches_only_needed_artifacts(self):
        parent = pipeline_config()
        for name in ('build', 'build-ui', 'test-ui', 'configure-deploy'):
            self.assertEqual([], parent[name]['dependencies'])
            self.assertNotIn('needs', parent[name], 'Keep stage barriers, including release checks')
        for name in ('dependency-check', 'publish-maven', 'publish-image', 'publish-chart', 'publish-ui-chart'):
            self.assertTrue(all(need['artifacts'] is False for need in parent[name]['needs']))
        self.assertEqual([{'job': 'build-ui', 'artifacts': True},
                          {'job': 'publish-maven', 'artifacts': False}], parent['publish-ui-image']['needs'])


    def test_all_external_dependencies_use_the_same_fixed_component_release(self):
        versions = set()
        for path in [*ROOT.glob('templates/*.yml'), *ROOT.glob('internal/*.yml')]:
            for entry in PARSED[str(path)][-1].get('include', []):
                if 'component' in entry:
                    versions.add(entry['component'].rsplit('@', 1)[1])
                elif 'project' in entry:
                    versions.add(entry['ref'])
        self.assertEqual({'1.2.0'}, versions)

    def test_compositions_reserve_distinct_output_prefixes(self):
        for path in ('templates/java-service.yml', 'internal/java-deploy.yml', 'internal/java-release.yml'):
            owners = {}
            for entry in pipeline_config(path)['include']:
                if 'component' not in entry:
                    continue
                component = entry['component'].rsplit('/', 1)[1].split('@')[0]
                inputs = entry.get('inputs', {})
                prefix = inputs.get('output-prefix', component.upper().replace('-', '_'))
                job = inputs.get('job-name', component)
                self.assertNotIn(prefix, owners, f'{path}: {prefix} shared by {owners.get(prefix)} and {job}')
                owners[prefix] = job

if __name__ == '__main__':
    unittest.main()
