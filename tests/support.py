"""Local composition fixtures; GitLab remains the authoritative YAML compiler."""
import copy
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'c' * 40
RUBY_YAML = 'require "yaml"; require "json"\nYAML.add_domain_type("", "reference") { |_, value| {"$reference" => value} }\nputs JSON.generate(ARGV.to_h { |p| [p, YAML.load_stream(File.read(p))] })'
FILES = [p for folder in ('templates', 'internal', 'shared', 'config') for p in (ROOT / folder).glob('*.yml')]
FILES += [ROOT / '.gitlab-ci.yml']
PARSED = json.loads(subprocess.check_output(['ruby', '-e', RUBY_YAML, *map(str, FILES)], text=True))

def interpolate(documents, overrides=None):
    """Small fixture expander; GitLab CI Lint remains the authoritative validator."""
    header, body = copy.deepcopy(documents)
    inputs = {key: spec.get("default", "test-value") for key, spec in header["spec"]["inputs"].items()}
    assert not (set(overrides or {}) - inputs.keys()), "Unknown input"
    inputs.update(overrides or {})
    def substitute(value):
        if isinstance(value, dict):
            return {substitute(key): substitute(item) for key, item in value.items()}
        if isinstance(value, list):
            return [substitute(item) for item in value]
        if isinstance(value, str):
            whole = re.fullmatch(r"\$\[\[ inputs\.([a-z-]+) \]\]", value)
            if whole:
                return inputs[whole[1]]
            # Fixture values use literal project names; GitLab validates expand_vars itself.
            value = value.replace("$[[ component.sha ]]", REVISION)
            return re.sub(r"\$\[\[ inputs\.([a-z-]+)(?: \| expand_vars)? \]\]",
                          lambda match: str(inputs[match[1]]).lower() if isinstance(inputs[match[1]], bool)
                          else str(inputs[match[1]]), value)
        return value
    return substitute(body)

def pipeline_config(path='templates/java-service.yml', overrides=None):
    """Expand local composition files for assertions; leave component includes intact."""
    documents = PARSED[str(ROOT / path)]
    body = interpolate(documents, overrides) if len(documents) == 2 else copy.deepcopy(documents[0])
    includes = []
    result = {}

    def merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = copy.deepcopy(value)

    for entry in body.pop('include', []):
        local = entry.get('local', '').lstrip('/')
        if local:
            child = pipeline_config(local, entry.get('inputs'))
            includes.extend(child.pop('include', []))
            merge(result, child)
        else:
            includes.append(entry)
    merge(result, body)
    result['include'] = includes
    return result
