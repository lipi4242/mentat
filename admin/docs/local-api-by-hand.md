# The local API by hand

Background for a quick look without an agent. The server is the one
`connect --local` installed (README *Connect your agent*), or `npm run dev:local`
in `worker/` after `npm run migrate:local`. In `worker/`:

```bash
curl -s localhost:8787/api/health              # → {"ok":true,"service":"mentat-admin"}
npm run mint-token -- --agent demo --scope cases:write --days 7 --local
TOKEN=mentat_…                                 # the token it printed (shown once)
ID=01JAB6Z9Q3M8K7T2V5W4X1Y0RS                  # the writer makes the case id (a ULID)
curl -s -X PUT localhost:8787/api/cases/$ID -H "X-Mentat-Token: $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"title":"Gas bill","recurrence":"monthly:10","anchor_at":"2026-10-10"}'   # → {"id":"01JAB…","due_at":"2026-10-10","version":1,…}
curl -s "localhost:8787/api/cases/due?until=2026-12-31" -H "X-Mentat-Token: $TOKEN"  # → 10-10 (closable), 11-10, 12-10
curl -s -X POST localhost:8787/api/cases/$ID/occurrences -H "X-Mentat-Token: $TOKEN" \
     -H 'Content-Type: application/json' -d '{"due_at":"2026-10-10"}'                # → {… "due_at":"2026-11-10","version":2 …}
npm run revoke-token -- --agent demo --local   # the token stops working

Signing in: `npm run login-link` (one-time link). For UI development with hot
reload, `npm --prefix admin run dev` serves on http://localhost:5173 and
proxies `/api` to :8787; with `OTP_DRY_RUN=1` the sign-in code is also printed
in the server's log.
