# YAML Schema Reference

This document describes the YAML schema format used to drive comparison and reporting.

A schema defines:
- which **sections** exist (e.g., `ATR`, `CPLC`, algorithm groups),
- how section data is structured (**record_schema**),
- how records are matched and compared (**component**),
- which visuals are rendered in the HTML report (**report**),
- optional comparator-specific options (**target**).

---

## 1. Top-level fields

```yaml
schema_version: "0.12"

defaults:         # optional but recommended
  data: ...
  component: ...
  report: ...
  target: ...

sections:         # required
  <SECTION_NAME>: ...
```

### `schema_version` (required)
A string identifying the schema format version. Only versions supported by the runtime should be used (commonly `0.11`, `0.12`, etc., depending on the project build). 

---

## 2. Defaults

`defaults` defines baseline configuration that is inherited by all sections. Any section may override any field.

### 2.1 `defaults.data`
```yaml
defaults:
  data:
    type: list
```

- `type` must be `list` (sections are lists of records).

### 2.2 `defaults.component`
```yaml
defaults:
  component:
    comparator: basic
    match_key: __override__
    show_key: __override__       # optional
    include_matches: true        # optional
    threshold_ratio: 0.0         # optional
    threshold_count: 0           # optional
```

Meaning:
- `comparator`: comparator identifier (e.g., `basic`, `cplc`, `algperf`).
- `match_key`: record field used to match items between reference and profile (must exist in `record_schema`).
- `show_key`: record field used for display labels (Optional. fall back to `match_key` if unset).
- `include_matches`: when true, matches are included in output JSON (`matches`) in addition to differences (`diffs`).
- `threshold_ratio` / `threshold_count`: comparator thresholds used to decide WARN vs SUSPICIOUS in some comparators.

### 2.3 `defaults.report`
```yaml
defaults:
  report:
    types: ["table"]
    theme: dark
```

Meaning:
- `types`: which visual blocks are rendered for each section (see **Report types**).
- `theme`: `light` or `dark` (applies to the whole HTML report).

Additional report options may exist for specific visualizations (e.g., axis labels for performance charts).

### 2.4 `defaults.target`
```yaml
defaults:
  target: {}
```

`target` is a free-form mapping used by specific comparators. Keys depend on the comparator (see **Target options**).

---

## 3. Sections

`sections` is a mapping of section name → section configuration.

Sections may be fully specified, or empty to inherit everything from defaults.

### 3.1 Fully specified section example

```yaml
sections:
  ATR:
    data:
      record_schema:
        name:  { dtype: string, required: true, category: nominal }
        value: { dtype: string, category: nominal }
    component:
      comparator: basic
      match_key: name
      show_key: name
      include_matches: true
    report:
      types: ["table"]
```

### 3.2 “inherit defaults” section example

When defaults contain sufficient configuration (e.g., shared record_schema + component + report), sections may be empty:

```yaml
sections:
  MESSAGE_DIGEST: {}
  RANDOM_GENERATOR: {}
```

---

## 4. Section data

### 4.1 `data.type`
Must be:

```yaml
data:
  type: list
```

### 4.2 `data.record_schema`
Defines the structure of each record in the section list.

Two formats are supported:

#### Short form
```yaml
record_schema:
  name: string
  value: string
```

#### Full form
```yaml
record_schema:
  name:
    dtype: string
    required: true
    category: nominal
  value:
    dtype: boolean
    required: false
    category: binary
```

#### Field properties

- `dtype` (required in full form):
  - Typical values: `string`, `boolean`, `integer`, `number`
- `required` (optional):
  - `true` → the field must be present in each record
- `category` (optional):
  - Allowed categories:
    - `ordinal`
    - `nominal`
    - `continuous`
    - `binary`
    - `set`

---

## 5. Section comparison behavior (`component`)

### 5.1 Required keys
At minimum, after defaults are applied, these must resolve to valid values:
- `component.comparator`
- `component.match_key`

### 5.2 `component.match_key`
A field name from `record_schema` used to identify a record uniquely.

Example:
```yaml
component:
  match_key: packageAID
```

### 5.3 `component.show_key` (optional)
A field name from `record_schema` used as a human-friendly label in the report.

Example:
```yaml
component:
  show_key: packageName
```

### 5.4 `component.include_matches`
When true, the report JSON may include a `matches` array alongside `diffs`.

Example:
```yaml
component:
  include_matches: true
```

### 5.5 Thresholds
Thresholds are used by comparators that support severity decisions based on how many items changed.

Buggy at the moment

Example:
```yaml
component:
  threshold_ratio: 0.20
  threshold_count: 10
```

---

## 6. Report configuration (`report`)

Report configuration controls what is rendered in HTML.

### 6.1 `report.types`

Two forms are supported:

#### Simple list form
```yaml
report:
  types: ["table", "radar"]
```

#### Structured form (type + optional variant)
```yaml
report:
  types:
    - type: table
      variant: cplc
    - type: radar
```

Supported visualization types commonly include:
- `table`
- `chart`
- `radar`

(Availability depends on the build and installed visualizations.)

### 6.2 Table variants
When a table variant is requested, the renderer attempts to load the matching variant implementation.

Example:
```yaml
report:
  types:
    - type: table
      variant: cplc
```

If only `table` is specified (no variant), the default table renderer is used.

### 6.3 Theme
Theme is typically configured in defaults and applied to the whole report:

```yaml
defaults:
  report:
    theme: dark
```

