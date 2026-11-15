#!/bin/sh
# Run the checker over each example file and show the result.
# The bad example fails on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/good.yaml examples/bad.yaml examples/edge.yaml; do
  echo "== $f =="
  python3 src/yaml_key_sort_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/yaml_key_sort_checker.py examples/ || true
