#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd -P)
cd "$REPO_ROOT"

python3 <<'PY'
import collections
import pathlib
import re
import sys

repo_root = pathlib.Path('.').resolve()
models_dir = repo_root / 'dbt' / 'models'
macros_dir = repo_root / 'dbt' / 'macros'

failures = []

# Check for duplicate model identifiers
if models_dir.exists():
    model_names = collections.defaultdict(list)
    for path in models_dir.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {'.sql', '.py'}:
            continue
        model_names[path.stem].append(path.relative_to(repo_root))
    duplicate_models = {name: sorted(paths) for name, paths in model_names.items() if len(paths) > 1}
    if duplicate_models:
        lines = ['Duplicate dbt model identifiers detected:']
        for name in sorted(duplicate_models):
            lines.append(f'  {name}')
            for loc in duplicate_models[name]:
                lines.append(f'    - {loc}')
        failures.append('\n'.join(lines))

# Check for duplicate macro names
macro_pattern = re.compile(r"{[%]\\s*macro\\s+([A-Za-z0-9_.]+)")
if macros_dir.exists():
    macro_definitions = collections.defaultdict(list)
    for path in macros_dir.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {'.sql', '.macros'}:
            continue
        with path.open(encoding='utf-8') as handle:
            for lineno, line in enumerate(handle, 1):
                match = macro_pattern.search(line)
                if match:
                    name = match.group(1)
                    macro_definitions[name].append(f"{path.relative_to(repo_root)}:{lineno}")
    duplicate_macros = {name: sorted(locs) for name, locs in macro_definitions.items() if len(locs) > 1}
    if duplicate_macros:
        lines = ['Duplicate dbt macro names detected:']
        for name in sorted(duplicate_macros):
            lines.append(f'  {name}')
            for loc in duplicate_macros[name]:
                lines.append(f'    - {loc}')
        failures.append('\n'.join(lines))

# Check for duplicate test names across schema YAML files
schema_files = []
if models_dir.exists():
    for extension in ('*.yml', '*.yaml'):
        schema_files.extend(models_dir.rglob(extension))

if schema_files:
    test_names = collections.defaultdict(list)
    for path in schema_files:
        with path.open(encoding='utf-8') as handle:
            tests_indent_stack = []
            for lineno, raw_line in enumerate(handle, 1):
                line = raw_line.rstrip('\n')
                stripped = line.lstrip(' ')
                if not stripped or stripped.startswith('#'):
                    continue
                indent = len(line) - len(stripped)

                while tests_indent_stack and indent <= tests_indent_stack[-1]:
                    tests_indent_stack.pop()

                if stripped.startswith('tests:'):
                    tests_indent_stack.append(indent)
                    continue

                if not tests_indent_stack:
                    continue

                current_indent = tests_indent_stack[-1]
                if stripped.startswith('- name:') and indent > current_indent:
                    name = stripped[len('- name:'):].strip()
                    name = name.strip('"\'')
                    if name:
                        location = f"{path.relative_to(repo_root)}:{lineno}"
                        test_names[name].append(location)

    duplicate_tests = {name: sorted(locs) for name, locs in test_names.items() if len(locs) > 1}
    if duplicate_tests:
        lines = ['Duplicate dbt schema test names detected:']
        for name in sorted(duplicate_tests):
            lines.append(f'  {name}')
            for loc in duplicate_tests[name]:
                lines.append(f'    - {loc}')
        failures.append('\n'.join(lines))

if failures:
    print('\n\n'.join(failures))
    sys.exit(1)

print('No duplicate dbt models, macros, or schema test names detected.')
PY
PY_STATUS=$?

exit "$PY_STATUS"