Valid values:
- `light`
- `dark`

### 6.4 Optional doc/readme link
Some builds support adding a documentation reference per section:

```yaml
report:
  doc: docs/cplc.txt
```

This is intended for short module explanations without making the YAML overly long.

### 6.5 Chart labels (performance schemas)
Performance schemas may provide axis label hints:

```yaml
report:
  types: ["chart", "table", "radar"]
  x_axis: "Reference avg (ms)"
  y_axis: "Profile avg (ms)"
```

These fields are consumed by visualization code that understands them (typically performance charts).

---

## 7. Target options (`target`)

`target` is comparator-specific configuration. Its keys and semantics depend on the comparator.

### 7.1 Example: CPLC comparator options
```yaml
target:
  value_field: value
  compare_first_token: true
```

Typical meaning:
- `value_field`: which record field holds the value to compare (e.g., `value`)
- `compare_first_token`: when true, only the first token of a value string is compared (e.g., compare `"6155"` from `"6155 (2016-06-03)"`)

---

## 8. Complete examples

### 8.1 Packages (basic comparator)
```yaml
schema_version: "0.11"

defaults:
  data:
    type: list
  report:
    types: ["table"]
  component:
    comparator: basic
    include_matches: true
    threshold_ratio: 0
    threshold_count: 0
  target: {}

sections:
  packages:
    data:
      record_schema:
        packageAID:   { dtype: string, required: true }
        packageName:  { dtype: string, required: true }
        version:      { dtype: string, required: true }
    component:
      match_key: packageAID
      show_key: packageName

  fullPackages:
    data:
      record_schema:
        fullPackageAID:          { dtype: string, required: true }
        isSupported:             { dtype: boolean, required: true }
        packageNameWithVersion:  { dtype: string, required: true }
    component:
      match_key: fullPackageAID
      show_key: packageNameWithVersion
```

### 8.2 Algorithm performance (algperf comparator)
```yaml
schema_version: "0.11"

defaults:
  data:
    type: list
    record_schema:
      algorithm:           { dtype: string,  category: nominal,    required: true }
      op_name:             { dtype: string,  category: nominal }
      measurement_config:  { dtype: string,  category: nominal }
      avg_ms:              { dtype: number,  category: continuous }
      min_ms:              { dtype: number,  category: continuous }
      max_ms:              { dtype: number,  category: continuous }
      baseline_avg_ms:     { dtype: number,  category: continuous }
      baseline_min_ms:     { dtype: number,  category: continuous }
      baseline_max_ms:     { dtype: number,  category: continuous }
      data_length:         { dtype: integer, category: continuous }
      total_iterations:    { dtype: integer, category: continuous }
      total_invocations:   { dtype: integer, category: continuous }
      error:               { dtype: string,  category: nominal }
      notes:               { dtype: string,  category: nominal }

  component:
    comparator: algperf
    match_key: algorithm
    show_key: op_name
    threshold_ratio: 0.20
    include_matches: true

  report:
    types: ["chart", "table", "radar"]
    x_axis: "Reference avg (ms)"
    y_axis: "Profile avg (ms)"

sections:
  MESSAGE_DIGEST: {}
  RANDOM_GENERATOR: {}
```

### 8.3 Algorithm support (basic comparator)
```yaml
schema_version: "0.11"

defaults:
  data:
    type: list
    record_schema:
      name:  { dtype: string, required: true, category: nominal }
      value: { dtype: string, category: binary }
  report:
    types: ["table", "radar"]
  component:
    comparator: basic
    match_key: name
    show_key: name
    include_matches: true
  target: {}

sections:
  "javacardx.crypto.Cipher": {}
  "javacard.crypto.Signature": {}
  "javacard.security.MessageDigest": {}
  "javacard.security.RandomData": {}
  "javacard.security.KeyBuilder": {}
  "javacard.security.KeyAgreement": {}
  "javacard.security.Checksum": {}
  "javacard.security.KeyPair ALG_RSA on-card generation": {}
  "javacard.security.KeyPair ALG_RSA_CRT on-card generation": {}
  "javacard.security.KeyPair ALG_DSA on-card generation": {}
  "javacard.security.KeyPair ALG_EC_F2M on-card generation": {}
  "javacard.security.KeyPair ALG_EC_FP on-card generation": {}
  "javacardx.crypto.AEADCipher": {}
```

### 8.4 ATR + CPLC with table variant and theme
```yaml
schema_version: "0.12"

defaults:
  data:
    type: list
  component:
    comparator: basic
    match_key: __override__
  target: {}
  report:
    theme: dark

sections:
  ATR:
    data:
      record_schema:
        name:  { dtype: string, required: true, category: nominal }
        value: { dtype: string, category: nominal }
    component:
      comparator: basic
      match_key: name
      show_key: name
      include_matches: true
    report:
      types: ["table"]
      doc: docs/cplc.txt

  CPLC:
    data:
      record_schema:
        field: { dtype: string, required: true, category: nominal }
        value: { dtype: string, category: nominal }
    component:
      comparator: cplc
      match_key: field
      show_key: field
      include_matches: true
    target:
      value_field: value
      compare_first_token: true
    report:
      types:
        - type: table
          variant: cplc
```

---

## 9. Merging and overrides

- Defaults are merged into section configurations.
- Section values override defaults.
- Comparator-specific knobs should be placed under `target`.
- Section visuals should be controlled using `report.types`.

