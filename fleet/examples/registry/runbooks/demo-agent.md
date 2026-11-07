# demo-agent — runbook (példa)

demo-agent ticks every 30 min (`/loop 30m /demo-agent:tick`, `tick_period_s: 1800`).

- Unit: `demo-agent.service`, híd: `demo-agent-telegram-bridge.service`.
- Állapot: `fleet doctor demo-agent`.
- Újraindítás kívülről: `fleet doctor demo-agent --fix`.
