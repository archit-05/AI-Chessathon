#!/bin/bash
# Single-item screens on the VM at 5 s (100 games each): SEE pruning alone, then the rescaled
# correction history alone. Generators pause during each.
cd "$(dirname "$0")/.." || exit 1
bash tools/vm_gate.sh bini_v5 bini_v4final 100 seep_only 5000 50 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1
bash tools/vm_gate.sh bini_v5 bini_v4final 100 corr_v2_only 5000 50 BINI_CORR=1 BINI_CONT=0 BINI_SEEP=0
echo "VM SCREENS DONE"
