# HyperTesting Extended Replication

Replication and extension of the empirical evaluation from:

> "Hypertesting of Programs: Theoretical Foundation and Automated Test Generation"  
> ICSE 2024

This project applies HyperFuzz, HyperEvo, and Phosphor to 10 previously unused IFSpec programs not included in the original paper.

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Linux/macOS)
- ~4 GB disk space
- ~35 minutes to run all experiments

No local Java or Python installation is required — everything runs inside Docker.

---

## Project Structure

```
.
├── Dockerfile                   # Ubuntu 20.04 + OpenJDK 16 + Python 3.8
├── run_all_experiments.sh       # Phases 8–12: Phosphor + RQ1/RQ2/RQ3
├── test_compat.sh               # Quick compatibility smoke test
├── fix_dataset.py               # Applies source compatibility fixes
├── patch_sources.py             # Targeted structural rewrites
├── prepare_phases_3_7.py        # Phases 3–7: candidate selection + settings
├── create_new_dataset.py        # Assembles the final NewDataset directories
├── TRABALHO_REALIZADO.md        # Portuguese summary of all 12 phases
├── bin/                         # HyperCoverageTester, HyperFuzz, HyperEvo JARs
├── lib/                         # Phosphor and support libraries
├── scripts/                     # Python experiment scripts (RQ1/RQ2/RQ3)
├── datasets/
│   ├── FullDataset/             # Original 34-program paper dataset
│   ├── NewDataset/              # 10 new programs (secure + insecure)
│   ├── NewDataset-phosphor/     # Phosphor-instrumented version
│   └── NewUnsecureDataset/      # 6 insecure programs (for RQ1)
├── artifacts/                   # Dataset metadata and selection logs
│   ├── original_paper_samples.json
│   ├── candidate_pool.json
│   ├── compatible_samples.json
│   ├── incompatible_samples.json
│   ├── selected_50_samples.json
│   └── fixed_dataset_mapping.json
└── results/
    ├── final_report.md          # Full report with all metrics
    ├── RQ1/                     # Hypercoverage correlation results
    ├── RQ2/                     # Coverage per tool (HyperFuzz/HyperEvo)
    └── RQ3/                     # Detection accuracy (all three tools)
```

---

## Installation

### 1. Clone this repository

```bash
git clone https://github.com/jpspm/replication-hypertesting.git
cd replication-hypertesting
```

### 2. Build the Docker image

```bash
docker build -t hypertesting-replication:latest .
```

This installs OpenJDK 16, Python 3.8, and all required Python dependencies inside the container.

**Expected time:** 3–5 minutes (first build downloads ~500 MB).

### 3. Verify the build

```bash
docker run --rm hypertesting-replication:latest java -version
docker run --rm hypertesting-replication:latest python3 --version
```

Expected output:
```
openjdk version "16.0.1" 2021-04-20
Python 3.8.10
```

---

## Running the Experiments

### Full pipeline (recommended)

Runs Phases 8–12: Phosphor installation, instrumentation, RQ1, RQ2, and RQ3.

**Windows (PowerShell):**
```powershell
docker run --rm `
  -v "${PWD}:/hypertesting" `
  hypertesting-replication:latest `
  bash /hypertesting/run_all_experiments.sh
```

**Linux / macOS:**
```bash
docker run --rm \
  -v "$(pwd):/hypertesting" \
  hypertesting-replication:latest \
  bash /hypertesting/run_all_experiments.sh
```

**Expected runtime:** ~35 minutes.  
**Results land in:** `results/`

---

### Individual phases

Open an interactive shell inside the container:

```bash
docker run --rm -it \
  -v "$(pwd):/hypertesting" \
  hypertesting-replication:latest bash
cd /hypertesting
```

Then run phases individually:

```bash
# Phase 8 — Install Phosphor
python3 scripts/phosphorInstallFromLocal.py install phosphor-install

# Phase 9 — Instrument with Phosphor
python3 scripts/phosphorCodeInstrumenter.py instrument \
  datasets/NewDataset-phosphor -withoutBranchNotTaken

