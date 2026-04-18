# Test structure overview

The test suite is organized by responsibility so that the main layers of the project can be validated independently, while still keeping practical confidence through selected workflow tests.

## Scope note

The test suite is intended to provide practical confidence in the main behaviors and workflows of the project. It does not imply that all code paths, edge cases, or integrations are covered by automated tests.

Some parts of the codebase are tested directly, some only indirectly through higher-level tests, and some may currently have limited coverage.

## `tests/workflow/` → user-level confidence

Workflow tests provide end-to-end confidence from a user perspective.

They validate representative project flows where multiple layers are combined together, such as generating reports from prepared verification JSON or running larger integrated command paths.

These tests answer the question:

> Does the tool work correctly as a complete workflow?

## `tests/mapper/` → normalization confidence

Mapper tests validate the normalization layer.

Their purpose is to check that supported source inputs are transformed into the expected normalized JSON structure used by later stages of the pipeline.

These tests focus on:

- output shape
- required fields
- field normalization
- mapper-specific section structure

These tests answer the question:

> Does a mapper produce the normalized contract expected by verification and reporting?

## `tests/comparators/` → diff logic confidence

Comparator tests validate section-level comparison behavior.

They check that comparator plugins correctly detect matches, differences, missing items, extra items, and comparator-specific change semantics.

These tests answer the question:

> Does the comparison layer produce the expected diff logic and section-level comparison output?

## `tests/viz/` → rendering confidence

Viz tests validate visualization rendering behavior.

They check that visualization plugins are registered correctly and that they produce usable render output for prepared section data.

These tests focus on rendering blocks rather than full workflow orchestration.

These tests answer the question:

> Do the visualization plugins render expected output blocks for the report layer?

## Schema-oriented and plugin-oriented tests → architecture confidence

Some tests validate architecture-level behavior such as:

- schema expectations
- ingest behavior
- dynamic section handling
- autodiscovery for mappers, comparators, and viz plugins

These tests answer the question:

> Does the modular architecture behave correctly as a system of discoverable and configurable components?

## Why the test suite is split this way

This structure helps make failures easier to interpret:

- if a mapper test fails, the issue is likely in normalization
- if a comparator test fails, the issue is likely in comparison logic
- if a viz test fails, the issue is likely in rendering
- if a workflow test fails, the issue is likely in integration across layers

The result is a test suite that supports both focused debugging and broader confidence in project behavior.
