# Examples guide

This document shows how to approach the example data shipped with the repository.

## Two common starting points

### 1. You already have normalized JSON

Use:

1. `verify`
2. `report`

Example:

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

### 2. You have raw input supported by a mapper

Use:

1. `map`
2. `verify`
3. `report`

or just use:

4. `full`

Example:

```bash
python scrutinize.py full \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -p tests/mapper/test-data/TPMAlgTest/INTC_Intel_10.0.36.1030.csv \
  -t tpm \
  --verify-output results/tpm_verify.json \
  --report-output tpm_comparison.html
```

## Discovering available plugins before choosing a workflow

If you are unsure which mapper, comparator, or viz plugin is available in your current build, list the discovered plugins first.

### List mapper plugins

```bash
python scrutinize.py map --list-mappers
```

### List comparator plugins

```bash
python scrutinize.py verify --list-comparators
```

### List viz plugins

```bash
python scrutinize.py report --list-viz
```

This is especially useful when working with custom builds, new plugins, or aliases that may differ between environments.

## Example pairings

### TPM examples

Schema:

- `scrutiny/schemas/TPMAlgTest.yml`

Typical commands:

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  -p examples/tpm_example2.json \
  -o results/tpm_verify.json
```

### JavaCard AID examples

Schema:

- `scrutiny/schemas/jcAIDScan.yml`

Typical commands:

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/jcAIDScan.yml \
  -r examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031-ref.json \
  -p examples/ACS_ACOSJ_40K_AIDSUPPORT_3B69000241434F534A76313031.json \
  -o results/jcaid_verify.json
```

### JavaCard AlgPerf examples

Schema:

- `scrutiny/schemas/jcAlgPerf.yml`

Typical commands:

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/jcAlgPerf.yml \
  -r examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED.json \
  -p examples/Athena_IDProtect____PERFORMANCE_SYMMETRIC_ASYMMETRIC_DATAFIXED_copy.json \
  -o results/jcperf_verify.json
```

### JavaCard AlgSupport examples

Schema:

- `scrutiny/schemas/jcAlgSupport.yml`

Typical commands:

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/jcAlgSupport.yml \
  -r examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json \
  -p examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT_copy.json \
  -o results/jcalgsupport_verify.json
```

### CPLC-like metadata examples

Schema:

- `scrutiny/schemas/jcCPLC.yml`

Typical commands:

```bash
python scrutinize.py verify \
  -s scrutiny/schemas/jcCPLC.yml \
  -r "examples/CSOB VISA debit.json" \
  -p "examples/IndusInd bank.json" \
  -o results/cplc_verify.json
```

## Batch examples

Batch verification is useful when you want to compare one reference against many profiles.

### Batch example with a directory of profiles

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/jcAlgSupport.yml \
  -r examples/Infineon_CJTOP_80K_INF_SLJ_52GLA080AL_M8.4_ICFabDate_2012_001_ALGSUPPORT.json \
  --profiles-dir tests/mapper/test-data/jcAlgSupport \
  --profile-type jcalgsupport
```

### Batch example with explicit profiles

```bash
python scrutinize.py batch-verify \
  -s scrutiny/schemas/TPMAlgTest.yml \
  -r examples/tpm_example1.json \
  --profiles examples/tpm_example2.json examples/tpm_example1.json \
  --report-mode all
```

## Practical advice

When starting with a new dataset:

1. first find the example that looks most similar to your input
2. use the schema paired with that example
3. if needed, use `map --list-mappers` to check the mapper names available in your build
4. start with `verify` if your data is already normalized JSON
5. use `map` or `full` if your source is still raw
6. switch to `batch-verify` when the same reference should be used against many profiles
7. if report output looks different than expected, use `report --list-viz` to confirm which viz plugins are present
