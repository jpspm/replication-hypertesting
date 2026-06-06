#!/bin/bash
# Phases 8-12: Phosphor + RQ1/RQ2/RQ3 for the new 10-program dataset
set -e
cd /hypertesting

PHOSPHOR_DIR="/hypertesting/phosphor-install"
NEW_DATASET="datasets/NewDataset"
NEW_UNSECURE="datasets/NewUnsecureDataset"
NEW_PHOSPHOR="datasets/NewDataset-phosphor"
RESULTS_DIR="/results"

mkdir -p "$RESULTS_DIR/RQ1" "$RESULTS_DIR/RQ2" "$RESULTS_DIR/RQ3"
mkdir -p logs

echo "=============================="
echo " Phase 8: Install Phosphor"
echo "=============================="
mkdir -p "$PHOSPHOR_DIR"
python3 scripts/phosphorInstallFromLocal.py install "$PHOSPHOR_DIR"
echo "Phosphor installed."

echo ""
echo "=============================="
echo " Phase 9: Phosphor Instrumentation"
echo "=============================="
python3 scripts/phosphorCodeInstrumenter.py instrument "$NEW_PHOSPHOR" -withoutBranchNotTaken 2>&1 | tee logs/phosphor_instrumentation.log
echo "Phosphor instrumentation done."

echo ""
echo "=============================="
echo " Phase 10: RQ1 (attempts=1000, sampling=100)"
echo "=============================="
# runExperimentRQ1.py writes JSON files into datasets/NewUnsecureDataset/*/
python3 scripts/runExperimentRQ1.py run "$NEW_UNSECURE" 1000 100 2>&1 | tee logs/rq1.log
# Copy results
cp -r "$NEW_UNSECURE" "$RESULTS_DIR/RQ1/" 2>/dev/null || true
echo "RQ1 done."

echo ""
echo "=============================="
echo " Phase 11: RQ2 (runs=5)"
echo "=============================="
python3 scripts/runExperimentRQ2.py run "$NEW_DATASET" 5 2>&1 | tee logs/rq2.log
cp -r "$NEW_DATASET" "$RESULTS_DIR/RQ2/" 2>/dev/null || true
echo "RQ2 done."

echo ""
echo "=============================="
echo " Phase 12: RQ3 (runs=5)"
echo "=============================="
python3 scripts/runExperimentRQ3.py run "$NEW_DATASET" "$NEW_PHOSPHOR" "$PHOSPHOR_DIR" 5 2>&1 | tee logs/rq3.log
cp -r "$NEW_DATASET" "$RESULTS_DIR/RQ3/" 2>/dev/null || true
echo "RQ3 done."

echo ""
echo "=============================="
echo " Collecting all results"
echo "=============================="
cp -r logs "$RESULTS_DIR/" 2>/dev/null || true

# Print summary of RQ1 results
echo ""
echo "--- RQ1 JSON results ---"
find "$NEW_UNSECURE" -name "*.json" 2>/dev/null | head -20
for f in $(find "$NEW_UNSECURE" -name "*.json" 2>/dev/null | head -20); do
    echo "=== $f ==="
    python3 -c "import json,sys; d=json.load(open('$f')); print(json.dumps({k:v for k,v in d.items() if k != 'details'}, indent=2))" 2>/dev/null || cat "$f"
done

# Print summary of RQ2 results
echo ""
echo "--- RQ2 JSON results ---"
find "$NEW_DATASET" -name "rq2*.json" -o -name "*rq2*.json" 2>/dev/null | head -20
for f in $(find "$NEW_DATASET" -name "rq2*.json" 2>/dev/null | head -20); do
    echo "=== $f ==="
    python3 -c "import json,sys; d=json.load(open('$f')); print(json.dumps(d, indent=2))" 2>/dev/null || cat "$f"
done

echo ""
echo "All phases complete."
ls "$RESULTS_DIR/"
