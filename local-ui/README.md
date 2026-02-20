# Job Search API - Local UI

A standalone web interface for testing and interacting with the Job Search API locally.

## Features

- **Refresh Database**: Scrape fresh jobs from all sources (RSS + optional headless scrapers)
- **Search & Filter**: Search through scraped jobs with multiple filters:
  - Free text query
  - Days (job age)
  - Source filter
  - Years of Experience (YOE) range
  - Sort by date, relevance, or source
  - Result limit
- **Beautiful UI**: Modern, responsive design with job cards
- **Real-time Status**: Loading states and status messages

## Usage

### 1. Start the API Server

Make sure the API server is running on `http://localhost:8000`:

```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
.venv\Scripts\Activate.ps1
$env:JOBS_SCRAPER_DATA_DIR = "data"
$env:ENABLE_HEADLESS = "1"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open the UI

Simply open `index.html` in your web browser:

- **Windows**: Double-click `index.html` or right-click → "Open with" → Your browser
- **Or**: Open your browser and navigate to the file path

### 3. Use the Interface

1. **Refresh Database** (left panel):
   - Enter a search query (e.g., "data analyst")
   - Set the number of days to look back (default: 3)
   - Toggle headless scrapers (slower but more comprehensive)
   - Click "🔄 Refresh Database"
   - Wait 30-90 seconds for scraping to complete

2. **Search Jobs** (right panel):
   - Enter search query (optional)
   - Adjust filters as needed
   - Click "🔎 Search Jobs"
   - Results will display in cards below

## Configuration

To change the API URL (if running on a different port or host), edit `app.js`:

```javascript
const API_BASE_URL = 'http://localhost:8000'; // Change this
```

## File Structure

```
local-ui/
├── index.html    # Main HTML structure
├── styles.css    # Styling
├── app.js        # JavaScript logic
└── README.md     # This file
```

## Notes

- The UI is completely standalone - no build process required
- All API calls are made directly from the browser
- CORS is enabled on the API, so cross-origin requests work
- Jobs are displayed in a responsive grid layout
- Each job card shows: title, company, location, description preview, source, date, match score, YOE, salary, and other metadata

## Troubleshooting

**"Failed to fetch" error:**
- Make sure the API server is running on `http://localhost:8000`
- Check browser console for detailed error messages

**No jobs found:**
- Refresh the database first using the "Refresh Database" button
- Try increasing the "Days" filter
- Check if the API server has scraped any jobs

**UI looks broken:**
- Make sure `styles.css` is in the same folder as `index.html`
- Check browser console for any errors
