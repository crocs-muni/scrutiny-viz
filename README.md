# scrutiny-viz

`scrutiny-viz` compares two measurement profiles using a YAML schema and produces:

- a machine-readable verification JSON
- an HTML report for human inspection

The project is modular. Mappers, comparators, schemas, and report visualizations can be extended without rewriting the core workflow.

The project is a part of a bigger project `Scurtiny` that can be found on https://github.com/crocs-muni/scrutiny

---

## What you get

The project now uses a single entry point:

- **`scrutinize.py`** — unified CLI with subcommands:
  - `map`
  - `verify`
  - `report`
  - `full`

The current CLI wiring shows exactly these four commands, with `full` chaining mapping, verification, and report generation when needed. :contentReference[oaicite:0]{index=0}

Other key parts of the project:

- **mapper plugins** — convert CSV-like source data into normalized JSON
- **verification comparators** — compare normalized reference vs profile sections
- **report/viz plugins** — render HTML visualization blocks such as table, chart, radar, and donut
- **YAML schemas** — define section structure, comparator behavior, ingest rules, and report output

---

## Requirements

- **Python**: 3.9+ recommended
- **pip**: installed with Python

Python dependencies are installed from `requirements.txt`.

---

## Setup

### 1) Clone the repository

```bash
git clone https://github.com/crocs-muni/scrutiny-viz.git
cd scrutiny-viz
```

### 2) Create a virtual environment (recommended)

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Run tests

```bash
python -m pytest -q -rs
```

---

## Main CLI entry point

### Help

```bash
python scrutinize.py -h
```

### Available commands

- `map` — map CSV input into normalized JSON
- `verify` — compare reference JSON and profile JSON using a schema
- `report` — render HTML from verification JSON
- `full` — run the full pipeline: map if needed, then verify, then report :contentReference[oaicite:1]{index=1}

---

## Map (generate normalized JSON)

Use `map` when your source input is CSV-like and must be converted into normalized JSON before verification.

### Help

```bash
python scrutinize.py map -h
```

### Generic example

```bash
python scrutinize.py map -t jcperf path/to/file.csv
```

### Example with explicit output

```bash
python scrutinize.py map -t tpm path/to/input.csv -o path/to/output.json
```

### Folder example

```bash
python scrutinize.py map -t jcalg -f path/to/folder -o path/to/output_folder
```

Typical mapper types include things like:

- `tpm`
- `jcperf`
- `jcaid`
- `jcalgsupport`

The exact mapper type must match the installed mapper plugins in your build.

---

## Verify (generate verification JSON)

Use `verify` when you already have normalized JSON for both reference and profile.

### Help

```bash
python scrutinize.py verify -h
```

### Generic example

```bash
python scrutinize.py verify \
  -s path/to/schema.yml \
  -r path/to/reference.json \
  -p path/to/profile.json \
  -o results/comparison.json
```

### Example with verbose output

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p examples/tpm_example2.json \
  -o results/tpm_verify.json \
  -v --print-diffs 20 --print-matches 20
```

Useful options include:

- `--print-diffs N`
- `--print-matches N`
- `--emit-matches`

These are passed into the verification stage in the current unified CLI as well. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

---

## Report (generate HTML report)

Use `report` when you already have a verification JSON and want HTML output.

### Help

```bash
python scrutinize.py report -h
```

### Example

```bash
python scrutinize.py report -p results/tpm_verify.json -o tpm_comparison.html -v
```

Depending on your report configuration, the HTML report is typically written into the `results/` folder.

Useful options include:

- `-e` / `--exclude-style-and-scripts`  
  Link CSS/JS instead of inlining them
- `-nz` / `--no-zip`  
  Disable zip creation

These same report-stage options are also available through the `full` command. :contentReference[oaicite:4]{index=4}

---

## Full workflow (map -> verify -> report)

Use `full` when your inputs may be CSV or JSON and you want one command to run the whole pipeline.

### Help

```bash
python scrutinize.py full -h
```

### What `full` does

The current implementation:

1. checks whether reference and profile inputs are `.json` or `.csv`
2. maps CSV inputs into JSON if needed
3. runs verification
4. renders the final HTML report :contentReference[oaicite:5]{index=5} :contentReference[oaicite:6]{index=6}

### Example: both inputs are CSV of the same type

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -t tpm \
  -vo results/tpm_verify.json \
  -ro tpm_comparison.html
```

