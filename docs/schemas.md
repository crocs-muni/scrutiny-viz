# YAML Schema Reference (v0.13)

This document describes the YAML schema format used by **scrutiny-viz 0.13** to drive schema loading, JSON ingest, comparison, and report rendering.

A schema defines:

- which **sections** exist
- how section data is structured (`data.record_schema`)
- how records are matched and compared (`component`)
- which report blocks are rendered (`report`)
- optional comparator-specific options (`target`)
- how ingest should behave for missing or unknown sections (`ingest`)

---

# 1. Top-level structure

```yaml
schema_version: "0.13"

ingest:           # optional but strongly recommended in 0.13
  dynamic_sections: false
  strict_sections: false
  allow_missing_sections: true

defaults:         # optional but recommended
  data: ...
  component: ...
  report: ...
  target: ...

sections:         # required unless the schema is intended to rely on dynamic sections
  <SECTION_NAME>: ...
```

## 1.1 `schema_version` (required)

A string identifying the schema format version.

For the current format, use:

```yaml
schema_version: "0.13"
```

---

# 2. `ingest`

Version `0.13` supports explicit top-level ingest behavior.

Example:

```yaml
ingest:
  dynamic_sections: true
  strict_sections: false
  allow_missing_sections: true
```

## 2.1 `ingest.dynamic_sections`

Controls whether unknown input sections may be adopted dynamically during ingest.

Example:

```yaml
ingest:
  dynamic_sections: true
```

Meaning:

- `false`  
  Only schema-declared sections are accepted. Should be used in strict and predictable environments such as CI/CD pipelines.

- `true`  
  Unknown sections found in the input may be accepted and normalized using defaults.

This is useful when many similarly shaped sections exist and you do not want to enumerate all of them explicitly.

### Important note

Dynamic section adoption only works well when `defaults` contains enough information to build a usable section definition, especially:

- `defaults.data.record_schema`
- `defaults.component`
- `defaults.report`

---

## 2.2 `ingest.strict_sections`

Controls how unknown input sections are handled.

Example:

```yaml
ingest:
  strict_sections: true
```

Meaning:

- `false`  
  Unknown sections may be ignored or dynamically adopted, depending on other settings.

- `true`  
  Unknown sections should be treated as an ingest error.

Use `strict_sections: true` when the schema must fully define the accepted structure.

---

## 2.3 `ingest.allow_missing_sections`

Controls whether declared schema sections may be missing from the input JSON.

Example:

```yaml
ingest:
  allow_missing_sections: true
```

Meaning:

- `true`  
  Missing sections are allowed.

- `false`  
  Missing declared sections should be treated as an ingest error.

This is useful when a schema represents a required complete profile.

---

# 3. `defaults`

`defaults` defines baseline configuration inherited by all sections.

Any section may override any part of `defaults`.

Using `defaults` is strongly recommended when many sections share the same structure, comparator, or report configuration.

---

## 3.1 `defaults.data`

```yaml
defaults:
  data:
    type: list
```

### Supported keys

- `type`
- `record_schema`

### `type`

Currently expected value:

```yaml
type: list
```

In practice, sections are treated as lists of records.

---

## 3.2 `defaults.component`

```yaml
defaults:
  component:
    comparator: basic
    match_key: __override__
    show_key: __override__
    include_matches: true
    threshold_ratio: 0.0
    threshold_count: 0
```

### Supported keys

- `comparator`
- `match_key`
- `show_key`
- `include_matches`
- `threshold_ratio`
- `threshold_count`

### Meaning

- `comparator`  
  Canonical comparator name used for the section.  
  Typical values include:
  - `basic`
  - `algperf`
  - `cplc`

- `match_key`  
  Field used to match records between reference and profile.

- `show_key`  
  Field used for display labels in outputs and reports.  
  If omitted, implementations usually fall back to `match_key`.

- `include_matches`  
  When `true`, comparison output may include a `matches` array in addition to `diffs`.

- `threshold_ratio`  
  Comparator threshold used when deciding result severity in comparators that support threshold-based evaluation.

- `threshold_count`  
  Additional threshold used by comparators that support absolute-count severity logic.

### Notes

- `comparator` and `match_key` must resolve to valid values after defaults and section overrides are merged.
- `threshold_ratio` and `threshold_count` are meaningful only for comparators that use them.

---

## 3.3 `defaults.report`

```yaml
defaults:
  report:
    types:
      - type: table
        variant: cplc
    theme: dark
```

### Supported keys

- `types`
- `theme`
- `doc`

### Meaning

- `types`  
  Controls which visual blocks are rendered for a section.  
  Each entry may optionally include a `variant`.

