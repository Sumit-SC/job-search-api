 # JobSentinel-style board testing (notebook)
 
 This folder contains a notebook that pulls job listings from multiple sources using **public endpoints** where possible (e.g. Greenhouse/Lever APIs, RSS feeds) and uses **python-jobspy** for boards it supports (Indeed/LinkedIn/ZipRecruiter/Google/Glassdoor).
 
 Reference project: [cboyd0319/JobSentinel](https://github.com/cboyd0319/JobSentinel).
 
 ## Setup
 
 ```bash
 # Uv (preferred)
 uv sync
 
 # or pip
 python -m venv .venv
 .venv\Scripts\activate
 pip install -r requirements.txt
 ```
 
 ## Run
 
 ```bash
 uv run jupyter notebook boards_test.ipynb
 # or with pip venv active:
 jupyter notebook boards_test.ipynb
 ```
 
 ## Notes
 
 - Some job boards are hostile to scraping and/or have strict ToS. The notebook is designed to prefer stable, public feeds/APIs.
 - For LinkedIn-heavy queries, expect rate limits; JobSpy supports proxies (see their README).
 
