# JobSpy integration

This app uses **python-jobspy** (PyPI: `python-jobspy`) to scrape job boards. The [pythonhosted.org/jobspy](https://pythonhosted.org/jobspy/jobs.html) docs are for a different library (jobs.py, Redis job locking). Our scraper is [python-jobspy](https://pypi.org/project/python-jobspy/).

## Supported sites (8)

Only these site names work; others cause API errors:

- **indeed**, **linkedin**, **zip_recruiter**, **glassdoor**, **google**
- **bayt**, **naukri**, **bdjobs**

Presets (popular / remote / all) use only these. For **Naukri** (India) use `country=india`. For **Indeed/Glassdoor** use `country=usa` (default), `india`, `uk`, etc.

## API: `GET /jobspy`

| Param        | Description |
|-------------|-------------|
| `q`         | Search term |
| `location`  | Location (e.g. Remote, Pune, USA) |
| `days`      | Max age of jobs (1–30) |
| `limit`     | Max results (1–400) |
| `sites`     | Comma-separated: `indeed,linkedin,naukri` |
| `preset`    | `popular`, `remote`, or `all` |
| `country`   | For Indeed/Glassdoor: `usa`, `india`, `uk`, etc. (default: `usa`) |
| `is_remote` | Filter for remote-only jobs |
| `skip_cache`| If `true`, bypass server cache and re-scrape (default: `false`) |

**Caching:** Responses are cached in-memory for 15 minutes (key = params). Use `skip_cache=true` to force a fresh scrape. Response headers: `X-Cache: HIT|MISS`, `Cache-Control: private, max-age=900`.

## Behavior

- **Per-site scraping**: Each board is scraped separately and results are merged. If one site fails (e.g. rate limit), others still return.
- **country_indeed**: Passed to python-jobspy; required for Indeed/Glassdoor domains. Use `india` for Naukri-focused searches.

## JobSpy.tech (external)

[jobspy.tech](https://www.jobspy.tech/jobs) is a separate job search app. The local UI has a **JobSpy.tech** page that opens it in a new tab, optionally with query/location params.

## JobSpy MCP Server

For use inside **Claude Desktop** or **Cursor** (local Python, no API key), you can use the [JobSpy MCP Server](http://lobehub.com/mcp/yourorg-jobspy-mcp-server). It exposes tools like `scrape_jobs_tool` with the same python-jobspy library. Configure it in your MCP client; it does not run inside this web app.
