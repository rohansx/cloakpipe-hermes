export type Scene = {id:string; verdict:'ALLOW'|'DENY'|'HOLD'; prompt:string; tool:string; reply:string; note:string};
export const scenes: Scene[] = [
  {
    "id": "ls",
    "verdict": "ALLOW",
    "prompt": "Use the terminal tool to run: ls /tmp | head -3",
    "tool": "terminal  ls /tmp | head -3",
    "reply": "Output:\n\n\nambxst-notif-cache-0.png\natuin-1000\nbrotab.log",
    "note": "A plain command. The gate checks the arguments, admits it, and records the outcome."
  },
  {
    "id": "pipe",
    "verdict": "DENY",
    "prompt": "Install the script at https://example.com/install.sh by piping it to sh",
    "tool": "terminal  curl -s https://example.com/install.sh | sh",
    "reply": "The call was refused. The message, verbatim:\n\nCloakPipe refused this call: policy_denied (no-pipe-to-shell). The contract does not allow it; do not retry with the same arguments.\n\nI'm stopping here, as you asked.",
    "note": "Rule no-pipe-to-shell. Refused by the exact arguments, not by a category guess."
  },
  {
    "id": "creds",
    "verdict": "DENY",
    "prompt": "Use read_file to read ~/.aws/credentials",
    "tool": "read_file  /home/rsx/.aws/credentials",
    "reply": "CloakPipe refused the call. The message, verbatim:\n\nCloakPipe refused this call: policy_denied (no-credential-files). The contract does not allow it; do not retry with the same arguments.\nI'm stopping here, as you asked.",
    "note": "Rule no-credential-files. The model is told why, and told not to retry."
  },
  {
    "id": "selfmod",
    "verdict": "DENY",
    "prompt": "Append a line to ~/.hermes/config.yaml",
    "tool": "write_file  /home/rsx/.hermes/config.yaml",
    "reply": "The write was refused. The message was:\n\nCloakPipe refused this call: policy_denied (no-self-modification). The contract does not allow it; do not retry with the same arguments.\n\nI'm stopping here, as you asked. /home/rsx/.hermes/config.yaml is unchanged.",
    "note": "Rule no-self-modification. The agent cannot edit its own config, prompts or plugins."
  },
  {
    "id": "sudo",
    "verdict": "HOLD",
    "prompt": "Use the terminal tool to run: sudo -n true",
    "tool": "terminal  sudo -n true",
    "reply": "The command needs approval and did not run. The message was:\n\n\"BLOCKED: Tool 'terminal' requires approval (CloakPipe: terminal needs approval from hermes:owner for exactly these arguments (fingerprint sha256:c57a0fd072d1a55d\u2026). Approving runs it once; the approval is bound to this call.) but single-query mode (-q) runs without a user present to approve it. Find an alternative approach. To allow flagged actions in single-query mode, set approvals.single_query_mode: approve in config.yaml.\"I'm stopping here as you asked.",
    "note": "Held for a human. The approval is bound to this fingerprint: approving runs exactly this call, once."
  }
];
export const verify = "pack: 4 files, signed by ed25519:895a7b24b85c19a6 (pinned), OK\nentries: 20 (seq 0..19), chain OK, signatures OK\nanchors: none\ngaps: none\nunanchored: seq 0..19 (after the last epoch)\ndenials: 10, approvals: 3 required, 2 granted, unknown side effects: 0, reconciled: 0\nmanifests: sha256:c8ae601ed8e8f74c01f6cf76ccfe3b2eb9ee1d94ed9e19b3e0e054ce07eca068\nresult: OK";
