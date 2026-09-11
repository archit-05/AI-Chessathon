#!/bin/bash
# Screen the three V5 search items one at a time against V4 on the x86 box (150 games at 5 s each):
# correction history alone, continuation history alone, SEE pruning alone.
cd "$(dirname "$0")/.." || exit 1
bash tools/x86_gate.sh bini_v5 bini_v4final 150 corr_only 5000 50 BINI_CORR=1 BINI_CONT=0 BINI_SEEP=0
bash tools/x86_gate.sh bini_v5 bini_v4final 150 cont_only 5000 50 BINI_CORR=0 BINI_CONT=1 BINI_SEEP=0
bash tools/x86_gate.sh bini_v5 bini_v4final 150 seep_only 5000 50 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1
echo "SPLIT GATES DONE"
