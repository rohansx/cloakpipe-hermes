"""Snapshot Hermes's built-in tool schemas (names, argument types, enums, required) so
``gen_contract.py`` can write a contract that covers every tool.

Runs inside Hermes's own runtime, which only `hermes --run-module` provides:

    cp tools/dump_hermes_tools.py "$HERMES_INSTALL/_cp_dump.py"
    CP_DUMP_OUT=contracts/hermes-tools.json hermes --run-module _cp_dump
    rm "$HERMES_INSTALL/_cp_dump.py"

Descriptions are dropped: the snapshot is about shapes, not prose.
"""

import json
import os

from tools.registry import discover_builtin_tools, registry

KEEP = ("type", "enum", "required", "properties", "items", "minimum", "maximum", "minLength", "maxLength",
        "minItems", "maxItems", "anyOf", "const")


def trim(schema):
    if isinstance(schema, dict):
        return {k: trim(v) for k, v in schema.items() if k in KEEP}
    if isinstance(schema, list):
        return [trim(v) for v in schema]
    return schema


discover_builtin_tools()
entries = getattr(registry, "_tools", None) or getattr(registry, "_entries", None) or {}
tools = {}
for name, entry in entries.items():
    schema = getattr(entry, "schema", None) if not isinstance(entry, dict) else entry.get("schema")
    toolset = getattr(entry, "toolset", None) if not isinstance(entry, dict) else entry.get("toolset")
    params = (schema or {}).get("parameters") or (schema or {}).get("input_schema") or {}
    tools[name] = {"toolset": toolset, "parameters": trim(params)}

out = os.environ.get("CP_DUMP_OUT", "hermes-tools.json")
with open(out, "w") as f:
    json.dump({"hermes": os.environ.get("HERMES_VERSION", ""), "tools": dict(sorted(tools.items()))}, f, indent=1)
print(f"{len(tools)} tools -> {out}")
