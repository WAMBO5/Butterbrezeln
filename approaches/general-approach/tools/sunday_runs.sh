#!/bin/zsh
# Sunday: N independent Sonnet pipeline samples on the held-out case, each in its own data dir, then an Opus
# FULL-mode replay from match of each one. Every output gets the exemption clauses and check_heldout, and lands
# in $BASE/upload/ ready for upload. Paid: about $5 per Sonnet run + $6.5 per replay (3 samples: ~$32).
#
#   tools/sunday_runs.sh [case_dir] [samples]        DRY=1 sunday_runs.sh ...   prints the commands only
#
# Run it after `uv run certivity build-corpus --extract-missing --cards` has finished,
# because each sample copies data/catalog.sqlite, data/obligations.sqlite and data/cards.
# Dev evidence for the recipe: Sonnet run 5 74.0% -> Opus replay 74.7% -> +ex 75.4% -> Opus FULL replay +ex 76.9%.
set -u
ROOT=${CERTIVITY_ROOT:-${0:A:h:h}}   # the approach folder: this script lives in tools/
CASE=${1:-$ROOT/industrial-ai-hackathon/cases/heldout-front-bumper}
N=${2:-3}
CID=$(basename $CASE)
BASE=${BASE:-$ROOT/data/sunday}   # data/general-approach/sunday/: git-ignored, and the UI shows its runs
EK=$ROOT/tools/evalkit
X() { if [ -n "${DRY:-}" ]; then echo "+ $*"; else eval "$@"; fi }
cd $ROOT
X mkdir -p $BASE/upload

finish() {  # <sample> <variant> <run_dir>: exemptions + check, one READY/FAILED line
  local out=$BASE/upload/$CID-$1-$2-ex.json
  if [ -z "${DRY:-}" ] && [ ! -s "$3/submission.json" ]; then echo "FAILED $1 $2: no submission in $3"; return 1; fi
  X uv run python $EK/add_exemptions.py $out $3/submission.json ">/dev/null"
  local chk=$([ -n "${DRY:-}" ] && echo dry || uv run python $EK/check_heldout.py $out --case $CID 2>&1 | tail -1)
  echo "READY $1 $2: $out ($([ -n "${DRY:-}" ] || python3 -c "import json;print(len(json.load(open('$out'))['requirements']))") requirements; check: $chk)"
}

chain() {  # one sample: Sonnet run, then the Opus FULL replay of it
  local n=$1 D=$BASE/$1
  X CERTIVITY_DATA_DIR=$D CERTIVITY_COST_MODE=reduced CERTIVITY_MAX_COST_USD=30 uv run certivity run $CASE ">" $D/run.log "2>&1"
  local R=$(print -l $D/runs/2026*-$CID(N) | head -1)
  [ -n "${DRY:-}" ] && R=$D/runs/'<sonnet run>'
  finish $n sonnet $R || return 1
  X CERTIVITY_DATA_DIR=$D ANTHROPIC_MODEL=claude-opus-5-5 CERTIVITY_COST_MODE=full CERTIVITY_MAX_COST_USD=20 uv run python tools/replay_from_match.py $R ">" $D/replay.log "2>&1"
  local R2=$(print -l $D/runs/2026*-$CID(N) | tail -1)
  [ -n "${DRY:-}" ] && R2=$D/runs/'<opus replay>'
  [ "$R2" = "$R" ] && { echo "FAILED $n opus: no replay run (see $D/replay.log)"; return 1; }
  finish $n opus $R2
}

for i in $(seq 1 $N); do
  D=$BASE/s$i
  X mkdir -p $D/runs
  X sqlite3 $ROOT/data/catalog.sqlite "'.backup $D/catalog.sqlite'"
  X sqlite3 $ROOT/data/obligations.sqlite "'.backup $D/obligations.sqlite'"
  X rm -rf $D/cards "&&" cp -RL $ROOT/data/cards $D/
done
for i in $(seq 1 $N); do
  chain s$i &
  sleep 2   # distinct run ids
done
wait
files=($BASE/upload/$CID-*-ex.json(N))
echo "ALL DONE: ${#files} files in $BASE/upload/"
