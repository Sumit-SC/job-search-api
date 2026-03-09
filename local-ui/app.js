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
const apiHealthBadge = document.getElementById('api-health-badge');
const apiHealthText = document.getElementById('api-health-text');

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

// Copy text to clipboard; works in iframes when navigator.clipboard is blocked (fallback: temp textarea + execCommand)
function copyTextToClipboard(text) {
    if (!text || !String(text).trim()) return Promise.resolve(false);
    const str = String(text);
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        return navigator.clipboard.writeText(str).then(() => true).catch(() => {
            return copyTextFallback(str);
        });
    }
    return Promise.resolve(copyTextFallback(str));
}
function copyTextFallback(text) {
    try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        ta.style.top = '0';
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, text.length);
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return !!ok;
    } catch (e) {
        return false;
    }
}

// Initialize datetime display on page load + delegated "Copy for ChatGPT" on job cards
window.addEventListener('DOMContentLoaded', () => {
    updateDateTimeDisplay();
    checkApiHealth();
    setupRoadmapEmbed();
    wireInstantFilters();
    setupClearFilters();

    const csvBtn = document.getElementById('export-csv-btn');
    const jsonBtn = document.getElementById('export-json-btn');
    if (csvBtn) csvBtn.addEventListener('click', exportCSV);
    if (jsonBtn) jsonBtn.addEventListener('click', exportJSON);

    if (jobsContainer) {
        jobsContainer.addEventListener('click', (e) => {
            const chatBtn = e.target.closest('.job-copy-chatgpt-btn');
            if (chatBtn && lastDisplayedJobs.length) {
                const idx = parseInt(chatBtn.getAttribute('data-job-index'), 10);
                if (!isNaN(idx) && idx >= 0 && idx < lastDisplayedJobs.length) {
                    const job = lastDisplayedJobs[idx];
                    const prompt = buildChatGPTPrepPrompt(job);
                    copyTextToClipboard(prompt).then((copied) => {
                        window.open('https://chat.openai.com/', '_blank', 'noopener');
                        if (copied) {
                            alert('Prompt copied. Paste it in the new ChatGPT tab. The AI will ask about your background first, then run a mock interview based on this JD.');
                        } else {
                            window.prompt('Copy this prompt and paste into ChatGPT or Gemini:', prompt);
                        }
                    });
                }
                return;
            }

            const prepBtn = e.target.closest('.job-send-prep-btn');
            if (prepBtn && lastDisplayedJobs.length) {
                const idx = parseInt(prepBtn.getAttribute('data-job-index'), 10);
                if (!isNaN(idx) && idx >= 0 && idx < lastDisplayedJobs.length) {
                    const job = lastDisplayedJobs[idx];
                    let desc = String(job.description || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
                    if (desc.length > 1500) desc = desc.slice(0, 1500) + '...';
                    const panel = document.getElementById('prep-flyout-panel');
                    const iframe = document.getElementById('prep-flyout-iframe');
                    if (panel) {
                        panel.classList.add('prep-flyout-open');
                        document.body.style.overflow = 'hidden';
                        const prepUrl = 'interview-prep.html?role=' + encodeURIComponent(job.title || '') + '&company=' + encodeURIComponent(job.company || '') + '&jd=' + encodeURIComponent(desc);
                        if (iframe) iframe.src = prepUrl;
                    } else {
                        window.open('interview-prep.html?role=' + encodeURIComponent(job.title || '') + '&company=' + encodeURIComponent(job.company || '') + '&jd=' + encodeURIComponent(desc), '_blank');
                    }
                }
                return;
            }
        });
    }
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
            updateSourceOptions(allJobs);
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
    const sourcesRaw = (document.getElementById('refresh-sources')?.value || '').trim();

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

        if (sourcesRaw) {
            params.append('sources', sourcesRaw);
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
            updateSourceOptions(allJobs);
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

// Step 3: Search / filter (mostly instant via wireInstantFilters, but keep manual trigger)
if (searchBtn) searchBtn.addEventListener('click', () => searchJobs());

function searchJobs() {
    if (!allJobs.length) {
        searchStatus.className = 'status-message info show';
        searchStatus.textContent = 'ℹ️ No data loaded yet. Use “Fetch saved data” or “Refresh from sources” first.';
        jobsContainer.innerHTML = '<div class="empty-state"><p>No data loaded. Fetch or refresh jobs above, then search.</p></div>';
        return;
    }

    searchStatus.className = 'status-message info show';
    searchStatus.textContent = '⏳ Filtering jobs...';

    const shownCount = applyFiltersAndRender();

    searchStatus.className = 'status-message success show';
    searchStatus.textContent = `✅ Showing ${shownCount} jobs (from ${allJobs.length} loaded)`;
}

function showStep3Card() {
    const step3 = document.getElementById('step3-card');
    if (step3 && allJobs.length > 0) step3.classList.remove('hidden');
}

function debounce(fn, ms) {
    let t;
    return function(...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
}

function wireInstantFilters() {
    const debouncedFilter = debounce(() => { if (allJobs.length) applyFiltersAndRender(); }, 300);
    ['search-query', 'filter-location-custom', 'search-days', 'search-limit', 'search-yoe-min', 'search-yoe-max'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', debouncedFilter);
    });
    ['filter-role', 'filter-location', 'filter-remote', 'filter-level', 'filter-sources', 'search-sort', 'search-currency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => { if (allJobs.length) applyFiltersAndRender(); });
    });
}

function setupClearFilters() {
    const btn = document.getElementById('clear-filters-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        ['filter-role', 'filter-location', 'filter-remote', 'filter-level', 'search-sort', 'search-currency'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['search-query', 'filter-location-custom', 'search-yoe-min', 'search-yoe-max'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const daysEl = document.getElementById('search-days');
        if (daysEl) daysEl.value = '7';
        const limitEl = document.getElementById('search-limit');
        if (limitEl) limitEl.value = '100';
        const srcSel = document.getElementById('filter-sources');
        if (srcSel) Array.from(srcSel.options).forEach(o => o.selected = false);
        if (allJobs.length) applyFiltersAndRender();
    });
}

function normalizeSourceLabel(src) {
    return String(src || '')
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function updateSourceOptions(jobs) {
    const select = document.getElementById('filter-sources');
    if (!select || !Array.isArray(jobs)) return;
    const prev = new Set(Array.from(select.selectedOptions).map(o => o.value));
    const discovered = Array.from(new Set(jobs.map(j => (j && j.source) ? String(j.source).trim() : '').filter(Boolean))).sort();
    select.innerHTML = discovered.map((src) => `<option value="${escapeHtml(src)}">${escapeHtml(normalizeSourceLabel(src))}</option>`).join('');
    Array.from(select.options).forEach((opt) => {
        if (prev.has(opt.value)) opt.selected = true;
    });
}

// Apply current filters on in-memory jobs and render
function applyFiltersAndRender() {
    const query = (document.getElementById('search-query')?.value.trim().toLowerCase()) || null;
    const roleFilter = document.getElementById('filter-role')?.value || '';
    const locationDropdown = document.getElementById('filter-location')?.value || '';
    const locationCustom = (document.getElementById('filter-location-custom')?.value.trim().toLowerCase()) || '';
    const remoteType = document.getElementById('filter-remote')?.value || '';
    const levelFilter = document.getElementById('filter-level')?.value || '';
    const days = parseInt(document.getElementById('search-days')?.value) || 7;
    const limit = parseInt(document.getElementById('search-limit')?.value) || 100;
    const sourcesSelect = document.getElementById('filter-sources');
    const selectedSources = sourcesSelect ? Array.from(sourcesSelect.selectedOptions).map(o => o.value) : [];
    const sort = document.getElementById('search-sort')?.value || 'date';
    const yoeMinVal = document.getElementById('search-yoe-min')?.value;
    const yoeMaxVal = document.getElementById('search-yoe-max')?.value;
    const currencyFilter = document.getElementById('search-currency')?.value || '';
    const yoeMin = (!yoeMinVal || yoeMinVal === '') ? null : parseInt(yoeMinVal);
    const yoeMax = (!yoeMaxVal || yoeMaxVal === '') ? null : parseInt(yoeMaxVal);
    const effectiveLocation = locationCustom || locationDropdown || null;

    if (!allJobs.length) {
        jobsContainer.innerHTML = '<div class="empty-state"><p>No data loaded. Fetch or refresh jobs above, then search.</p></div>';
        updateResultsHeader(0);
        return 0;
    }

    const now = new Date();
    const LEVEL_YOE = { intern: [0, 0], entry: [0, 2], mid: [2, 5], senior: [5, 10], lead: [10, 99] };
    const levelRange = levelFilter ? LEVEL_YOE[levelFilter] : null;

    let filtered = allJobs.filter((job) => {
        if (days && job.date) {
            const diffDays = (now - new Date(job.date)) / (1000 * 60 * 60 * 24);
            if (diffDays > days) return false;
        }

        if (selectedSources.length > 0 && !selectedSources.includes(job.source)) {
            return false;
        }

        if (effectiveLocation) {
            const loc = (job.location || '').toLowerCase();
            if (!loc.includes(effectiveLocation)) return false;
        }

        if (remoteType) {
            const loc = (job.location || '').toLowerCase();
            const title = (job.title || '').toLowerCase();
            const desc = (job.description || '').toLowerCase();
            const blob = loc + ' ' + title + ' ' + desc;
            if (remoteType === 'remote') {
                if (!/(remote|anywhere|work from home|wfh|distributed)/.test(blob)) return false;
            } else if (remoteType === 'hybrid') {
                if (!/(hybrid)/.test(blob)) return false;
            } else if (remoteType === 'onsite') {
                if (/(remote|anywhere|work from home|wfh|distributed|hybrid)/.test(blob)) return false;
            }
        }

        if (roleFilter) {
            const text = ((job.title || '') + ' ' + (job.description || '')).toLowerCase();
            if (!text.includes(roleFilter)) return false;
        }

        if (query) {
            const text = [job.title, job.company, job.location, job.description].filter(Boolean).join(' ').toLowerCase();
            if (!text.includes(query)) return false;
        }

        const jMin = job.yoe_min;
        const jMax = job.yoe_max;
        const effYoeMin = yoeMin !== null ? yoeMin : (levelRange ? levelRange[0] : null);
        const effYoeMax = yoeMax !== null ? yoeMax : (levelRange ? levelRange[1] : null);
        if (effYoeMin !== null) {
            if (jMax !== null && jMax < effYoeMin) return false;
        }
        if (effYoeMax !== null) {
            if (jMin !== null && jMin > effYoeMax) return false;
        }

        if (currencyFilter) {
            if (!job.currency || job.currency.toUpperCase() !== currencyFilter.toUpperCase()) return false;
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

    renderSourceStats(filtered);
    const limited = filtered.slice(0, limit);
    displayJobs(limited);
    updateResultsHeader(filtered.length);

    return limited.length;
}

var lastDisplayedJobs = [];

function displayJobs(jobs) {
    if (jobs.length === 0) {
        jobsContainer.innerHTML = '<div class="empty-state"><p>No jobs found matching your criteria. Try adjusting your filters or refresh the database.</p></div>';
        lastDisplayedJobs = [];
        return;
    }
    lastDisplayedJobs = jobs;
    jobsContainer.innerHTML = jobs.map((job, index) => createJobCard(job, index)).join('');
}

function buildChatGPTPrepPrompt(job) {
    const role = job.title || 'this role';
    const company = job.company || '';
    const location = job.location || '';
    let desc = String(job.description || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (desc.length > 8000) desc = desc.slice(0, 8000) + '...';
    return 'I am preparing for an interview. Please help me as follows.\n\n' +
        '**Role:** ' + role + (company ? '\n**Company:** ' + company : '') + (location ? '\n**Location:** ' + location : '') + '\n\n' +
        '**Job description:**\n' + (desc || '(No description provided.)') + '\n\n' +
        '**Instructions for you (the AI):**\n' +
        '1. First, ask me about my background and relevant experience (e.g. years of experience, key skills, recent roles). Wait for my answer.\n' +
        '2. Then, using the job description above, act as an interviewer. Ask me one interview question at a time (behavioral, technical, or role-specific). Base each question on this role and JD.\n' +
        '3. After each answer, give brief constructive feedback, then ask the next question.\n' +
        '4. After 5–7 questions, give a short overall prep tip. Keep responses concise.\n\n' +
        'Start by asking about my background.';
}

function createJobCard(job, index) {
    const date = job.date ? new Date(job.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    }) : 'Unknown date';

    const matchScore = job.match_score ? Math.round(job.match_score) : null;
    const yoe = formatYOE(job.yoe_min, job.yoe_max);
    const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
    const dataIndex = typeof index === 'number' ? index : '';

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
                <a href="interview-prep.html?role=${encodeURIComponent(job.title || '')}&company=${encodeURIComponent(job.company || '')}" class="job-meta-item job-prep-link" title="Interview prep for this role">🎯 Prep</a>
                <button type="button" class="job-meta-item job-send-prep-btn" data-job-index="${dataIndex}" title="Send JD to Interview Prep flyout for mock questions">🎤 Interview Prep</button>
                <button type="button" class="job-meta-item job-copy-chatgpt-btn" data-job-index="${dataIndex}" title="Copy JD + prompt and open ChatGPT/Gemini">📋 Copy for ChatGPT</button>
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

function renderSourceStats(jobs) {
    const el = document.getElementById('source-stats');
    if (!el) return;
    if (!jobs.length) { el.innerHTML = ''; return; }
    const counts = {};
    jobs.forEach(j => { const s = j.source || '?'; counts[s] = (counts[s] || 0) + 1; });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    el.innerHTML = sorted.map(([src, count]) =>
        `<span class="source-badge" data-source="${escapeHtml(src)}" title="Click to filter by ${escapeHtml(src)}">${escapeHtml(normalizeSourceLabel(src))} <strong>${count}</strong></span>`
    ).join('');
    el.querySelectorAll('.source-badge').forEach(badge => {
        badge.addEventListener('click', () => {
            const src = badge.dataset.source;
            const sel = document.getElementById('filter-sources');
            if (!sel) return;
            Array.from(sel.options).forEach(opt => { opt.selected = opt.value === src; });
            applyFiltersAndRender();
        });
    });
}

function exportCSV() {
    if (!lastDisplayedJobs.length) return;
    const headers = ['title','company','location','source','date','url','salary_min','salary_max','currency','yoe_min','yoe_max'];
    const rows = lastDisplayedJobs.map(j => headers.map(h => {
        let v = j[h]; if (v == null) v = ''; if (v instanceof Date) v = v.toISOString();
        return '"' + String(v).replace(/"/g, '""') + '"';
    }).join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    downloadFile(csv, 'jobs-export.csv', 'text/csv');
}

function exportJSON() {
    if (!lastDisplayedJobs.length) return;
    const json = JSON.stringify(lastDisplayedJobs, null, 2);
    downloadFile(json, 'jobs-export.json', 'application/json');
}

function downloadFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function checkApiHealth() {
    if (!apiHealthBadge || !apiHealthText) return;
    try {
        apiHealthBadge.classList.remove('is-ok', 'is-error');
        apiHealthText.textContent = 'Checking API health...';
        const response = await fetch(`${API_BASE_URL}/health`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const statusText = (data && data.status) ? String(data.status) : 'ok';
        apiHealthBadge.classList.add('is-ok');
        apiHealthText.textContent = `API: ${statusText.toUpperCase()} (${API_BASE_URL})`;
    } catch (error) {
        apiHealthBadge.classList.add('is-error');
        apiHealthText.textContent = `API unreachable (${API_BASE_URL})`;
        console.warn('Health check failed:', error);
    }
}

function setupRoadmapEmbed() {
    const toggle = document.getElementById('roadmap-embed-toggle');
    const wrap = document.getElementById('roadmap-embed-wrap');
    const iframe = document.getElementById('roadmap-embed-iframe');
    if (!toggle || !wrap || !iframe) return;

    const defaultRoadmap = 'https://roadmap.sh/data-analyst';
    toggle.addEventListener('click', () => {
        const isOpen = !wrap.classList.contains('hidden');
        if (isOpen) {
            wrap.classList.add('hidden');
            toggle.setAttribute('aria-expanded', 'false');
            toggle.textContent = 'Show embed';
            return;
        }
        wrap.classList.remove('hidden');
        toggle.setAttribute('aria-expanded', 'true');
        toggle.textContent = 'Hide embed';
        if (iframe.src === 'about:blank') iframe.src = defaultRoadmap;
    });
}

// Initialize: Try to load jobs on page load
window.addEventListener('DOMContentLoaded', () => {
    // Optionally auto-load jobs on page load
    // searchJobs();
});