- `theme`  
  Global report theme. Common values:
  - `light`
  - `dark`

- `doc`  
  Optional documentation reference for section explanation.

### Important note about `doc`

If `report.doc` is defined and points to a readable file, the loader may load that file and store its contents as `report.doc_text` in the normalized schema structure. This allows the report layer to use ready text instead of reopening the file later.

Example:

```yaml
report:
  doc: docs/cplc.txt
```

The current loader also applies a few restrictions:

- the path must stay within the schema directory
- the file must be `.txt` or `.md`
- extremely large files are rejected

---

## 3.4 `defaults.target`

```yaml
defaults:
  target: {}
```

`target` is a free-form mapping used by comparator-specific implementations.

The meaning of its keys depends on the selected comparator.

---

# 4. `sections`

`sections` is a mapping of:

```yaml
<section name> -> <section configuration>
```

Example:

```yaml
sections:
  ATR:
    ...
  CPLC:
    ...
```

A section may be fully defined, partially defined, or empty if it inherits enough from defaults.

If `ingest.dynamic_sections: true`, a schema may also intentionally keep `sections` minimal or even empty and rely on defaults to construct adopted sections.

---

## 4.1 Fully specified section

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

---

## 4.2 Inherited section

```yaml
sections:
  MESSAGE_DIGEST: {}
  RANDOM_GENERATOR: {}
```

This is valid when `defaults` already provides enough configuration.

---

## 4.3 Dynamic sections

If `ingest.dynamic_sections: true`, input may contain sections not explicitly listed under `sections`.

Those sections may be accepted if defaults contain enough information to construct a compatible definition.

This is especially useful for schemas such as algorithm groups where many similarly shaped sections share one structure.

---

# 5. Section data (`data`)

`data` defines the structure of records expected in a section.

---

## 5.1 `data.type`

Expected value:

```yaml
data:
  type: list
```

---

## 5.2 `data.record_schema`

Defines the shape of a record inside the section list.

Two forms are supported.

### Short form

```yaml
record_schema:
  name: string
  value: string
```

### Full form

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

---

## 5.3 Field properties

### `dtype`

Data type of the field.

Common values:

- `string`
- `boolean`
- `integer`
- `number`

### `required`

Whether the field is expected to be present.

Example:

```yaml
required: true
```

### `category`

Semantic category used by comparators and reporting logic.

Common values:

- `nominal`
- `ordinal`
- `continuous`
- `binary`
- `set`

### Important ingest rule

During ingest, fields marked `required: true` are expected to exist in each record.

In practice, the effective required set should also include the section `match_key`, because matching cannot work if the match field is missing, even if it was not explicitly marked `required: true`.

So when designing schemas, the safe rule is:

- always define `match_key` as a real field in `record_schema`
- strongly prefer marking the `match_key` field as `required: true`

---

# 6. Comparison behavior (`component`)

`component` controls how a section is compared.

---

## 6.1 Required resolved fields

After defaults and section overrides are merged, these should resolve:

- `component.comparator`
- `component.match_key`

`show_key` is optional but usually recommended.

---

## 6.2 `component.comparator`

Comparator identifier used for the section.

Example:

```yaml
component:
  comparator: basic
```

Common values:

- `basic`
- `algperf`
- `cplc`

Use canonical names where possible.

---

## 6.3 `component.match_key`

Field used to identify records between reference and profile.

Example:

```yaml
component:
  match_key: packageAID
```

This field should uniquely identify records within the section.

---

## 6.4 `component.show_key`

Field used as a user-friendly display label.

Example:

```yaml
component:
  show_key: packageName
```

If omitted, implementations commonly fall back to `match_key`.

---

## 6.5 `component.include_matches`

Controls whether matching items are included in the output.

Example:

```yaml
component:
  include_matches: true
```

When enabled, the verification result may include:

- `diffs`
- `matches`

When disabled, only differences may be emitted.

---

## 6.6 `component.threshold_ratio`

Comparator threshold used for severity logic where supported.

Example:

```yaml
component:
  threshold_ratio: 0.20
```

This is typically interpreted as a proportion of changed items among compared items.

---

## 6.7 `component.threshold_count`

Absolute change threshold used where supported.

Example:

```yaml
component:
  threshold_count: 10
```

This is useful when severity should increase after a fixed number of changes even if the ratio remains low.

---

# 7. Report configuration (`report`)

`report` controls how section results are rendered.

---

## 7.1 `report.types`

Two forms are supported.

### Simple form

```yaml
report:
  types: ["table", "radar"]
```

### Structured form