### Example: only profile needs mapping

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  --profile-type tpm \
  -vo results/tpm_verify.json \
  -ro tpm_comparison.html
```

### Important note

If **both** `-r` and `-p` are CSV files, both sides need a mapper type.

You can do that either with:

```bash
-t <type>
```

or with separate values:

```bash
--reference-type <type> --profile-type <type>
```

The current CLI explicitly enforces this for CSV inputs. :contentReference[oaicite:7]{index=7}

---

## Report visuals (YAML)

Each section can specify what is rendered using `report.types`.

### Example: table only

```yaml
report:
  types: ["table"]
```

### Example: table variant

```yaml
report:
  types:
    - type: table
      variant: cplc
```

### Example: chart + table + radar

```yaml
report:
  types:
    - type: chart
    - type: table
    - type: radar
```

Depending on the schema and build, available section-level visualization types commonly include:

- `table`
- `chart`
- `radar`

---

## Common issues

### “reference input '...' is CSV, so a mapper type is required”

If you use `scrutinize.py full` and one of the inputs is CSV, you must provide a mapper type for that side.

Use one of:

```bash
-t tpm
```

or

```bash
--reference-type tpm --profile-type tpm
```

---

### “Unknown csv type 'X'”

- make sure the mapper plugin exists
- make sure the mapper name or alias is correct
- check that autodiscovery is loading the expected mapper package

---

### “Comparator 'X' not found” or fallback behavior is wrong

- make sure the comparator plugin exists
- make sure the schema uses the correct comparator name
- verify comparator autodiscovery is working

---

### “No chart/radar/table is shown”

- confirm the section has `report.types` set in the YAML
- confirm the requested visualization exists in your build
- if a variant is requested, confirm that specific variant exists

---

### “HTML was generated, but styles or buttons do not work”

- ensure the report assets are present
- if using linked mode, ensure CSS and JS are being copied or served correctly
- if using inline mode, confirm asset loading succeeded during report generation

---

## Development notes

The project is now organized around internal plugins:

- **mappers** parse and normalize source input
- **comparators** compare normalized sections
- **viz plugins** render report visuals

The service layer should orchestrate the workflow, while the real implementation should live inside plugin modules.

A simplified structure looks like:

```text
scrutiny/
  reporting/
    ...
  schemas/
    *.yml
  ingest.py
  schemaloader.py
  ...

mapper/
  mappers/
    ...

verification/
  comparators/
    ...

report/
  viz/
    ...

tests/
scrutinize.py
```

---

## Getting help / reporting problems

If you run into issues:

- first check the help output of the relevant command:
  - `python scrutinize.py map -h`
  - `python scrutinize.py verify -h`
  - `python scrutinize.py report -h`
  - `python scrutinize.py full -h`

If the problem persists, please:

1. contact the project creators or maintainers
2. or open an issue on the GitHub repository

When reporting a problem, include:

- the command you ran
- the schema file used
- whether the input was CSV or JSON
- the exact error message
- your Python version
- your operating system

That makes debugging much easier.

---

## Summary

The recommended modern workflow is now based on `scrutinize.py`:

- use `map` for CSV -> JSON
- use `verify` for JSON -> verification JSON
- use `report` for verification JSON -> HTML
- use `full` for the whole pipeline in one command

That is the most up-to-date way to use `scrutiny-viz` in the current project state. :contentReference[oaicite:8]{index=8}