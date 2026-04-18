# 1. How the plugin system works

The plugin setup in scrutiny-viz is meant to make **mappers**, **comparators**, and **visualizations** easier to extend without repeatedly editing core service files.

The basic idea is the same in all three areas:

* there is a **contract/base definition** that says what a plugin must implement
* there is a **registry** that keeps track of available plugins
* plugins live in a dedicated package folder
* built-in plugins are loaded through **autodiscovery**
* the service layer asks the registry for the requested plugin and runs it

So instead of writing a new module and then wiring it manually in several unrelated places, the intended flow is:

1. create a new plugin file in the correct folder
2. expose the plugin in that module
3. let autodiscovery load it
4. use it by name through CLI, schema, or service logic

This gives scrutiny-viz a more consistent internal extension model.

## 1.0.1 Common pattern

Even though mapper, comparator, and viz do different work, they follow the same shape:

* **Contracts** define the public API
* **Plugin modules** hold the actual implementation
* **Registry** resolves canonical names and aliases
* **Service** orchestrates execution, but should not contain the implementation logic itself

A useful mental model is:

* **plugin file** = the real behavior
* **registry** = name lookup and discovery
* **service** = workflow/orchestration

## 1.0.2 Discovery model

The project does **not** use external plugins.

That means plugins are:

* stored inside the repository
* loaded from known package folders
* discovered by scanning those folders

This is important because the goal is modularity **inside the project**, not third-party extension installation.

---

# 1.1 Specifics of mapper plugins

Mapper plugins are responsible for converting source input into the normalized JSON structure used by scrutiny-viz.

The important thing to have in mind is that **ingest is owned by the mapper plugin**, not by `service.py`. That means the mapper layer now supports both:

* a **default grouped-text ingest path** for existing CSV-like mappers
* **custom ingest** for special sources such as RSABias directory bundles

## 1.1.1 Purpose

A mapper plugin should:

* parse one input format or bucket family
* transform raw input into normalized sections
* return a dictionary payload ready for further processing

A mapper plugin should **not**:

* write files directly
* perform CLI argument handling
* decide report rendering
* perform verification

## 1.1.2 Folder layout

The current intended structure is:

```text
mapper/
  cli.py
  mapper_utils.py
  registry.py
  service.py
  mappers/
    __init__.py
    contracts.py
    jcaid.py
    jcperf.py
    jcalg_support.py
    tpm.py
    rsabias.py
    ....
```

## 1.1.3 Mapper contract

A mapper plugin implements the mapper contract from `mapper/mappers/contracts.py`.

Conceptually, a mapper plugin contains:

* a spec with its canonical name, aliases, and description
* an ingest step that loads the source input into an internal representation
* a mapping step that transforms that representation into the normalized JSON structure
* a public entry point used by the rest of the system

In the current design, the public entry point is map_path(...).
This method represents the standard plugin interface for mapping a source path. Internally, it performs the ingest phase and then calls the mapping phase.

The contract supports two practical styles:

### A. Default grouped-text mappers

These mappers use the default contract behavior:

* `ingest(...)` loads grouped text as grouped text
* `map_source(...)` forwards that grouped-text representation to `map_groups(...)`

This is the standard path for CSV-like and text-based mappers.

### B. Custom-source mappers

These mappers override `ingest(...)`, and optionally `map_source(...)`, when the source is not naturally handled as grouped text.

This is used for source types such as:

directory-based inputs
structured JSON inputs
other non-grouped source formats

Examples in the current codebase include **rsabias**, **traceclassifier**, and **tracescompare**.

## 1.1.4 Registry role

The mapper registry should:

* discover built-in mapper modules from `mapper.mappers`
* register mapper names and aliases
* resolve canonical mapper type names
* return the mapper plugin when requested

The mapper registry should **not** contain the actual parsing logic.

## 1.1.5 Service role

The mapper service should stay relatively thin.

It should handle:

* resolving the mapper plugin
* building the mapping context
* calling the selected plugin
* applying generic exclusions if needed
* writing output JSON
* handling output path decisions

It should **not** contain mapper-specific parsing logic.

In other words, the service coordinates mapping, but it should not decide how a source file or source directory is parsed.

## 1.1.6 Ingest strategy

The mapper layer now follows this rule:

* **simple mappers** should use the default grouped-text ingest from the contract
* **special mappers** should override `ingest(...)` and, if needed, `map_source(...)`

This avoids two bad extremes:

* forcing every mapper to reimplement trivial file loading
* forcing the service layer to know how every source type must be loaded

So the preferred design is:

* default ingest in the contract
* shared helper functions in `mapper_utils.py`
* custom ingest only when the source format truly needs it

## 1.1.7 Role of `mapper_utils.py`

`mapper_utils.py` is now best understood as the shared helper layer for mapper ingest and parsing support.

It is a good place for generic helpers such as:

* loading grouped text
* loading JSON
* listing files in a directory
* basic conversions
* generic parsing helpers
* exclusion helpers

It is **not** the place for format-specific business logic.  
For example, RSABias-specific interpretation should stay in `rsabias.py`, not in `mapper_utils.py`.

## 1.1.8 Examples of current mapper styles

Examples of normal grouped-text mappers in the project include:

* `tpm`
* `jcperf`
* `jcaid`
* `jcalgsupport`

These still follow the grouped-text pattern and implement `map_groups(...)`.

The current special-case mapper is:

* `RSABias`
* `TraceClassifier`
* `TraceComparer`

This mapper overrides ingest because its source is a directory containing multiple JSON/text artifacts that must be combined into one normalized output.

## 1.1.9 How to add a new mapper

Typical steps:

1. create a new file in `mapper/mappers/`
2. implement the mapper contract
3. define a spec with a canonical name and aliases
4. decide whether the mapper uses:
   * the default grouped-text ingest, or
   * a custom ingest path
5. expose the plugin from the module through `PLUGINS`
6. run mapping through the registry name

This means adding a mapper should ideally not require edits in unrelated service files, but may still require new schemas, tests or report-side additions.

## 1.1.10 Practical naming rule

Aliases are useful for CLI ergonomics, but the project should still use one canonical internal name.

That means:

* users may type an alias
* the registry resolves it
* the rest of the system works with the canonical mapper name

---

# 1.2 Specifics of comparator plugins

Comparator plugins are responsible for comparing normalized sections from reference and tested/profile JSONs.

## 1.2.1 Purpose

A comparator plugin should:

* compare one kind of section data
* produce structured comparison output
* report matches, differences, and metadata in a normalized way

A comparator plugin should **not**:

* load files directly
* choose schemas
* render HTML
* perform final report composition

## 1.2.2 Folder layout

The intended structure is:

```text
verification/
  __init__.py
  service.py
  cli.py
  comparators/
    __init__.py
    verification/comparators/utility.py
    contracts.py
    registry.py
    basic.py
    algperf.py
    cplc.py
    ...
```

## 1.2.3 Comparator contract

A comparator plugin implements the comparator contract defined in `verification/comparators/contracts.py`.

At a practical level, a comparator plugin defines:

* a **spec** that provides its canonical name, aliases, and description
* a **`compare(...)` method** that performs the actual section comparison
* a **normalized result structure** that can be consumed by the verification and reporting layers

The `compare(...)` method receives:

* the section name
* the key field
* the display field
* metadata derived from schema configuration
* reference rows
* tested/profile rows

It returns a structured comparison result. In the current design, this typically includes:

* `counts` / `stats`
* `labels` / `key_labels`
* `diffs`
* optional `matches`
* optional `artifacts`

Some comparators may also return additional reporting-support fields when needed, such as source row snapshots or an explicit override of the section result.

The important point is that comparator plugins should return data in a normalized shape, so the verification service and report layer do not need to know the internal comparison logic of individual comparators. 

## 1.2.4 Registry role

The comparator registry should:

* autodiscover comparator modules
* register canonical names and aliases
* return comparator plugins by name

## 1.2.5 Service role

The verification service should coordinate the verification workflow.

It should handle:

* loading the schema
* loading and parsing the reference and tested/profile JSON inputs
* selecting the appropriate comparator based on schema configuration
* passing normalized section rows and metadata into the comparator
* collecting section-level comparison results
* assembling the final verification JSON structure
* optionally triggering report generation when requested

It should **not** contain comparator-specific comparison algorithms.

In other words, the verification service is responsible for orchestration, aggregation, and output generation, while the comparator plugins remain responsible for the actual section comparison logic. This separation keeps comparator behavior modular and prevents the service layer from accumulating format-specific comparison code. 

## 1.2.6 Why comparators are especially important

Comparators are the main bridge between:

* normalized mapped data
* schema rules
* final report content

If comparators are consistent, the rest of the pipeline stays much cleaner.

## 1.2.7 How to add a new comparator

Typical steps:

