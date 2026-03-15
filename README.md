# scrutiny-viz

`scrutiny-viz` is the visualization and comparison component of the broader **Scrutiny** toolset.

It helps to compare two measurement profiles using a YAML schema and generate:

- a machine-readable verification JSON
- an HTML report for human inspection

Scrutiny-viz is designed to work both as a standalone comparison/reporting tool and as a later-stage component in a larger Scrutiny workflow.

## Relation to the main Scrutiny toolset

Scrutiny-viz is part of the wider **Scrutiny** ecosystem.

If another Scrutiny component produces:

- normalized JSON profiles
- CSV-like result exports
- structured measurement outputs that can be mapped into supported JSON

then Scrutiny-viz can help you:

- compare a reference profile and a tested/profiled device
- detect missing, extra, changed, or suspicious values
- visualize differences in tables, charts, radar plots, and report summaries

In other words:

- other Scrutiny tools may **collect or produce the data**
- Scrutiny-viz **compares and visualizes the differences**

Main Scrutiny project: [crocs-muni/scrutiny](https://github.com/crocs-muni/scrutiny)
---

# What scrutiny-viz does

Scrutiny-viz supports four main workflow stages:

- **map** — converts supported CSV-like inputs into normalized JSON
- **verify** — compares two normalized JSON files using a schema
- **report** — renders an HTML report from verification JSON
- **full** — runs the whole pipeline: map if needed, then verify, then report

The project is modular:

- **mappers** convert raw source formats into normalized JSON
- **comparators** compare normalized sections
- **viz plugins** render report visuals
- **schemas** define section structure, ingest rules, comparator behavior, and report output

---

# Quick start

## Requirements

- Python 3.9+
- pip

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

# Main CLI entry point

Use the unified entry point:

```bash
python scrutinize.py -h
```

Available commands:

- `map`
- `verify`
- `report`
- `full`

---

# For average users

This section is for users who want to use the shipped schemas and existing inputs without modifying internals.

## Typical workflow

### Case A — you already have normalized JSON

Use:

1. `verify`
2. `report`

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/TPMAlgTest.yml -r examples/tpm_example1.json -p examples/tpm_example2.json -o results/tpm_verify.json
python scrutinize.py report -p results/tpm_verify.json -o tpm_comparison.html
```

### Case B — you have CSV-like input supported by a mapper

Use:

1. `map`
2. `verify`
3. `report`

Or just use:

4. `full`

Example:

```bash
python scrutinize.py full -s scrutiny/schemas/TPMAlgTest.yml -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv -t tpm -vo results/tpm_verify.json -ro tpm_comparison.html
```

## Which command should I use?

- Use **`map`** if your source is CSV-like and must be converted to normalized JSON.
- Use **`verify`** if you already have two normalized JSON files and want a comparison JSON.
- Use **`report`** if you already have a verification JSON and want HTML.
- Use **`full`** if you want one command to handle mapping if needed, then verification, then reporting.

---

# Predefined schemas

The project ships with predefined schemas so users do not need to write their own from scratch.

## `TPMAlgTest.yml`

**Purpose:** comparison of TPM algorithm/performance-style data for https://github.com/crocs-muni/tpm2-algtest

**Typical input shape:** TPM measurement results normalized into JSON sections

**Typical mapper/input source:** `tpm`

**Typical visuals:**

- table
- chart
- radar

**Use when:** comparing TPM capability or performance-like outputs between two devices or two runs

---

## `jcAIDScan.yml`

**Purpose:** comparison of JavaCard AID/package/app presence data for https://github.com/petrs/jcAIDScan

**Typical input shape:** package/app/AID lists normalized into JSON

**Typical mapper/input source:** `jcaid`

**Typical visuals:**

- table

**Use when:** comparing which AIDs, packages, or applets are present between two cards or profiles

---

## `jcAlgPerf.yml`

**Purpose:** comparison of JavaCard algorithm performance results

**Typical input shape:** structured performance measurement records

**Typical mapper/input source:** `jcperf`

**Typical visuals:**

- chart
- table
- radar

**Use when:** comparing algorithm timing/performance differences between reference and profile

---

## `jcAlgSupport.yml`

**Purpose:** comparison of JavaCard algorithm support / capability data for https://github.com/crocs-muni/JCAlgTest

**Typical input shape:** feature or algorithm support lists

**Typical mapper/input source:** `jcalgsupport`

**Typical visuals:**

- table
- radar

**Use when:** comparing supported vs unsupported algorithms or features

---

## `jcCPLC.yml`

**Purpose:** comparison of ATR/CPLC/card metadata-style sections

**Typical input shape:** card metadata fields and values

**Typical comparator:** `cplc` for CPLC-like fields, `basic` for simpler metadata sections

**Typical visuals:**

- table
- table variant `cplc`

**Use when:** comparing smart-card metadata, CPLC-like values, or similar record-style card descriptors

---

# Which schema should I use?

Use this quick guide:

- **TPM performance/capability-like data** → `TPMAlgTest.yml`
- **JavaCard AID/package presence** → `jcAIDScan.yml`
- **JavaCard algorithm performance** → `jcAlgPerf.yml`
- **JavaCard algorithm support** → `jcAlgSupport.yml`
- **ATR/CPLC/card metadata** → `jcCPLC.yml`

If you are unsure, inspect:

- the structure of your JSON
- the kind of differences you care about
- which example files look most similar to your input

---

# Examples and matching schemas

The `examples/` folder already contains normalized JSON files that can be compared directly with `verify` and `report`.

## TPM examples

Files:

- `examples/tpm_example1.json`
- `examples/tpm_example2.json`

Schema:

- `scrutiny/schemas/TPMAlgTest.yml`

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/TPMAlgTest.yml -r examples/tpm_example1.json -p examples/tpm_example2.json -o results/tpm_verify.json
python scrutinize.py report -p results/tpm_verify.json -o tpm_comparison.html
```

---

## JavaCard AID examples

Files:

- `examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031-ref.json`
- `examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031.json`

Schema:

- `scrutiny/schemas/jcAIDScan.yml`

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/jcAIDScan.yml -r examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031-ref.json -p examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031.json -o results/jcaid_verify.json
python scrutinize.py report -p results/jcaid_verify.json -o jcaid_comparison.html
```

---

## JavaCard AlgPerf examples

Files:

- `examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED.json`
- `examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED_copy.json`

Schema:

- `scrutiny/schemas/jcAlgPerf.yml`

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/jcAlgPerf.yml -r examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED.json -p examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED_copy.json -o results/jcperf_verify.json
python scrutinize.py report -p results/jcperf_verify.json -o jcperf_comparison.html
```

---

## JavaCard AlgSupport examples

Files:

- `examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json`
- `examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT_copy.json`

Schema:

- `scrutiny/schemas/jcAlgSupport.yml`

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/jcAlgSupport.yml -r examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json -p examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT_copy.json -o results/jcalgsupport_verify.json
python scrutinize.py report -p results/jcalgsupport_verify.json -o jcalgsupport_comparison.html
```

---

## Card metadata / CPLC-like examples

Files:

- `examples/CSOB VISA debit.json`
- `examples/IndusInd bank.json`
- `examples/n26_mastercard.json`

Schema:

- `scrutiny/schemas/jcCPLC.yml` 

Example:

```bash
python scrutinize.py verify -s scrutiny/schemas/jcCPLC.yml -r "examples/CSOB VISA debit.json" -p "examples/IndusInd bank.json" -o results/cplc_verify.json
python scrutinize.py report -p results/cplc_verify.json -o cplc_comparison.html
```

---

# How scrutiny-viz fits into Scrutiny workflows

A simple way to explain the toolchain is:

1. another Scrutiny component produces raw or normalized measurement results
2. Scrutiny-viz maps them into normalized JSON if needed
3. Scrutiny-viz compares a reference and a profile
4. Scrutiny-viz renders a report showing differences

Examples of what Scrutiny-viz helps reveal:

- missing vs extra features
- changed support flags
- metadata differences
- timing/performance changes
- suspicious deviations based on comparator thresholds

So if you already have results from another Scrutiny component, Scrutiny-viz is the part that helps **visualize and interpret the differences**.

---

# Command usage

## `map`

Use `map` when your source is CSV-like and supported by a mapper.

### Help

```bash
python scrutinize.py map -h
```

### Example

```bash
python scrutinize.py map -t tpm tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv -o results/tpm_input.json
```

### Folder example

```bash
python scrutinize.py map -t jcalgsupport -f tests/mapper/test-data/jcAlgSupport -o results/jcalgsupport_mapped
```

---

## `verify`

Use `verify` when you already have normalized JSON.

### Help

```bash
python scrutinize.py verify -h
```

### Example

```bash
python scrutinize.py verify -s scrutiny/schemas/TPMAlgTest.yml -r examples/tpm_example1.json -p examples/tpm_example2.json -o results/tpm_verify.json
```

### Useful options

```bash
--print-diffs N
--print-matches N
--emit-matches
```

---

## `report`

Use `report` to generate HTML from verification JSON.

### Help

```bash
python scrutinize.py report -h
```

### Example

```bash
python scrutinize.py report -p results/tpm_verify.json -o tpm_comparison.html
```

Depending on configuration, the output is typically written into `results/`.

---

## `full`

Use `full` when inputs may be CSV or JSON and you want one command for the whole pipeline.

### Help

```bash
python scrutinize.py full -h
```

### Example: both sides CSV

```bash
python scrutinize.py full -s scrutiny/schemas/TPMAlgTest.yml -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv -t tpm -vo results/tpm_verify.json -ro tpm_comparison.html
```

### Example: profile CSV, reference JSON

```bash
python scrutinize.py full -s scrutiny/schemas/TPMAlgTest.yml -r examples/tpm_example1.json -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv --profile-type tpm -vo results/tpm_verify.json -ro tpm_comparison.html
```

### Important note

If both `-r` and `-p` are CSV files, both sides need a mapper type.

Use either:

```bash
-t tpm
```

or:

```bash
--reference-type tpm --profile-type tpm
```

---

# Report visuals in YAML

Each section can specify what is rendered using `report.types`.

### Table only

```yaml
report:
  types: ["table"]
```

### Table variant

```yaml
report:
  types:
    - type: table
      variant: cplc
```

### Chart + table + radar

```yaml
report:
  types:
    - type: chart
    - type: table
    - type: radar
```

Only the visualization types supported by the current build and requested by the schema will be shown.

---

# Common issues

## “reference input '...' is CSV, so a mapper type is required”

If you use `full` and an input is CSV, you must provide a mapper type for that side.

Use:

```bash
-t <type>
```

or:

```bash
--reference-type <type> --profile-type <type>
```

---

## “Unknown csv type 'X'”

- make sure the mapper exists
- make sure the mapper name or alias is correct
- check that autodiscovery is loading the expected mapper package

---

## “Comparator 'X' not found”

- make sure the comparator plugin exists
- make sure the schema uses the correct comparator name
- verify comparator autodiscovery is working

---

## “No chart/radar/table is shown”

- confirm the section has `report.types` in YAML
- confirm the requested visualization exists
- if a table variant is used, confirm that the variant exists too

---

## “HTML was generated, but styles or buttons do not work”

- ensure report assets are present
- if using linked mode, confirm CSS and JS are available next to the report
- if using inline mode, confirm asset loading succeeded during report generation

---

# For power users / developers

This section is for users who want to extend the project.

Power users may want to:

- create or modify schemas
- add new mappers
- add new comparators
- add new visualizations
- update plugin discovery and registry behavior

If you need more information please read the provided documentation in /docs.

---

# Development overview

The project is organized around internal plugins:

- **mappers** parse and normalize source input
- **comparators** compare normalized sections
- **viz plugins** render report visuals

A simplified structure looks like this:

```text
scrutiny/
  reporting/
  schemas/
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

The main design idea is:

- plugin modules contain the real implementation
- registries handle discovery and lookup
- service layers orchestrate execution

---

# Getting help / reporting issues

If you run into problems:

1. first check command help:
   - `python scrutinize.py map -h`
   - `python scrutinize.py verify -h`
   - `python scrutinize.py report -h`
   - `python scrutinize.py full -h`

2. then check the predefined schemas and examples in this README

3. if the issue persists:
   - contact the project creators / maintainers
   - or open an issue on the GitHub repository

When reporting a problem, include:

- the exact command you ran
- which schema you used
- whether the input was CSV or JSON
- the exact error message
- your Python version
- your operating system

That makes troubleshooting much easier.

---

# Summary

The recommended modern workflow is based on `scrutinize.py`:

- use `map` for CSV -> JSON
- use `verify` for JSON -> verification JSON
- use `report` for verification JSON -> HTML
- use `full` for the complete pipeline

For ordinary users, the most important parts are:

- choose the correct predefined schema
- start from the matching example pair if possible
- use the unified CLI commands

For power users, the project also supports extension through schemas and plugins without rewriting the core workflow.