---
name: model
description: Which model this agent runs on — Claude (default) or a measured open model via OpenRouter — switch and switch back in one command, with a live probe. Use when the USER wants to change model, asks for a cheaper or Claude-independent run, or asks what you run on.
---

# Skill — `model`

**Invoke when** the USER says "switch to DeepSeek", "run on a cheaper model", "back to Claude", or asks what you run on.

This switches **this agent** (this repo) only. The shared Claude login (`~/.claude`) is never touched, so other agents on the same machine stay on Claude. To switch another agent, ask **that** agent.

## Step 1 — The tool

If `.mentat/bin/mentat_model.py` is missing (it is not committed):

```bash
mkdir -p .mentat/bin
for f in mentat_model.py mentat_model_cfg.py mentat-models.json; do curl -fsSL https://raw.githubusercontent.com/lipi4242/mentat/v0.6.0/reference/manifest/$f -o .mentat/bin/$f; done
```

## Step 2 — What you recommend

`python3 .mentat/bin/mentat_model.py list` — recommend **measured** models only, with the line's note (score against Opus, price). If the USER asks for another one, say it is not measured; use `--force` only on an explicit request.

## Step 3 — The key

The USER **never types a command**: you talk in plain language, you run the commands.

`python3 .mentat/bin/mentat_model.py status` → if `KEY missing`:

- Ask them to create a **separate, credit-limited** key for this agent on openrouter.ai.
- **If you run on the same Mac they sit at:** ask them to copy the key to the clipboard and say "done". Then YOU run `python3 .mentat/bin/mentat_model.py key --clipboard` — the key never enters the conversation. Afterwards ask them to copy something else.
- **For a remote agent** (reachable only by message): say honestly that a key sent in a message stays in the transcript and the channel; if they still want it, they send it **privately** (never in a group), and you pass it on stdin (`printf '%s\n' "<key>" | python3 .mentat/bin/mentat_model.py key`). Suggest a credit limit on the key.

Never echo the key back, and never write it to a file yourself.

## Step 4 — Switch

**Before the switch, tell the USER:** from now on everything this agent reads (brain, files, conversation) goes to OpenRouter and the provider it routes to. Ask them to set openrouter.ai **Settings → Privacy**: zero-data-retention endpoints only, and no providers that train on inputs.

`python3 .mentat/bin/mentat_model.py use <model-id>` — sets this repo's `.claude/settings.local.json` (git-ignored, 0600) and checks with a live probe that the answer really comes from the requested model. If not, it restores everything (`ROLLED BACK`) and the agent stays on its previous model: say so, do not work around it.

## Step 5 — Restart (yours to handle too)

The running session keeps its old model. The tool's last line says what happens:

- `RESTART in 20 s` (always-on agent): the tool scheduled your restart from outside. Tell the USER **right away**: "I'll restart on the new model in half a minute and report back". In the new session's first answer run `status` and say what you run on.
- `NEXT … no fleet command`: this machine has no fleet; ask the agent that deployed you to restart you. Never ask the USER for a command.
- `NEXT tell the USER…` (interactive session): say simply "close this window and open a new one in this folder".

Never restart your own unit from your own session (`systemctl restart`): it kills you mid-command.

## Step 6 — Back to Claude

`python3 .mentat/bin/mentat_model.py use claude` — removes only its own keys; then the same restart, handled the same way by you.

## Tell the USER

One or two lines: what you run on now, what it costs per the measurement, what changed (this agent only), and the next step (restart). No JSON, no token.