1. create a file in `verification/comparators/`
2. implement the comparator contract
3. define spec, aliases, and compare logic
4. expose the plugin from the module
5. reference it by canonical name from the schema configuration. The verification service resolves that name through the comparator registry

---

# 1.3 Specifics of viz plugins

Viz plugins are responsible for producing visual output blocks used in reports.

## 1.3.1 Purpose

A viz plugin should:

* render one visualization type
* accept already-prepared section data or section-level inputs
* return HTML/DOM nodes used by the report renderer

A viz plugin should **not**:

* build the full report page
* load report JSON files
* manage CSS/JS assets globally
* decide workflow orchestration

## 1.3.2 Folder layout

The intended structure is:

```text
report/
  service.py
  cli.py
  bundle.py
  viz/
    __init__.py
    contracts.py
    registry.py
    chart.py
    radar.py
    donut.py
    table.py
    ...
```

## 1.3.3 Viz contract

A viz plugin implements the contract defined in `report/viz/contracts.py`.

At a practical level, a viz plugin defines:

its identity through a spec
its slot in the current design
a `render(...)` method that returns renderable content

In the current design, the spec contains:

a canonical plugin name
a slot
optional aliases
an optional description

The render method is the actual plugin entry point. It receives prepared inputs from the report layer and returns content that can be inserted into the generated report.

A viz plugin should focus only on the visualization itself.

Examples in this project include:

* chart
* radar
* donut
* heatmap
* table

## 1.3.4 Registry role

The viz registry should:

* autodiscover viz modules
* register names and aliases
* return viz plugins by name

This allows the report layer to ask for a visualization by type instead of using hardcoded dispatch maps.

## 1.3.5 Service role

The report service should coordinate full report generation.

It should handle:

* loading the verification JSON
* preparing any bundled assets needed by the report
* resolving requested viz types from the registry
* assembling the full HTML document
* inserting the returned render blocks into the document
* writing the final HTML output
* optionally preparing zip output

It should not keep the actual chart, radar, donut, heatmap, or table rendering logic inside itself.

## 1.3.6 What should stay outside viz

Not everything belongs in viz plugins.

The following are report-level concerns rather than viz concerns:

* page layout
* intro blocks
* overall module ordering
* file writing
* zip creation
* CSS/JS loading
* report bundling

So the correct modular split is:

* `report/service.py` = orchestration and page assembly
* `report/bundle.py` = report asset preparation and bundling support
* `report/viz/*` = visualization implementation
* `report/viz/utility.py` = shared visualization helpers

## 1.3.7 How to add a new viz plugin

Typical steps:

1. create a file in `report/viz/`
2. implement the viz contract
3. define plugin spec and render method
4. expose the plugin from the module
5. reference it through report configuration or section report types

---

# 1.4 Summary of the plugin situation

The plugin situation can be summarized like this:

* **Mapper plugins** transform raw or preprocessed input into normalized JSON
* **Comparator plugins** compare normalized JSON sections
* **Viz plugins** render visual blocks for the report

All three follow the same architectural rule:

* implementation lives in plugin modules
* registration/discovery lives in a registry
* orchestration lives in service code

For mappers specifically, the important refinement is:

* ingest belongs to the plugin layer
* the contract provides a default ingest path
* special formats override ingest when needed

That is the core design principle behind the newer scrutiny-viz structure.

---

# 1.5 Recommended practical rules for future additions

When adding any new plugin type, follow these rules:

1. put the real logic in the plugin file, not in the service
2. keep the registry responsible only for discovery and lookup
3. keep aliases user-friendly, but use one canonical internal name
4. keep service code focused on orchestration
5. keep generic ingest helpers in shared utilities, not in the service
6. only override ingest when the source format truly needs it
7. test autodiscovery with an isolated test package
8. avoid hidden side effects outside the registry/discovery path

These rules help keep scrutiny-viz modular without making it overly abstract or hard to debug.

---

# 1.6 Final takeaway

The plugin system in scrutiny-viz is build on a consistent internal architecture:

* **mappers** parse and normalize input
* **comparators** compare normalized structures
* **viz plugins** render report visuals

The most important idea is consistency.

Every time a new building block is added, it should follow the same broad pattern:

* define the contract
* implement the plugin
* expose it for autodiscovery
* resolve it through the registry
* run it from the service layer

For mapper plugins, that now also means:

* let the contract handle the common ingest case
* let the mapper override ingest only when needed

That is what makes the project feel modular instead of just split across many files.