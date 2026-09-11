# Build-by-build evidence table

## Archives

| build | patches | archive SHA-256 | bini_search.py md5 |
|---|---|---|---|
| `bini_v8_ship` | (frozen baseline) | `47ace1930f8119473b49524e30652f0ae7c798e8cdad601bac07e6adebee8449` | `163cda13023d7d5aa89cc4b523c6b576` |
| `bini_astra_c2` | C2 | `92a8098b60947f1cfa8009a0297680b67eef67645e017ca215d5c9821afd842b` | `41cdc1d17d80f643fe18084325450242` |
| `bini_astra_correctness` | C2+C1 | `ef41bc8d1f3bb7e587b0ffa888afa4a3333d2c7d936a1bdde5490c2b1f902617` | `9e409ed2ec715cd0ffd141e1ceb2372d` |
| `bini_astra_v2` | C2+C1+C1b+C2b | `2c14b91fbb131dcd74f9d3fca488aacd8e3288e9a8e568017e30c834a9ac20db` | `cafa3df29a76d6a0015fd2f8bf398da3` |
| `bini_astra_v3_noc2b` | C2+C1+C1b | `93e18686bd6abfcd9da74d4f0cc178953c1b8b67ce2d29566d4a7b660a8ba98a` | `d7d19119727506640286a7249e57fad9` |
| `bini_astra_v5` | C2+C1+C1b+C2b+C1c+C1d  **FINAL CANDIDATE** | `873152525b895f69b58e934622e56aac6ea2d474b30de0d01884878f460242bc` | `2f9f4d717c6ac2609e40f8dc9a65d4c3` |
| `bini_astra_v5_noc2b` | C2+C1+C1b+C1c+C1d  (final minus C2b) | `26828c240ebcd9ae175f0af8b800131f16e26d01c21b6ae590af02cbc73174dd` | `56ead3446ea7a7e482cea91a67083995` |

## Every test result, keyed to the hash that received it

| build | bini_search.py md5 | arch | test artefact | total | passed | FAILED |
|---|---|---|---|---|---|---|
| `?` | `not recorded…` | ? | `wrapper_c1c2_candidate_normal.json` | 13 | 13 | 0 |
| `?` | `not recorded…` | ? | `wrapper_c2_only_normal.json` | 13 | 13 | 0 |
| `?` | `not recorded…` | ? | `wrapper_v8_baseline_normal.json` | 13 | 13 | 0 |
| `bini_astra  (old box: C2+C1)` | `9e409ed2ec715cd0…` | x86_64 | `c3_x86_c1c2.json` | 4 | 2 | **1** |
| `bini_astra  (old box: C2+C1)` | `9e409ed2ec715cd0…` | x86_64 | `repro_x86_c1c2.json` | 23 | 21 | 0 |
| `bini_astra  (old box: C2+C1)` | `9e409ed2ec715cd0…` | x86_64 | `suite_x86_c1c2.json` | 20 | 20 | 0 |
| `bini_astra_c2` | `41cdc1d17d80f643…` | arm64 | `repro_c2_only.json` | 23 | 15 | **6** |
| `bini_astra_correctness` | `9e409ed2ec715cd0…` | arm64 | `bench_c1c2_candidate.json` | None | None | 0 |
| `bini_astra_correctness` | `9e409ed2ec715cd0…` | arm64 | `bench_c1c2_d11.json` | None | None | 0 |
| `bini_astra_correctness` | `9e409ed2ec715cd0…` | arm64 | `bench_c1c2_d11b.json` | None | None | 0 |
| `bini_astra_correctness` | `9e409ed2ec715cd0…` | arm64 | `repro_c1c2_candidate.json` | 23 | 21 | 0 |
| `bini_astra_correctness` | `9e409ed2ec715cd0…` | arm64 | `suite_c1c2_candidate.json` | 20 | 20 | 0 |
| `bini_astra_v2` | `cafa3df29a76d6a0…` | arm64 | `repro_c1c2_v2.json` | 24 | 22 | 0 |
| `bini_astra_v2` | `cafa3df29a76d6a0…` | arm64 | `suite_c1c2_v2.json` | 20 | 20 | 0 |
| `bini_astra_v2` | `cafa3df29a76d6a0…` | arm64 | `terminal_v2.json` | 7 | 3 | **3** |
| `bini_astra_v2` | `cafa3df29a76d6a0…` | arm64 | `v2_c1c2_v2.json` | 12 | 12 | 0 |
| `bini_astra_v4` | `65d23893f9126008…` | arm64 | `terminal_v4.json` | 8 | 6 | **1** |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | arm64 | `c3_v5.json` | 4 | 2 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | arm64 | `qsrep_v5.json` | 3 | 1 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | arm64 | `terminal_v5.json` | 8 | 7 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | x86_64 | `qsrep_x86_bini_astra_v5.json` | 3 | 1 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | x86_64 | `repro_x86_bini_astra_v5.json` | 24 | 22 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | x86_64 | `suite_x86_bini_astra_v5.json` | 20 | 20 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | x86_64 | `terminal_x86_bini_astra_v5.json` | 8 | 7 | 0 |
| `bini_astra_v5` | `2f9f4d717c6ac260…` | x86_64 | `v2_x86_bini_astra_v5.json` | 12 | 12 | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | arm64 | `bench_run.json` | None | None | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | x86_64 | `qsrep_x86_bini_astra_v5_noc2b.json` | 3 | 1 | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | x86_64 | `repro_x86_bini_astra_v5_noc2b.json` | 24 | 22 | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | x86_64 | `suite_x86_bini_astra_v5_noc2b.json` | 20 | 20 | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | x86_64 | `terminal_x86_bini_astra_v5_noc2b.json` | 8 | 7 | 0 |
| `bini_astra_v5_noc2b` | `56ead3446ea7a7e4…` | x86_64 | `v2_x86_bini_astra_v5_noc2b.json` | 12 | 10 | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `bench_v8_baseline.json` | None | None | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `bench_v8_d11.json` | None | None | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `bench_v8_d11b.json` | None | None | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `c3_v8.json` | 4 | 2 | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `c3_v8_baseline.json` | 4 | 2 | **1** |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `repro_v8_baseline.json` | 24 | 15 | **7** |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `suite_v8_baseline.json` | 20 | 19 | **1** |
| `bini_v8_ship` | `163cda13023d7d5a…` | arm64 | `v2_v8.json` | 12 | 8 | **2** |
| `bini_v8_ship` | `163cda13023d7d5a…` | x86_64 | `bench_run.json` | None | None | 0 |
| `bini_v8_ship` | `163cda13023d7d5a…` | x86_64 | `repro_x86_v8.json` | 23 | 14 | **7** |
| `bini_v8_ship` | `163cda13023d7d5a…` | x86_64 | `suite_x86_v8.json` | 20 | 19 | **1** |

**Known failure, unchanged from the baseline and deliberately not fixed:** `C3.book_key_ep_aliasing`. The book key omits en passant, so a position offering an en-passant capture can share a book entry with one that does not. It fails **identically on the frozen V8 baseline and on every candidate**, so it is a pre-existing property, not a regression, and it does not bear on the ship decision. `agent.py` legality-checks the book move it plays, so the worst case is a suboptimal move, never an illegal one. Fixing it requires changing the book key format, which would strand all 1,226 existing entries; the brief directs that a book migration be kept separate from the search work, so it is recorded as a post-lock item.

**Network md5 across every build tested:** 182c8fc8fb60b96fdb51f231cbe9c0e9 (identical everywhere)
**Book md5 across every build tested:** 51c97f3f4e8ab4c1801543945d749906 (identical everywhere)
