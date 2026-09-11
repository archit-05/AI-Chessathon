#!/bin/bash
# On the x86 box: pause the generators (SIGSTOP), run a command in a given directory, resume them.
#   bash ~/chess/bini_v5/tools/x86_quiet_run.sh <dir> <command...>
DIR=$1; shift
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true
trap 'pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -x stockfish || true' EXIT
cd "$DIR" && "$@"
