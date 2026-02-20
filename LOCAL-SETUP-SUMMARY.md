# Local Setup Summary - No Docker Needed!

**Quick answer:** You **DON'T need Docker** - just Python!

---

## ✅ What You Need

- ✅ **Python 3.9+** (that's it!)
- ❌ **Docker** (optional, not required)
- ❌ **Complex setup** (it's simple!)

---

## 🚀 Quick Start (3 Steps)

### Step 1: Run Setup Script
```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
.\setup_local.ps1
```

This will:
- Create virtual environment
- Install all dependencies
- Install Playwright Chromium browser
- Create data directory

### Step 2: Start Server
```powershell
# Activate venv (if not already active)
.venv\Scripts\Activate.ps1

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Test It
```powershell
# In another terminal
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

**That's it!** API is running locally.

---

## 🧪 Test Headless Scrapers

### Test All Headless Scrapers (8 total)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300
```

**Expected:** JSON with 8 scrapers:
- linkedin
- indeed_headless
- naukri
- hirist
- foundit
- shine
- monster
- glassdoor

**Time:** 2-5 minutes (each scraper has 90s timeout)

### Test Individual Scrapers
Check server logs when running `/debug/headless` to see which ones work.

---

## 📊 What Runs Locally

### RSS Scrapers (14 sources)
- ✅ **Works immediately** - No browser needed
- ✅ **Fast** - ~30 seconds total
- ✅ **Reliable** - HTTP requests only

### Headless Scrapers (8 sources)
- ✅ **Requires Playwright** - Already installed by setup script
- ⚠️ **Slow** - 2-5 minutes total
- ⚠️ **May return 0 jobs** - Sites may block scrapers

---

## 🐳 Docker (Optional)

**You don't need Docker**, but if you want to use it:

```powershell
# Build image
docker build -t job-search-api .

# Run container
docker run -p 8000:8000 -e ENABLE_HEADLESS=1 job-search-api
```

**Why use Docker?**
- Matches production environment exactly
- Isolated dependencies
- Easy to share with team

**Why NOT use Docker?**
- Slower startup
- More complex
- Not needed for development

---

## 🔍 Troubleshooting

### Playwright Not Found
```powershell
python -m playwright install chromium
```

### Port Already in Use
```powershell
# Use different port
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Import Errors
```powershell
# Make sure venv is activated
.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Headless Returns 0 Jobs
- **Normal** - Sites may block scrapers
- Check server logs for errors
- Try with `days=30` (longer date range)
- Some scrapers may need selector updates

---

## 📝 Files Created

1. **`LOCAL-TESTING-GUIDE.md`** - Complete testing guide
2. **`QUICK-START.md`** - Fast setup instructions
3. **`setup_local.ps1`** - Automated setup script
4. **`test_local.ps1`** - Automated testing script

---

## 🎯 Next Steps

1. ✅ **Run setup:** `.\setup_local.ps1`
2. ✅ **Start server:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
3. ✅ **Test API:** `.\test_local.ps1`
4. ✅ **Test headless:** `Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300`
5. ✅ **Test with frontend:** Point `jobs.html` to `http://localhost:8000`

---

## 💡 Pro Tips

- **Use `--reload` flag** - Auto-restarts on code changes
- **Check server logs** - See what scrapers are doing
- **Test RSS first** - Fast and reliable
- **Test headless later** - Slow but comprehensive
- **Data saves locally** - Check `data/jobs.json` file

---

## 📚 Documentation

- **`LOCAL-TESTING-GUIDE.md`** - Full testing guide
- **`API-PARAMETERS-GUIDE.md`** - API parameters reference
- **`README.md`** - Project overview
