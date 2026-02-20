# LinkedIn Jobs Scraper

A Python scraper for LinkedIn job postings using BeautifulSoup. This scraper extracts job listings from LinkedIn's public job search API.

## Files

- **`linkedin-scraper.ipynb`** - Jupyter notebook with interactive scraping interface
- **`linkedin-scraper.py`** - Standalone Python script version
- **`test-linkedin-scraper.py`** - Test script to verify code structure
- **`requirements-linkedin-scraper.txt`** - Python dependencies

## Features

- ✅ Scrapes job listings from LinkedIn
- ✅ Configurable search parameters (keywords, location, max jobs)
- ✅ Rate limiting and retry logic
- ✅ Exports results to JSON and CSV
- ✅ Clean, structured data output
- ✅ Interactive notebook interface

## Installation

### Option 1: Using pip

```bash
pip install -r requirements-linkedin-scraper.txt
```

### Option 2: Manual installation

```bash
pip install requests==2.32.3 beautifulsoup4==4.12.3 tenacity==9.0.0 pandas
```

## Usage

### Using the Jupyter Notebook (Recommended)

1. Open `linkedin-scraper.ipynb` in Jupyter Notebook or JupyterLab
2. Run all cells sequentially
3. Edit the search parameters in the "Configure Search Parameters" cell:
   - `SEARCH_KEYWORDS`: Job title or keywords (e.g., "Data Analyst", "AI/ML Engineer")
   - `SEARCH_LOCATION`: Location (e.g., "London", "San Francisco", "Remote")
   - `MAX_JOBS`: Maximum number of jobs to scrape (e.g., 50, 100)
4. Run the scraping cells
5. View results in the DataFrame or save to JSON/CSV

### Using the Python Script

```bash
python linkedin-scraper.py
```

The script uses default parameters:
- Keywords: "AI/ML Engineer"
- Location: "London"
- Max Jobs: 100

To customize, edit the `main()` function in `linkedin-scraper.py`.

## Testing

Run the test script to verify the code structure:

```bash
python test-linkedin-scraper.py
```

This will test:
- ✅ All imports
- ✅ Configuration values
- ✅ Scraper initialization
- ✅ URL building logic

## Output Format

The scraper returns `JobData` objects with the following fields:

```python
@dataclass
class JobData:
    title: str          # Job title
    company: str        # Company name
    location: str       # Job location
    job_link: str       # Direct link to job posting
    posted_date: str    # When the job was posted
```

## Example Output

```json
[
  {
    "title": "Data Analyst",
    "company": "Tech Corp",
    "location": "San Francisco, CA",
    "job_link": "https://www.linkedin.com/jobs/view/1234567890",
    "posted_date": "2 days ago"
  }
]
```

## Rate Limiting

The scraper includes built-in rate limiting:
- Random delays between 2-5 seconds between requests
- Retry logic for failed requests (429, 500, 502, 503, 504)
- Configurable delays in `ScraperConfig`

## Important Notes

⚠️ **Rate Limiting**: LinkedIn may rate-limit requests. If you encounter errors:
- Reduce `MAX_JOBS`
- Increase delays in `ScraperConfig`
- Wait before retrying

⚠️ **LinkedIn API Changes**: LinkedIn may change their HTML structure or API endpoints. If scraping fails:
- Check if LinkedIn's HTML structure has changed
- Verify the selectors in `_extract_job_data()` method
- Check if the BASE_URL is still valid

⚠️ **Legal Considerations**: 
- Respect LinkedIn's Terms of Service
- Use reasonable request rates
- Don't overload their servers
- Consider using LinkedIn's official API for production use

## Troubleshooting

### No jobs found
- Try different keywords or location
- Check your internet connection
- Verify LinkedIn's website is accessible
- LinkedIn may have changed their HTML structure

### Import errors
- Ensure all dependencies are installed: `pip install -r requirements-linkedin-scraper.txt`
- Check Python version (requires Python 3.7+)

### Rate limit errors
- Reduce the number of jobs requested
- Increase delays between requests
- Wait before retrying

## License

This code is provided as-is for educational purposes. Please respect LinkedIn's Terms of Service when using this scraper.
