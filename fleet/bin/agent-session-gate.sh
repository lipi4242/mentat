#!/usr/bin/env bash
# agent-session-gate.sh — transcript-méret kapu az ágens-indítás elé.
#
# MIÉRT: a Claude Code memóriaigénye együtt nő a resume-olt transcripttel.
# 2026-08-07-én egy ágens transcriptje 153 MB-ra hízott, a box 3,7 GB RAM-ján ez
# OOM-ot okozott, ami magát a systemd user managert is kivitte — és vele az
# összes watchdogot. Tíz órás néma kiesés lett belőle.
#
# MIT CSINÁL: indulás előtt megnézi, mekkora a resume-célpont transcript.
# A küszöb felett FÉLRETESZI a session.id-t (nem törli), így a launcher friss
# sessiont indít. Az ágens állapota úgyis a repóban, a `data/`-ban és a
# közös DB-ben él, nem a chat-előzményben.
#
# HASZNÁLAT (ExecStartPre a unitban):
#   ExecStartPre=%h/bin/agent-session-gate.sh demo-agent
# ahol az argumentum a ~/.config/<NÉV>/session.id könyvtárneve.
#
# Küszöb: AGENT_TRANSCRIPT_MAX_MB (alap 10).
# Kilépési kód mindig 0 — ez kapu, nem gate: soha ne akadályozza az indulást.

set -uo pipefail

AGENT="${1:-}"
MAX_MB="${AGENT_TRANSCRIPT_MAX_MB:-10}"
SID_FILE="$HOME/.config/${AGENT}/session.id"

log() { echo "session-gate[${AGENT:-?}]: $*"; }

[ -n "$AGENT" ] || { log "nincs ágensnév megadva — kihagyva"; exit 0; }
[ -f "$SID_FILE" ] || { log "nincs session.id — friss indítás lesz"; exit 0; }

SID="$(tr -d '[:space:]' < "$SID_FILE" 2>/dev/null || true)"
[ -n "$SID" ] || { log "üres session.id — kihagyva"; exit 0; }

# A transcript bárhol lehet a projects/ alatt; az elsőt vesszük.
TRANSCRIPT="$(ls -1 "$HOME"/.claude/projects/*/"$SID".jsonl 2>/dev/null | head -1 || true)"
if [ -z "$TRANSCRIPT" ]; then
    log "a(z) $SID transcriptje nincs meg — a launcher úgyis frisset indít"
    exit 0
fi

BYTES="$(stat -c %s "$TRANSCRIPT" 2>/dev/null || echo 0)"
MAX_BYTES=$(( MAX_MB * 1024 * 1024 ))
MB=$(( BYTES / 1024 / 1024 ))

if [ "$BYTES" -le "$MAX_BYTES" ]; then
    log "transcript ${MB} MB (küszöb ${MAX_MB} MB) — resume marad"
    exit 0
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
mv -f "$SID_FILE" "${SID_FILE}.retired-${STAMP}" 2>/dev/null \
    && log "transcript ${MB} MB > ${MAX_MB} MB → FRISS INDÍTÁS (session.id félretéve: ${SID_FILE}.retired-${STAMP})" \
    || log "transcript ${MB} MB, de a session.id-t nem sikerült félretenni — resume marad"

# A régi retired-jelölőkből csak az utolsó ötöt tartjuk meg.
ls -1t "${SID_FILE}".retired-* 2>/dev/null | tail -n +6 | xargs -r rm -f

exit 0
