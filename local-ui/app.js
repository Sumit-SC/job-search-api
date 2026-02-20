// Configuration: use same origin when served from Railway (or any host), else localhost
const API_BASE_URL = (typeof window !== 'undefined' && window.location && window.location.origin)
    ? window.location.origin
    : 'http://localhost:8000';

// In-memory cache of jobs loaded from /jobs or /refresh
let allJobs = [];

// Datetime tracking keys for localStorage
const LAST_FETCHED_KEY = 'job_search_last_fetched';
const CURRENT_FETCHED_KEY = 'job_search_current_fetched';

// DOM Elements
const fetchBtn = document.getElementById('fetch-btn');
const refreshBtn = document.getElementById('refresh-btn');
const searchBtn = document.getElementById('search-btn');
const fetchStatus = document.getElementById('fetch-status');
const refreshStatus = document.getElementById('refresh-status');
const searchStatus = document.getElementById('search-status');
const jobsContainer = document.getElementById('jobs-container');
const resultsTitle = document.getElementById('results-title');
const resultsCount = document.getElementById('results-count');

// Helper: format datetime for display
function formatDateTime(date) {
    if (!date) return 'Never';
    const d = new Date(date);
    return d.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

// Helper: update datetime display
function updateDateTimeDisplay() {
    const lastFetchedEl = document.getElementById('last-fetched-info');
    const currentFetchedEl = document.getElementById('current-fetched-info');
    
    if (lastFetchedEl) {
        const lastFetched = localStorage.getItem(LAST_FETCHED_KEY);
        lastFetchedEl.textContent = `Last fetched: ${formatDateTime(lastFetched)}`;
    }
    
    if (currentFetchedEl) {
        const currentFetched = localStorage.getItem(CURRENT_FETCHED_KEY);
        currentFetchedEl.textContent = `Current fetched: ${formatDateTime(currentFetched)}`;
    }
}

// Initialize datetime display on page load
window.addEventListener('DOMContentLoaded', () => {
    updateDateTimeDisplay();
});

// -----------------------------
// Step 2: Fetch saved data
// -----------------------------
fetchBtn.addEventListener('click', async () => {
    const days = parseInt(document.getElementById('fetch-days').value) || 7;
    const limit = parseInt(document.getElementById('fetch-limit').value) || 200;

    fetchBtn.disabled = true;
    fetchBtn.querySelector('.btn-text').style.display = 'none';
    fetchBtn.querySelector('.btn-loader').style.display = 'inline';

    fetchStatus.className = 'status-message info show';
    fetchStatus.textContent = `⏳ Fetching saved jobs (last ${days} days, limit ${limit})...`;

    try {
        const params = new URLSearchParams({
            days: days.toString(),
            limit: limit.toString(),
            sort: 'date',
        });

        const response = await fetch(`${API_BASE_URL}/jobs?${params}`);
        const data = await response.json();

        if (data.ok) {
            allJobs = data.jobs || [];
            const now = new Date().toISOString();
            
            // Update last fetched timestamp
            localStorage.setItem(LAST_FETCHED_KEY, now);
            localStorage.setItem(CURRENT_FETCHED_KEY, now);
            updateDateTimeDisplay();
            
            fetchStatus.className = 'status-message success show';
            fetchStatus.textContent = `✅ Loaded ${allJobs.length} saved jobs. Use “Search & Filter Jobs” below to narrow them down.`;

            showStep3Card();
            applyFiltersAndRender();
        } else {
            throw new Error(data.error || 'Fetch failed');
        }
    } catch (error) {
        fetchStatus.className = 'status-message error show';
        fetchStatus.textContent = `❌ Error: ${error.message}`;
        console.error('Fetch error:', error);
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.querySelector('.btn-text').style.display = 'inline';
        fetchBtn.querySelector('.btn-loader').style.display = 'none';
    }
});

// Helper: get current source mode (rss, headless, all)
function getSourceMode() {
    const radios = document.querySelectorAll('input[name="source-mode"]');
    for (const r of radios) {
        if (r.checked) return r.value;
    }
    return 'all';
}

// -----------------------------
// Step 1: Refresh data (scrapers)
// -----------------------------
refreshBtn.addEventListener('click', async () => {
    const query = document.getElementById('refresh-query').value.trim() || 'data analyst';
    const days = parseInt(document.getElementById('refresh-days').value) || 3;
    const mode = getSourceMode();

    refreshBtn.disabled = true;
    refreshBtn.querySelector('.btn-text').style.display = 'none';
    refreshBtn.querySelector('.btn-loader').style.display = 'inline';

    refreshStatus.className = 'status-message info show';
    refreshStatus.textContent = `⏳ Refreshing database with query "${query}" (${days} days)... This may take 30-90 seconds.`;

    try {
        const params = new URLSearchParams({
            q: query,
            days: days.toString(),
        });

        if (mode === 'rss') {
            params.append('headless', '0');
            params.append('mode', 'rss');
        } else if (mode === 'headless') {
            params.append('headless', '1');
            params.append('mode', 'headless');
        } else {
            params.append('headless', '1');
            params.append('mode', 'all');
        }

        const response = await fetch(`${API_BASE_URL}/refresh?${params}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.ok) {
            // Replace in-memory jobs with freshly scraped ones
            allJobs = data.jobs || [];
            const now = new Date().toISOString();
            
            // Update timestamps after refresh (refresh saves to storage, so this is when data was refreshed)
            localStorage.setItem(LAST_FETCHED_KEY, now);
            localStorage.setItem(CURRENT_FETCHED_KEY, now);
            updateDateTimeDisplay();
            
            refreshStatus.className = 'status-message success show';
            refreshStatus.textContent = `✅ Successfully refreshed! Scraped ${allJobs.length} jobs. Use “Search & Filter Jobs” below to narrow them down.`;

            showStep3Card();
            applyFiltersAndRender();
        } else {
            throw new Error(data.error || 'Refresh failed');
        }
    } catch (error) {
        refreshStatus.className = 'status-message error show';
        refreshStatus.textContent = `❌ Error: ${error.message}`;
        console.error('Refresh error:', error);
    } finally {
        refreshBtn.disabled = false;
        refreshBtn.querySelector('.btn-text').style.display = 'inline';
        refreshBtn.querySelector('.btn-loader').style.display = 'none';
    }
});

// -----------------------------
// Step 3: Search / filter jobs (client-side only)
// -----------------------------
searchBtn.addEventListener('click', () => {
    searchJobs();
});

// Allow Enter key to trigger search
document.getElementById('search-query').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        searchJobs();
    }
});

function searchJobs() {
    if (!allJobs.length) {
        searchStatus.className = 'status-message info show';
        searchStatus.textContent = 'ℹ️ No data loaded yet. Use “Fetch saved data” or “Refresh from sources” first.';
        jobsContainer.innerHTML = '<div class="empty-state"><p>No data loaded. Fetch or refresh jobs above, then search.</p></div>';
        return;
    }

    searchBtn.disabled = true;
    searchBtn.querySelector('.btn-text').style.display = 'none';
    searchBtn.querySelector('.btn-loader').style.display = 'inline';

    searchStatus.className = 'status-message info show';
    searchStatus.textContent = '⏳ Filtering jobs...';

    const shownCount = applyFiltersAndRender();

    searchStatus.className = 'status-message success show';
    searchStatus.textContent = `✅ Showing ${shownCount} jobs (from ${allJobs.length} loaded)`;

    searchBtn.disabled = false;
    searchBtn.querySelector('.btn-text').style.display = 'inline';
    searchBtn.querySelector('.btn-loader').style.display = 'none';
}

function showStep3Card() {
    const step3 = document.getElementById('step3-card');
    if (step3 && allJobs.length > 0) step3.classList.remove('hidden');
}

// Apply current filters on in-memory jobs and render
function applyFiltersAndRender() {
    const queryEl = document.getElementById('search-query');
    const locationEl = document.getElementById('search-location-text');
    const query = (queryEl && queryEl.value.trim().toLowerCase()) || null;
    const locationText = (locationEl && locationEl.value.trim().toLowerCase()) || null;
    const days = parseInt(document.getElementById('search-days')?.value) || 3;
    const limit = parseInt(document.getElementById('search-limit')?.value) || 50;
    const sourcesSelect = document.getElementById('search-sources-select');
    const selectedSources = sourcesSelect ? Array.from(sourcesSelect.selectedOptions).map(o => o.value) : [];
    const sort = document.getElementById('search-sort').value || 'date';
    const yoeMinVal = document.getElementById('search-yoe-min').value;
    const yoeMaxVal = document.getElementById('search-yoe-max').value;
    const remoteOnly = document.getElementById('search-remote-only').checked;
    const currencyFilter = document.getElementById('search-currency').value;
    const yoeMin = yoeMinVal === '' ? null : parseInt(yoeMinVal);
    const yoeMax = yoeMaxVal === '' ? null : parseInt(yoeMaxVal);

    if (!allJobs.length) {
        jobsContainer.innerHTML = '<div class="empty-state"><p>No data loaded. Fetch or refresh jobs above, then search.</p></div>';
        updateResultsHeader(0);
        return 0;
    }

    const now = new Date();

    let filtered = allJobs.filter((job) => {
        // Days filter
        if (days && job.date) {
            const jobDate = new Date(job.date);
            const diffMs = now - jobDate;
            const diffDays = diffMs / (1000 * 60 * 60 * 24);
            if (diffDays > days) return false;
        }

        // Source filter (multi-select)
        if (selectedSources.length > 0 && !selectedSources.includes(job.source)) {
            return false;
        }

        // Location text filter
        if (locationText) {
            const loc = (job.location || '').toLowerCase();
            if (!loc.includes(locationText)) return false;
        }

        // Remote-only filter
        if (remoteOnly) {
            const loc = (job.location || '').toLowerCase();
            const desc = (job.description || '').toLowerCase();
            const remoteHints = ['remote', 'anywhere', 'work from home', 'wfh', 'hybrid'];
            const isRemote = remoteHints.some((hint) => loc.includes(hint) || desc.includes(hint));
            if (!isRemote) return false;
        }

        // Text query filter
        if (query) {
            const text = [
                job.title,
                job.company,
                job.location,
                job.description,
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();

            if (!text.includes(query)) return false;
        }

        // YOE filter
        const jMin = job.yoe_min;
        const jMax = job.yoe_max;
        if (yoeMin !== null) {
            if (jMax !== null && jMax < yoeMin) return false;
            if (jMin !== null && jMin > yoeMin) return false;
        }
        if (yoeMax !== null) {
            if (jMin !== null && jMin > yoeMax) return false;
            if (jMax !== null && jMax > yoeMax) return false;
        }

        // Currency filter
        if (currencyFilter) {
            if (!job.currency || job.currency.toUpperCase() !== currencyFilter.toUpperCase()) {
                return false;
            }
        }

        return true;
    });

    // Sort
    if (sort === 'date') {
        filtered.sort((a, b) => {
            const da = a.date ? new Date(a.date).getTime() : 0;
            const db = b.date ? new Date(b.date).getTime() : 0;
            return db - da; // newest first
        });
    } else if (sort === 'relevance') {
        filtered.sort((a, b) => {
            const sa = typeof a.match_score === 'number' ? a.match_score : 0;
            const sb = typeof b.match_score === 'number' ? b.match_score : 0;
            return sb - sa;
        });
    } else if (sort === 'source') {
        filtered.sort((a, b) => {
            const sa = (a.source || '').localeCompare(b.source || '');
            if (sa !== 0) return sa;
            const da = a.date ? new Date(a.date).getTime() : 0;
            const db = b.date ? new Date(b.date).getTime() : 0;
            return db - da;
        });
    } else if (sort === 'salary') {
        filtered.sort((a, b) => {
            const sa = getSalaryValue(a);
            const sb = getSalaryValue(b);
            return sb - sa; // highest first
        });
    } else if (sort === 'currency') {
        filtered.sort((a, b) => {
            const ca = (a.currency || '').toUpperCase();
            const cb = (b.currency || '').toUpperCase();
            const cmp = ca.localeCompare(cb);
            if (cmp !== 0) return cmp;
            return getSalaryValue(b) - getSalaryValue(a);
        });
    }

    const limited = filtered.slice(0, limit);
    displayJobs(limited);
    updateResultsHeader(filtered.length);

    return limited.length;
}

function displayJobs(jobs) {
    if (jobs.length === 0) {
        jobsContainer.innerHTML = '<div class="empty-state"><p>No jobs found matching your criteria. Try adjusting your filters or refresh the database.</p></div>';
        return;
    }

    jobsContainer.innerHTML = jobs.map(job => createJobCard(job)).join('');
}

function createJobCard(job) {
    const date = job.date ? new Date(job.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    }) : 'Unknown date';

    const matchScore = job.match_score ? Math.round(job.match_score) : null;
    const yoe = formatYOE(job.yoe_min, job.yoe_max);
    const salary = formatSalary(job.salary_min, job.salary_max, job.currency);

    return `
        <div class="job-card">
            <div class="job-header">
                <div class="job-title">
                    <a href="${job.url}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(job.title)}
                    </a>
                </div>
                <div class="job-company">${escapeHtml(job.company || 'Unknown Company')}</div>
                <div class="job-location">📍 ${escapeHtml(job.location || 'Location not specified')}</div>
            </div>
            
            ${job.description ? `<div class="job-description">${truncateHtml(job.description, 200)}</div>` : ''}
            
            <div class="job-meta">
                <span class="job-meta-item job-source">${escapeHtml(job.source || 'unknown')}</span>
                <span class="job-meta-item job-date">📅 ${date}</span>
                ${matchScore ? `<span class="job-meta-item job-match-score">⭐ ${matchScore}% match</span>` : ''}
                ${yoe ? `<span class="job-meta-item">💼 ${yoe}</span>` : ''}
                ${salary ? `<span class="job-meta-item">💰 ${salary}</span>` : ''}
                ${job.visa_sponsorship ? `<span class="job-meta-item">✈️ Visa Sponsorship</span>` : ''}
                ${job.job_type ? `<span class="job-meta-item">📋 ${escapeHtml(job.job_type)}</span>` : ''}
            </div>
        </div>
    `;
}

function formatYOE(min, max) {
    if (min === null && max === null) return null;
    if (min === max) return `${min} years`;
    if (min === null) return `Up to ${max} years`;
    if (max === null) return `${min}+ years`;
    return `${min}-${max} years`;
}

function formatSalary(min, max, currency) {
    if (min === null && max === null) return null;
    const curr = currency || 'USD';
    const formatNum = (num) => {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(0) + 'K';
        return num.toString();
    };
    if (min === max) return `${curr} ${formatNum(min)}`;
    if (min === null) return `Up to ${curr} ${formatNum(max)}`;
    if (max === null) return `${curr} ${formatNum(min)}+`;
    return `${curr} ${formatNum(min)}-${formatNum(max)}`;
}

// Helper for numeric salary sort: use avg(min,max) or single value, 0 if unknown
function getSalaryValue(job) {
    const min = typeof job.salary_min === 'number' ? job.salary_min : null;
    const max = typeof job.salary_max === 'number' ? job.salary_max : null;
    if (min === null && max === null) return 0;
    if (min !== null && max !== null) return (min + max) / 2;
    return (min !== null ? min : max);
}

function truncateHtml(html, maxLength) {
    const text = html.replace(/<[^>]*>/g, '');
    if (text.length <= maxLength) return escapeHtml(html);
    return escapeHtml(text.substring(0, maxLength)) + '...';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateResultsHeader(count) {
    resultsTitle.textContent = 'Jobs';
    resultsCount.textContent = `${count} ${count === 1 ? 'job' : 'jobs'} found`;
}

// Initialize: Try to load jobs on page load
window.addEventListener('DOMContentLoaded', () => {
    // Optionally auto-load jobs on page load
    // searchJobs();
});
