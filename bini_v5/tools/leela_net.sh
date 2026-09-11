#!/bin/bash
# On the GPU box: fetch a strong Leela network for labelling (never shipped). Tries known
# locations in order; leaves ~/chess/data/leela/net.pb.gz.
mkdir -p ~/chess/data/leela && cd ~/chess/data/leela
for url in \
  "https://storage.lczero.org/files/networks-contrib/big-transformers/BT4-1740.pb.gz" \
  "https://storage.lczero.org/files/networks-contrib/t1-768x15x24h-swa-4000000.pb.gz" \
  "https://storage.lczero.org/files/networks-contrib/t2-768x15x24h-swa-5230000.pb.gz" \
  "https://training.lczero.org/get_network?sha=eb46b40b7fdd3e7d95ac3e4d4a9d5c1c9f6dc1c2b62a7c4b6a4d9f9a3b0e3e3e"; do
  echo "trying $url"; if curl -fsSL --retry 2 -o net.pb.gz "$url" && [ "$(stat -c %s net.pb.gz)" -gt 10000000 ]; then echo "got $(stat -c %s net.pb.gz) bytes from $url"; exit 0; fi
done
echo "NO NETWORK FETCHED: download one from https://lczero.org/play/networks/bestnets/ and place it at ~/chess/data/leela/net.pb.gz"; exit 1
