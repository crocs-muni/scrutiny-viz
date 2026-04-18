# CLI guide

This document describes the main `scrutinize.py` commands at a practical level.

## Unified entry point

```bash
python scrutinize.py -h
```

Available commands:

- `map`
- `verify`
- `batch-verify`
- `report`
- `full`

---

## Discovering available plugins

The CLI can also list the plugins discovered in the current build.

### List mapper plugins

```bash
python scrutinize.py map --list-mappers
```

This prints the discovered mapper names together with aliases and descriptions.

### List comparator plugins

```bash
python scrutinize.py verify --list-comparators
```

This prints the discovered comparator names together with aliases and descriptions.

### List viz plugins

```bash
python scrutinize.py report --list-viz
```

This prints the discovered visualization plugins. For viz plugins, the output may also include the configured slot.

These listing modes are useful when you are unsure which mapper, comparator, or viz type is currently available through plugin autodiscovery.

---

## `map`

Use `map` when your source input is supported by a mapper and must be converted into normalized JSON.

### Typical uses

- map one CSV-like file into JSON
- map a folder of files into multiple JSON outputs
- run a directory-based mapper such as `rsabias`
- inspect which mapper plugins are currently available

### Help

```bash
python scrutinize.py map -h
```

### Example: one file

```bash
python scrutinize.py map \
  -t tpm \
  tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -o results/tpm_input.json
```

### Example: folder input

```bash
python scrutinize.py map \
  -t jcalgsupport \
  --folder tests/mapper/test-data/jcAlgSupport \
  -o results/jcalgsupport_mapped
```

### Example: directory-based mapper

```bash
python scrutinize.py map \
  -t rsabias \
  --folder tests/test-data/RSABias/out_eval \
  -o results/rsabias.json
```

### Example: list discovered mappers

```bash
python scrutinize.py map --list-mappers
```

### Important options

- `-t, --type` — mapper type
- `-o, --output` — output file or output directory
- `--folder` — folder input or source directory for directory-based mappers
- `--delimiter` — delimiter for grouped-text mappers
- `--exclude-file` — file listing attributes to exclude
- `--list-mappers` — print discovered mapper plugins and exit

---

## `verify`

Use `verify` when you already have normalized JSON profiles and want a comparison result.

### Typical uses

- compare two normalized JSON profiles using a schema
- inspect comparator-driven diff logic in a machine-readable form
- generate a report immediately after verification
- inspect which comparator plugins are currently available

### Help

```bash
python scrutinize.py verify -h
```

### Example

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p examples/tpm_example2.json \
  -o results/tpm_verify.json
```

### Optional report generation

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p examples/tpm_example2.json \
  -o results/tpm_verify.json \
  --report
```

### Example: list discovered comparators

```bash
python scrutinize.py verify --list-comparators
```

### Important options

- `-s, --schema` — schema YAML
- `-r, --reference` — reference JSON
- `-p, --profile` — tested/profile JSON
- `-o, --output-file` — verification JSON output path
- `--emit-matches` — include matches when supported
- `--print-diffs N` — print up to `N` diffs per section
- `--print-matches N` — print up to `N` matches per section
- `--report` — generate HTML report immediately after verification
- `--list-comparators` — print discovered comparator plugins and exit

---

## `report`

Use `report` when you already have a verification JSON and want HTML output.

### Typical uses

- render a human-readable HTML report from verification JSON
- control whether assets are inlined or linked
- disable zip output when only HTML is needed
- inspect which viz plugins are currently available

### Help

```bash
python scrutinize.py report -h
```

### Example

```bash
python scrutinize.py report \
  -p results/tpm_verify.json \
  -o tpm_comparison.html
```

### Example: list discovered viz plugins

```bash
python scrutinize.py report --list-viz
```

### Important options

- `-p, --verification-profile` — verification JSON input
- `-o, --output-file` — HTML filename
- `--exclude-style-and-scripts` — link CSS/JS instead of inlining them
- `--no-zip` — disable zip generation
- `--list-viz` — print discovered viz plugins and exit

---

## `full`

Use `full` when you want a single command that maps inputs if needed, then verifies, then renders a report.

### Help

```bash
python scrutinize.py full -h
```

### Example: both inputs are CSV

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -t tpm \
  --verify-output results/tpm_verify.json \
  --report-output tpm_comparison.html
```

### Example: reference JSON, profile CSV

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  --profile-type tpm \
  --verify-output results/tpm_verify.json \
  --report-output tpm_comparison.html
```

### Important options

- `-s, --schema` — schema YAML
- `-r, --reference` — reference input (`.json` or `.csv`)
- `-p, --profile` — profile input (`.json` or `.csv`)
- `-t, --type` — shared mapper type for CSV inputs
- `--reference-type`, `--profile-type` — side-specific mapper types
- `--mapped-dir` — location for intermediate mapped JSON files
- `--verify-output` — verification JSON output path
- `--report-output` — final report HTML output path
- `--emit-matches`, `--print-diffs`, `--print-matches`
- `--exclude-style-and-scripts`, `--no-zip`

### Important note

If an input is CSV, that side needs a mapper type.

Use either:

```bash
-t <mapper>
```

or:

```bash
--reference-type <mapper> --profile-type <mapper>
```

---

## `batch-verify`

Use `batch-verify` when you want to compare one reference against many profiles.

This is useful for regression-style checks, multi-profile evaluation, or generating many comparison outputs from one reference baseline.

### Help

```bash
python scrutinize.py batch-verify -h
```

### Example: profiles from a directory

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/jcAlgSupport.yml \
  -r examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json \
  --profiles-dir tests/mapper/test-data/jcAlgSupport \
  --profile-type jcalgsupport
```

### Example: explicit profile list

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  --profiles examples/tpm_example2.json examples/tpm_example1.json \
  --report-mode all
```

### Example: shared mapper type for many raw inputs

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  --profiles-dir tests/mapper/test-data/TPMAlgTest \
  -t tpm
```

### Important options

- `-s, --schema` — schema YAML
- `-r, --reference` — reference input (JSON, raw file, or mapper-supported directory)
- `--profiles-dir` — directory containing profiles
- `--profiles` — explicit list of profile inputs
- `-t, --type` — shared mapper type for reference and profiles when needed
- `--reference-type`, `--profile-type` — side-specific mapper types
- `--batch-id` — custom batch identifier
- `--report-mode` — `nonmatch`, `all`, or `none`
- `--keep-mapped` — keep intermediate mapped JSON files

### Output layout

Batch verification writes results under a dedicated batch directory in `results/`, typically including:

- per-profile verification JSON outputs
- per-profile HTML reports when enabled
- summary JSON and CSV

---

## Verbosity

Most commands support:

```bash
-v
-vv
```

Use these to increase CLI logging detail.
