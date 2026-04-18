# Troubleshooting

This document covers common CLI and workflow issues.

## First step: confirm which plugins are available

Before debugging a mapper, comparator, or visualization problem, first confirm which plugins were actually discovered in the current environment.

Use:

```bash
python scrutinize.py map --list-mappers
python scrutinize.py verify --list-comparators
python scrutinize.py report --list-viz
```

These commands help verify whether a name, alias, or expected plugin is available before running a full workflow.

## A CSV input needs a mapper type

Typical message:

> reference input '...' is CSV, so a mapper type is required

This happens when you use `full` or `batch-verify` with raw inputs but do not specify a mapper.

Use either:

```bash
-t <mapper>
```

or side-specific types:

```bash
--reference-type <mapper> --profile-type <mapper>
```

If you are unsure which mapper name to use, run:

```bash
python scrutinize.py map --list-mappers
```

## Unknown mapper type

Typical message:

> Unknown mapper type 'X'

Check that:

- the mapper exists
- the mapper name or alias is correct
- plugin autodiscovery is loading the expected mapper package

You can confirm the discovered mapper set with:

```bash
python scrutinize.py map --list-mappers
```

## Comparator not found

Typical message:

> Comparator 'X' not found

Check that:

- the comparator plugin exists
- the schema uses the correct comparator name
- comparator autodiscovery is working

You can confirm the discovered comparator set with:

```bash
python scrutinize.py verify --list-comparators
```

## No report blocks are shown

If a table, chart, radar, or heatmap is missing:

- confirm that the section has `report.types` in the schema
- confirm that the requested viz plugin exists in the current build
- if a table variant is requested, confirm that the variant is implemented

You can confirm the discovered viz set with:

```bash
python scrutinize.py report --list-viz
```

## HTML was generated, but styles or buttons do not work

Check that:

- report asset loading succeeded during report generation
- if linked mode is used, CSS and JS are present next to the report or in the bundle
- if inline mode is used, the assets were successfully read and embedded

## Batch verification found no profiles

Typical message:

> No profile inputs found.

Check that:

- `--profiles-dir` points to an existing directory
- the directory actually contains files or mapper-supported source folders
- or use `--profiles` with an explicit list of inputs

## A directory mapper was used incorrectly

Some mappers support directories and some do not.

If you see a message such as:

> Mapper 'X' does not accept directory input

then either:

- pass a file instead of a directory
- or use a mapper that is designed for directory-based input

If you are unsure whether the mapper you want exists in the current build, first run:

```bash
python scrutinize.py map --list-mappers
```

## Dynamic sections do not appear

If you expect unknown sections to be adopted dynamically:

- confirm that the schema has `ingest.dynamic_sections: true`
- confirm that defaults provide enough data to build a usable section definition
- confirm that the dynamic section rows contain the required match field

## The report was generated, but some images are missing

For trace-style reports, missing images usually mean one of these:

- the mapped data points to a path that does not exist
- the comparator did not preserve enough image metadata
- the report bundle could not resolve or copy the referenced asset

If the HTML contains an `<img>` tag but the image is not visible, verify the referenced `src` path first.

## Good information to include when reporting a problem

When opening an issue or asking for help, include:

- the exact command you ran
- the schema you used
- whether the inputs were JSON, CSV-like, or directory-based
- the exact error output
- your Python version
- your operating system
- the output of `--list-mappers`, `--list-comparators`, or `--list-viz` when relevant
