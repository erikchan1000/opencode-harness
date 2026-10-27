"""Validate the omp-native worked examples under skills/create-harness/examples/.

Each ```json block in examples/omp-*.md must be immediately preceded by a
marker line `<!-- schema: <name> -->`, where <name> is one of the schemas under
skills/create-harness/schemas/ (without `.schema.json`) or `none` for JSON that
is not a schema document (task-call / todo arguments). Blocks with a schema
name must validate against that schema.

The omp examples must also be free of Claude-Code / opencode vocabulary that
has no omp equivalent (Task(...) calls, task_id, subagent_type, SendMessage,
scratchpad files, plan/ paths).
"""

import json
import re
from pathlib import Path

import jsonschema
import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "create-harness"
SCHEMAS = SKILL / "schemas"
EXAMPLES = sorted((SKILL / "examples").glob("omp-*.md"))

BLOCK = re.compile(r"(?P<pre>[^\n]*)\n```json\n(?P<body>.*?)\n```", re.S)
MARKER = re.compile(r"^<!-- schema: ([a-z-]+) -->$")
# Any opening fence whose info string starts with "json" (```json, ```jsonc,
# ``` json, ```json5 ...). Every one of these must be a block BLOCK parses,
# otherwise a slightly malformed fence would silently escape validation.
JSON_FENCE = re.compile(r"^```\s*json\S*\s*$", re.M | re.I)

FORBIDDEN = ["Task(", "task_id", "subagent_type", "SendMessage", "scratch", "plan/"]


def _blocks():
    for path in EXAMPLES:
        for i, m in enumerate(BLOCK.finditer(path.read_text())):
            yield pytest.param(path, m.group("pre"), m.group("body"), id=f"{path.name}#{i}")


def _schema_names():
    return sorted(p.name[: -len(".schema.json")] for p in SCHEMAS.glob("*.schema.json"))


def test_examples_exist():
    assert {p.name for p in EXAMPLES} == {"omp-mobile-bugs.md", "omp-failure-recovery.md"}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_json_fence_is_parsed(path):
    text = path.read_text()
    fences = len(JSON_FENCE.findall(text))
    parsed = len(BLOCK.findall(text))
    assert fences > 0, f"{path.name}: no ```json blocks to validate"
    assert fences == parsed, (
        f"{path.name}: {fences} json-ish fences but only {parsed} well-formed ```json blocks"
    )


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
@pytest.mark.parametrize("token", FORBIDDEN)
def test_no_forbidden_tokens(path, token):
    hits = [
        f"{n}: {line}"
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if token.lower() in line.lower()
    ]
    assert not hits, f"{path.name} contains forbidden token {token!r}:\n" + "\n".join(hits)


def test_every_schema_is_exercised():
    used = set()
    for path in EXAMPLES:
        for m in BLOCK.finditer(path.read_text()):
            marker = MARKER.match(m.group("pre").strip())
            if marker:
                used.add(marker.group(1))
    missing = set(_schema_names()) - used
    assert not missing, f"no omp example validates against: {sorted(missing)}"


@pytest.mark.parametrize("path,pre,body", _blocks())
def test_json_block_validates(path, pre, body):
    m = MARKER.match(pre.strip())
    assert m, f"{path.name}: json block lacks a `<!-- schema: X -->` marker"
    name = m.group(1)
    data = json.loads(body)
    if name == "none":
        return
    assert name in _schema_names(), f"unknown schema {name}"
    schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
