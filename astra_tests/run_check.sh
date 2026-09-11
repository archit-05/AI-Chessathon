#!/bin/bash
# Run one check and propagate ITS exit status, not the pipeline's.
# `set -o pipefail` alone is not enough when the last stage is `tail`: pipefail returns the
# last NONZERO status, but a wrapper that writes `EXIT=$?` after a pipe still reads tail's.
# So the command's status is captured directly and the log is written to a file.
set -u
BUILD="$1"; SCRIPT="$2"; LABEL="${3:-run}"
PY=/tmp/chess-external-review-venv/bin/python
LOG="/tmp/check_${LABEL}_$(basename "$SCRIPT" .py).log"
BINI_DIR="$BUILD" LABEL="$LABEL" "$PY" "astra_tests/$SCRIPT" > "$LOG" 2>&1
rc=$?
tail -n "${TAIL_N:-12}" "$LOG"
echo "---- $SCRIPT on $BUILD : exit $rc ----"
exit $rc
