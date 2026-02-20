"""
Quick test script for LinkedIn scraper
Tests basic functionality without making actual requests
"""

import sys
import importlib.util

# Load the module from file
spec = importlib.util.spec_from_file_location("linkedin_scraper", "linkedin-scraper.py")
linkedin_scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linkedin_scraper)

LinkedInJobsScraper = linkedin_scraper.LinkedInJobsScraper
ScraperConfig = linkedin_scraper.ScraperConfig
JobData = linkedin_scraper.JobData

def test_imports():
    """Test that all imports work"""
    print("[OK] Testing imports...")
    try:
        from dataclasses import dataclass
        from typing import List, Optional
        import requests
        from bs4 import BeautifulSoup
        import time
        import random
        import json
        from urllib.parse import quote
        from requests.adapters import HTTPAdapter
        from urllib3.util import Retry
        print("   All imports successful")
        return True
    except ImportError as e:
        print(f"   [ERROR] Import error: {e}")
        return False

def test_scraper_init():
    """Test scraper initialization"""
    print("\n[OK] Testing scraper initialization...")
    try:
        scraper = LinkedInJobsScraper()
        assert scraper.session is not None
        print("   Scraper initialized successfully")
        return True
    except Exception as e:
        print(f"   [ERROR] Initialization error: {e}")
        return False

def test_url_building():
    """Test URL building logic"""
    print("\n[OK] Testing URL building...")
    try:
        scraper = LinkedInJobsScraper()
        url = scraper._build_search_url("Data Analyst", "San Francisco", 0)
        assert "linkedin.com" in url
        assert "Data+Analyst" in url or "Data%20Analyst" in url
        assert "San+Francisco" in url or "San%20Francisco" in url
        print(f"   URL built: {url[:80]}...")
        return True
    except Exception as e:
        print(f"   [ERROR] URL building error: {e}")
        return False

def test_config():
    """Test configuration values"""
    print("\n[OK] Testing configuration...")
    try:
        assert ScraperConfig.BASE_URL is not None
        assert ScraperConfig.JOBS_PER_PAGE > 0
        assert ScraperConfig.MIN_DELAY >= 0
        assert ScraperConfig.MAX_DELAY > ScraperConfig.MIN_DELAY
        assert len(ScraperConfig.HEADERS) > 0
        print("   Configuration valid")
        return True
    except Exception as e:
        print(f"   [ERROR] Configuration error: {e}")
        return False

def main():
    print("=" * 60)
    print("LinkedIn Scraper - Basic Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_scraper_init,
        test_url_building,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   [ERROR] Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n[SUCCESS] All basic tests passed!")
        print("   The scraper structure is correct.")
        print("   Note: Actual scraping requires network access and may be rate-limited by LinkedIn.")
        return 0
    else:
        print("\n[FAILED] Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
