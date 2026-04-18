# scrutiny-viz

`scrutiny-viz` is the comparison and reporting component of the broader **Scrutiny** toolset.

It compares measurement profiles using YAML schemas and can produce:

- normalized JSON from supported raw inputs
- a machine-readable verification JSON
- an HTML report for human inspection
- batch comparison outputs for one-to-many workflows

Scrutiny-viz can be used as a standalone tool or as a later-stage component in a larger Scrutiny workflow.

Main Scrutiny project: <https://github.com/crocs-muni/scrutiny>

## Main workflows

The unified CLI entry point is:

```bash
python scrutinize.py -h
```

Available commands:

- `map` — convert supported raw inputs into normalized JSON
- `verify` — compare two normalized JSON files using a schema
- `report` — render an HTML report from verification JSON
- `full` — map if needed, then verify, then report
- `batch-verify` — compare one reference against many profiles

## Quick start

### Requirements

- Python 3.13+
- pip

### Setup

```bash
git clone https://github.com/crocs-muni/scrutiny-viz.git
cd scrutiny-viz
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
# or .\.venv\Scripts\Activate.ps1 on Windows PowerShell
pip install -r requirements.txt
```

### Minimal JSON workflow

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p examples/tpm_example2.json \
  -o results/tpm_verify.json

python scrutinize.py report \
  -p results/tpm_verify.json \
  -o tpm_comparison.html
```

### One-command workflow for CSV/JSON inputs

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -t tpm \
  --verify-output results/tpm_verify.json \
  --report-output tpm_comparison.html
```

### Batch verification example

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/jcAlgSupport.yml \
  -r examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json \
  --profiles-dir tests/mapper/test-data/jcAlgSupport \
  --profile-type jcalgsupport \
  --report-mode nonmatch
```

## Documentation

For deeper usage and development information, see:

- [CLI guide](docs/cli.md)
- [Schema overview](docs/schemas.md)
- [Examples guide](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Plugin module overview](docs/plugins.md)
- [Test structure](docs/tests.md)

## Choosing the right command

- Use **`map`** when your input is raw and supported by a mapper.
- Use **`verify`** when you already have two normalized JSON files.
- Use **`report`** when you already have a verification JSON.
- Use **`full`** when you want one command for the entire single comparison pipeline.
- Use **`batch-verify`** when you want to compare one reference against many profiles.

## For developers

The project is organized around modular:

- **mappers** for normalization
- **comparators** for section-level comparison
- **viz plugins** for report rendering
- **schemas** for structure, ingest behavior, comparator selection, and report types