```yaml
report:
  types:
    - type: table
      variant: cplc
    - type: radar
```

### Common visualization types

Current section-level types commonly include:

- `table`
- `chart`
- `radar`

Dashboard-style donut visuals may also exist, but those are usually handled at report/dashboard level rather than section-by-section schema configuration.

### Notes

- `table` may optionally use a `variant`
- visualization availability depends on the runtime/build
- types are normalized by the loader into a consistent internal structure

---

## 7.2 Table variants

A table block may request a specific variant.

Example:

```yaml
report:
  types:
    - type: table
      variant: cplc
```

If no variant is given, the default table renderer is used.

---

## 7.3 `report.theme`

Theme is usually defined under `defaults.report`, because it applies to the whole generated report.

Example:

```yaml
defaults:
  report:
    theme: dark
```

Typical values:

- `light`
- `dark`

---

## 7.4 `report.doc`

Optional documentation reference for the section.

Example:

```yaml
report:
  doc: docs/cplc.txt
```

If the file can be loaded, the loader may store the resolved text as:

```yaml
report:
  doc_text: ...
```

This allows report rendering to consume text directly.

---

## 7.5 Additional report keys

The current normalized loader primarily preserves these report keys:

- `types`
- `theme`
- `doc`
- `doc_text`

If additional visualization-specific report keys are introduced in the future, they should be documented explicitly together with the loader and renderer behavior that supports them.

---

# 8. Comparator-specific `target`

`target` is comparator-specific configuration.

Its meaning depends on the selected comparator.

---

## 8.1 Example: CPLC comparator options

```yaml
target:
  value_field: value
  compare_first_token: true
```

Typical meaning:

- `value_field`  
  Which record field contains the value to compare.

- `compare_first_token`  
  When `true`, only the first token of a value string is compared.

This is useful for values such as:

```text
6155 (2016-06-03)
```

where only the leading token should be used.

---

# 9. Complete examples

## 9.1 Packages (basic comparator)

```yaml
schema_version: "0.13"

ingest:
  dynamic_sections: false
  strict_sections: false
  allow_missing_sections: true

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

---

## 9.2 Algorithm performance (algperf comparator)

```yaml
schema_version: "0.13"

ingest:
  dynamic_sections: true
  strict_sections: false
  allow_missing_sections: true

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

  target: {}

sections:
  MESSAGE_DIGEST: {}
  RANDOM_GENERATOR: {}
```

This pattern is a good candidate for `dynamic_sections: true` when many similar algorithm sections may appear.

---

## 9.3 Algorithm support (basic comparator)

```yaml
schema_version: "0.13"

ingest:
  dynamic_sections: true
  strict_sections: false
  allow_missing_sections: true

defaults:
  data:
    type: list
    record_schema:
      algorithm_name: { dtype: string,  required: true, category: nominal }
      is_supported:   { dtype: string,  category: binary }
  report:
    types: ["table", "radar"]
  component:
    comparator: basic
    match_key: algorithm_name
    show_key: algorithm_name
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

---

## 9.4 ATR + CPLC with table variant and theme

```yaml
schema_version: "0.13"

ingest:
  dynamic_sections: false
  strict_sections: false
  allow_missing_sections: true

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

# 10. Merging and normalization rules

The loader normalizes and merges schema content before ingest and verification.

In practice, the following rules apply:

- defaults are merged into section configurations
- section values override defaults
- `report.types` is normalized into a consistent internal structure
- `report.doc` may be resolved into `report.doc_text`
- ingest behavior is normalized from top-level `ingest`
- dynamic sections may be constructed from defaults when enabled

---

# 11. Practical recommendations

To avoid schema problems, follow these rules:

1. always use `schema_version: "0.13"`
2. always define `ingest`
3. define `match_key` explicitly
4. make the `match_key` field real and preferably `required: true`
5. use `defaults` whenever many sections share the same layout
6. use canonical comparator names
7. use `report.types` for section visualization selection
8. keep comparator-specific knobs under `target`
9. use `dynamic_sections: true` only when defaults are strong enough to define adopted sections safely
10. use `strict_sections: true` only when you want unexpected input sections to fail immediately

---

# 12. Summary

Schema version `0.13` keeps the earlier core ideas of scrutiny-viz schemas, but adds a more explicit and modernized ingest model.

The most important concepts are:

- `sections` define what exists
- `data.record_schema` defines how records look
- `component` defines how comparison works
- `report` defines how rendering works
- `target` holds comparator-specific options
- `ingest` defines how unknown and missing sections are handled

That combination controls the full flow from normalized input through verification output to rendered report.
