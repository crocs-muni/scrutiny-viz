# scrutiny-viz

Compare two smart-card measurement profiles (JSON) using a YAML schema and generate:

- a machine-readable comparison JSON, and
- a self-contained HTML report.

The project is modular: comparators, schemas, and visualizations can be extended without rewriting the core.

---

## What you get

- **`verify.py`**: compares reference vs profile using a schema  
- **`report_html.py`**: turns the verification JSON into an HTML report  
- **`data/style.css` + `data/script.js`**: report styling/behavior  
- **YAML schemas**: define sections, comparators, and report visuals (`report.types`)

---

## Requirements

- **Python**: 3.9+ recommended
- **pip**: installed with Python

Python dependencies (from `requirements.txt`):

- `dominate~=2.9.1`
- `jsonpickle~=2.0.0`
- `flake8~=3.9.0`
- `overrides~=7.7.0`
- `PyYAML~=6.0.2`

---

## Setup

### 1) Clone
```bash
git clone https://github.com/crocs-muni/scrutiny-viz.git
cd https://github.com/crocs-muni/scrutiny-viz.git
```

### 2) (Recommended) Create a virtual environment

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks activation:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Run tests to check complete repo

```bash
python -m pytest -q -rs
```

---

## Verify (generate comparison JSON)

### Help
```bash
python verify.py -h
```

### Generic example
```bash
python verify.py \
  -s path/to/schema.yml \
  -r path/to/reference.json \
  -p path/to/profile.json \
  -o results/comparison.json
```

### CPLC example
```powershell
python verify.py `
  -s .\scrutiny\javacard\modules\jcCPLC.yml `
  -r ".\data\examples\CSOB VISA debit.json" `
  -p ".\data\examples\CSOB VISA debit.json" `
  -o test.json `
  -v --print-diffs 100 --print-matches 100 -rep
```

---

## Generate HTML report

### Help
```bash
python report_html.py -h
```

### Example
```bash
python report_html.py -p test.json -o comparison.html -v
```

The report is written to the `results/` folder (depending on your script config), typically:
- `results/comparison.html`

---

## Report visuals (YAML)

Each section can specify what is rendered using `report.types`.

### Example: table only
```yaml
report:
  types: ["table"]
```

### Example: table variant (CPLC)
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

> If your build uses “strict types from YAML”, only visuals listed in `report.types` will be shown.

---

## Common issues

### “comparator 'X' not found; falling back to 'basic'”
- Make sure the comparator is registered/imported.
- Ensure the schema uses the correct comparator name.

### “No table/radar/chart is shown”
- Confirm the section has `report.types` set in YAML.
- Confirm your “strict YAML” behavior if enabled (no inference).

### “Show All / Hide All / Default doesn’t work”
- Ensure `data/script.js` is present and loaded.
- Ensure toggle blocks are created via `show_hide_div(...)` so they get the right HTML attributes.

---

## Development

## Suggested repo structure (example)

```
scrutiny/
  reporting/
    viz/
  htmlutils.py
  ...
data/
  examples/
    *.json
  style.css
  *.json
  script.js
schemas/
  *.yml
tests/
verify.py
report_html.py
```

---
