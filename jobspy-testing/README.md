# JobSpy local testing

Local runbook for [JobSpy](https://github.com/speedyapply/JobSpy) (LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, etc.). Uses **Uv** for dependencies (with pip fallback). Structured for future conversion to a [Marimo](https://marimo.io) notebook (memory-conscious: small batches, minimal globals).

## Setup (Uv, preferred)

Install [Uv](https://docs.astral.sh/uv/) if needed (`pip install uv` or see astral.sh/uv). From this folder:

```bash
uv sync
```

## Setup (pip fallback)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Run the notebook

**With Uv:**

```bash
uv run jupyter notebook jobspy_test.ipynb
```

**With pip venv:** activate `.venv`, then:

```bash
jupyter notebook jobspy_test.ipynb
```

Or open `jobspy_test.ipynb` in VS Code/Cursor and select the kernel from `.venv` (e.g. `jobspy-testing\.venv`).

## Quick test from CLI

**Uv:** `uv run python -c "from jobspy import scrape_jobs; ..."`  
**Pip:** activate venv then:

```bash
python -c "from jobspy import scrape_jobs; df = scrape_jobs(site_name=['indeed'], search_term='software engineer', results_wanted=5, verbose=0); print(df.shape); print(df[['title','company','job_url']].head())"
```

## Marimo later

- Keep cells small and single-purpose.
- Prefer small `results_wanted` to avoid large in-memory DataFrames.
- After exporting to CSV, you can `del jobs` in a cell to free memory when converting to Marimo's reactive model.
