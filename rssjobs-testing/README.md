 # rssjobs / Jobber RSS testing
 
 Local notebook to test [Jobber](https://github.com/alwedo/jobber) job-search feeds and [rssjobs.app](https://rssjobs.app/) RSS URLs.
 
 ## Setup
 
 From this folder:
 
 ```bash
 # Uv (preferred)
 uv sync
 
 # or pip
 python -m venv .venv
 .venv\Scripts\activate
 pip install -r requirements.txt
 ```
 
 ## Run the notebook
 
 ```bash
 uv run jupyter notebook rssjobs_test.ipynb
 # or, with pip venv active:
 jupyter notebook rssjobs_test.ipynb
 ```
 
 Then paste any rssjobs/jobber RSS feed URL into the notebook UI.
 
 ## Creating a feed
 
 - Hosted: use [rssjobs.app](https://rssjobs.app/) to create a feed, then click **open RSS feed** and copy the URL.  
 - Local Jobber: run Jobber locally as per its README, open `http://localhost`, create a search, then copy the RSS feed URL from the UI.
 
 The notebook only reads the RSS URL — it doesn’t run scraping itself.
 