# Phase 10 — RQ1: hypercoverage vs. violations correlation
python3 scripts/runExperimentRQ1.py run datasets/NewUnsecureDataset 1000 100

# Phase 11 — RQ2: coverage achieved by HyperFuzz and HyperEvo
python3 scripts/runExperimentRQ2.py run datasets/NewDataset 5

# Phase 12 — RQ3: detection effectiveness
python3 scripts/runExperimentRQ3.py run \
  datasets/NewDataset datasets/NewDataset-phosphor phosphor-install 5
```

---

### Compatibility smoke test

Verifies all 10 programs run without errors (fast, ~2 minutes):

```bash
docker run --rm \
  -v "$(pwd):/hypertesting" \
  hypertesting-replication:latest \
  bash /hypertesting/test_compat.sh
```

Each program prints `PASS`. Uses `p=20, z=10` (required — `p=5, z=2` causes `ArithmeticException`).

---

## Reading the Results

### Quick view (PowerShell)

```powershell
# RQ1 — correlation metrics CSV
(Get-Content results\RQ1\*\hypercoveragetester-metrics.json |
  ConvertFrom-Json).csvTable

# RQ2 — hypercoverage per program
(Get-Content results\RQ2\*_metrics.json |
  ConvertFrom-Json).csvTable

# RQ3 — classification metrics
(Get-Content results\RQ3\*_metrics.json |
  ConvertFrom-Json).csvTable
```

### Full report

Open [`results/final_report.md`](results/final_report.md) for the complete analysis including:
- Dataset selection and compatibility screening
- RQ1 correlation tables (Pearson, Spearman, Kendall, point-biserial)
- RQ2 hypercoverage per program
- RQ3 TP/TN/FP/FN classification table and accuracy metrics
- Threats to validity discussion
- Reproducibility commands

---

## Key Results at a Glance

**Dataset:** 10 programs (6 insecure, 4 secure) from IFSpec — out of 198 candidates, only 10 were tool-compatible.

**RQ1 — All 6 insecure programs show significant positive correlation between hypercoverage and violations (p < 0.01).**

**RQ2 — Hypercoverage achieved:**

| Tool | Programs at 100% coverage |
|---|---|
| HyperEvo | 10 / 10 |
| HyperFuzz | 9 / 10 (gives up on `simpleTypes`) |

**RQ3 — Detection accuracy:**

| Tool | TPR (Recall) | FPR | Accuracy |
|---|---|---|---|
| HyperEvo | 1.00 | 0.25 | 0.90 |
| HyperFuzz | 0.83 | 0.25 | 0.80 |
| Phosphor | n/a* | n/a* | n/a* |

\* Phosphor requires programs to have a `main()` method. The simplified IFSpec programs do not, so Phosphor produced no meaningful results.

---

## Known Limitations

| Issue | Impact |
|---|---|
| Only 10/50 requested programs found compatible | Reduced statistical power |
| Programs required source modifications | Divergence from original IFSpec form |
| `timebomb` causes false positive in both fuzzing tools | Unreachable dead-code branch triggers coverage goal |
| Phosphor incompatible with programs lacking `main()` | RQ3 Phosphor baseline invalid for this dataset |
| `computeMetricsRQ3.py` crashes (`hyperrandom` vs `hyperfuzz` naming mismatch) | RQ3 metrics JSON computed manually |

---

## Reproducing the Dataset Preparation (optional)

The `NewDataset` is already included. To rebuild it from scratch from the IFSpec source:

```bash
# 1. Clone IFSpec
git clone https://github.com/statycc/ifspec workspace/ifspec

# 2. Generate settings and initial dataset (inside Docker container)
python3 prepare_phases_3_7.py

# 3. Apply source compatibility patches
python3 patch_sources.py

# 4. Rebuild dataset directories
python3 fix_dataset.py
python3 create_new_dataset.py
```

Then re-run the Docker pipeline above.
