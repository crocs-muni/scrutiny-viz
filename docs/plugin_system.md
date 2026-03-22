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

The most important recent change is that **ingest is now owned by the mapper plugin**, not by `service.py`. That means the mapper layer now supports both:

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
```

## 1.1.3 Mapper contract

A mapper plugin implements the mapper contract from `mapper/mappers/contracts.py`.

Conceptually, a mapper plugin contains:

* a **spec** with name and aliases
* the actual parsing logic
* an ingest path for its source type
* a public method used by the rest of the system

The current contract supports two practical styles:

### A. Default grouped-text mappers

These mappers use the default contract behavior:

* `ingest(...)` loads grouped text
* `map_source(...)` forwards to `map_groups(...)`

This is the normal path for the existing text/CSV-like mappers.

### B. Custom-source mappers

These mappers override ingest behavior when the input is not just one grouped-text file.

This is the path used by RSABias, where the mapper reads a **directory** containing several result files and combines them into one normalized output.

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

* `rsabias`

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

This means adding a mapper should ideally not require edits in unrelated service files.

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
  service.py
  comparators/
    __init__.py
    contracts.py
    registry.py
    basic.py
    algperf.py
    cplc.py
```

## 1.2.3 Comparator contract

A comparator plugin should define:

* its identity through a spec
* a compare method
* normalized return data expected by verification and report layers

The compare step usually receives:

* section name
* key field
* display field
* metadata
* reference rows
* tested rows

And it returns a structured result with things like:

* diffs
* matches
* labels
* counts/stats
* optional visualization artifacts

## 1.2.4 Registry role

The comparator registry should:

* autodiscover comparator modules
* register canonical names and aliases
* return comparator plugins by name

## 1.2.5 Service role

The verification service should:

* load reference and tested JSON
* read schema instructions
* choose the appropriate comparator
* collect comparison results
* produce verification JSON

It should not contain comparator-specific comparison algorithms.

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
5. reference it by name from verification logic or schema-driven selection

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
  viz/
    __init__.py
    contracts.py
    registry.py
    chart.py
    radar.py
    donut.py
    table.py
```

Legacy files under `scrutiny/reporting/viz/...` may still exist for compatibility, but the long-term goal is that the real implementation lives in `report/viz/`.

## 1.3.3 Viz contract

A viz plugin should define:

* its identity/spec
* the slot or role if the current design uses one
* a render method returning nodes or renderable content

A viz plugin should focus on the visualization itself.

Examples in this project include:

* chart
* radar
* donut
* table

## 1.3.4 Registry role

The viz registry should:

* autodiscover viz modules
* register names and aliases
* return viz plugins by name

This allows the report layer to ask for a visualization by type instead of using hardcoded dispatch maps.

## 1.3.5 Service role

The report service should:

* orchestrate full report generation
* resolve requested viz types from the registry
* insert the returned nodes into the document

It should not keep the real chart/radar/donut/table implementation logic inside itself.

## 1.3.6 What should stay outside viz

Not everything belongs in viz plugins.

The following are report-level concerns rather than viz concerns:

* page layout
* intro blocks
* overall module ordering
* file writing
* zip creation
* CSS/JS loading

So the correct modular split is:

* `report/service.py` = orchestration
* `report/viz/*` = visualization implementation
* optional future report-specific helpers = page/rendering support

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

The plugin system in scrutiny-viz is moving toward a consistent internal architecture:

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