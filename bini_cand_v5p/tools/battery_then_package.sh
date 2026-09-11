#!/bin/bash
# After the proxies: full battery on bini_v4final on a quiet Mac, then package, byte-check and a
# fresh-extraction game. Every step logs; nothing here uploads.
cd "/Users/architbhardwaj/Desktop/AI Chessathon/bini_v4" || exit 1
PY=../aichessathon-starter/.venv/bin/python
until [ -f ../data/net_decided ]; do sleep 60; done
while true; do l=$(uptime | sed 's/.*load averages*: *//' | cut -d' ' -f1 | tr -d ','); ok=$($PY -c "print(1 if float('$l') <= 3 else 0)"); [ "$ok" = "1" ] && break; sleep 60; done
bash tools/battery.sh ../bini_v4final > ../data/battery_v4final.log 2>&1
echo "$(date '+%F %T') battery done"; grep -E "init|ok|passed|tactics|regression|harvest|results|min clock|median|CHECKMATE|Error|Traceback|FAIL" ../data/battery_v4final.log | head -40
cd ../bini_v4final && bash tools/package.sh > ../data/package_v4final.log 2>&1 && tail -3 ../data/package_v4final.log
stamp=$(date '+%m%d_%H%M'); cp submission.zip "../submission_v4_${stamp}.zip"; shasum -a 256 "../submission_v4_${stamp}.zip" | cut -c1-16
# byte-check: every file in the zip identical to the sources
rm -rf /tmp/v4extract && mkdir -p /tmp/v4extract && unzip -q submission.zip -d /tmp/v4extract && for f in agent.py bini_board.py bini_engine.py bini_eval.py bini_magics.py bini_nnue.py bini_search.py nnue.safetensors book.json; do cmp -s "$f" "/tmp/v4extract/$f" && echo "same $f" || echo "DIFFERENT $f"; done
# fresh-extraction game vs the minimax baseline at 30 s + 0.5 s, through the harness
cd ../aichessathon-starter && .venv/bin/python -m harness.play --white /tmp/v4extract --black baselines/minimax --base-ms 30000 --inc-ms 500 2>&1 | grep -E "result|Result|won|draw|termination|Termination" | head -3
echo "$(date '+%F %T') package step done: ../submission_v4_${stamp}.zip"
