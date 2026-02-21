// API base: ?api_base=URL override, else same-origin (Railway /ui/ or localhost), else fallback
function getRssjobsApiBase() {
    if (typeof window === 'undefined' || !window.location) return 'http://localhost:8000';
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get('api_base') || params.get('api');
    if (fromQuery && fromQuery.startsWith('http')) return fromQuery.replace(/\/$/, '');
    const origin = window.location.origin;
    if (origin && origin !== 'null' && origin !== 'file://') return origin;
    return 'https://job-search-api-production-5d5d.up.railway.app';
}
const RSSJOBS_API_BASE_URL = getRssjobsApiBase();

var RSSJOBS_CLIENT_CACHE_TTL_MS = 5 * 60 * 1000;
var RSSJOBS_CACHE_KEY_PREFIX = 'rssjobs_';

function rssjobsClientCacheKey(params) {
    return RSSJOBS_CACHE_KEY_PREFIX + params.toString();
}

function getRssjobsClientCached(params) {
    try {
        var raw = sessionStorage.getItem(rssjobsClientCacheKey(params));
        if (!raw) return null;
        var entry = JSON.parse(raw);
        if (entry.expiresAt && Date.now() > entry.expiresAt) {
            sessionStorage.removeItem(rssjobsClientCacheKey(params));
            return null;
        }
        return entry;
    } catch (e) {
        return null;
    }
}

function setRssjobsClientCache(params, data, xCache) {
    try {
        sessionStorage.setItem(rssjobsClientCacheKey(params), JSON.stringify({
            data: data,
            xCache: xCache || null,
            cachedAt: Date.now(),
            expiresAt: Date.now() + RSSJOBS_CLIENT_CACHE_TTL_MS,
        }));
    } catch (e) { /* quota or disabled */ }
}

const rssFetchBtn = document.getElementById('rss-fetch-btn');
const rssStatus = document.getElementById('rss-status');
const rssJobsContainer = document.getElementById('rss-jobs-container');
const rssResultsCount = document.getElementById('rss-results-count');

rssFetchBtn.addEventListener('click', fetchFromRssJobs);

async function fetchFromRssJobs() {
    const role = document.getElementById('rss-role').value.trim() || 'analyst';
    const location = document.getElementById('rss-location').value.trim() || 'remote';
    const maxItems = parseInt(document.getElementById('rss-max').value) || 100;

    const params = new URLSearchParams({
        keywords: role,
        location: location,
        limit: maxItems.toString(),
    });

    var skipCache = document.getElementById('rss-skip-cache');
    if (skipCache && skipCache.checked) params.set('skip_cache', 'true');

    var clientCached = !params.has('skip_cache') ? getRssjobsClientCached(params) : null;
    if (clientCached && clientCached.data && Array.isArray(clientCached.data.jobs) && clientCached.data.jobs.length > 0) {
        var jobs = clientCached.data.jobs;
        var mins = Math.round((Date.now() - clientCached.cachedAt) / 60000);
        rssStatus.className = 'status-message info show';
        rssStatus.textContent = '📦 Cached results (' + mins + ' min ago). Click Fetch again to refresh.';
        if (clientCached.xCache === 'HIT') rssStatus.textContent += ' (server cache hit)';
        rssResultsCount.textContent = jobs.length + ' jobs from rssjobs.app';
        rssJobsContainer.innerHTML = jobs.map(renderRssJobCard).join('');
        return;
    }

    rssFetchBtn.disabled = true;
    rssFetchBtn.querySelector('.btn-text').style.display = 'none';
    rssFetchBtn.querySelector('.btn-loader').style.display = 'inline';

    rssStatus.className = 'status-message info show';
    rssStatus.textContent = '⏳ Fetching from rssjobs.app via backend proxy...';

    rssJobsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading RSS feed...</div>';

    try {
        const response = await fetch(`${RSSJOBS_API_BASE_URL}/rssjobs?${params}`);
        const xCache = response.headers.get('X-Cache') || null;
        var data;
        try {
            data = await response.json();
        } catch (parseErr) {
            throw new Error('Invalid JSON from server. Try again.');
        }

        if (!response.ok) {
            throw new Error(data && data.error ? data.error : 'HTTP ' + response.status);
        }

        if (!data.ok) {
            throw new Error(data.error || 'Backend returned ok=false');
        }

        const jobs = Array.isArray(data.jobs) ? data.jobs : [];
        setRssjobsClientCache(params, data, xCache);

        if (!jobs.length) {
            rssStatus.className = 'status-message info show';
            rssStatus.textContent = 'ℹ️ No jobs found from rssjobs.app. Try different keywords or location.';
            rssJobsContainer.innerHTML = '<div class="empty-state"><p>No jobs found. Try adjusting keywords or location.</p></div>';
            rssResultsCount.textContent = '';
            return;
        }

        rssStatus.className = 'status-message success show';
        rssStatus.textContent = '✅ Fetched ' + jobs.length + ' jobs from rssjobs.app';
        if (xCache === 'HIT') rssStatus.textContent += ' (from server cache)';
        rssJobsContainer.innerHTML = jobs.map(renderRssJobCard).join('');
        rssResultsCount.textContent = jobs.length + ' jobs from rssjobs.app';
    } catch (error) {
        rssStatus.className = 'status-message error show';
        rssStatus.textContent = '❌ Error: ' + error.message;
        rssJobsContainer.innerHTML = '<div class="empty-state"><p>❌ ' + (error.message || 'Failed to fetch.') + '</p><p><button type="button" class="btn btn-primary" id="rss-retry-btn">Retry</button></p></div>';
        rssResultsCount.textContent = '';
        console.error('rssjobs.app fetch error:', error);
        var retryBtn = document.getElementById('rss-retry-btn');
        if (retryBtn) retryBtn.addEventListener('click', fetchFromRssJobs);
    } finally {
        rssFetchBtn.disabled = false;
        rssFetchBtn.querySelector('.btn-text').style.display = 'inline';
        rssFetchBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

// Parsing is now done server-side, so this function is no longer needed
// Keeping it for reference but it won't be called

function renderRssJobCard(job) {
    const date = job.date ? new Date(job.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    }) : 'Unknown date';

    const loc = job.location || 'Location not specified';
    const company = job.company || 'Company not specified';

    return `
        <div class="job-card">
            <div class="job-header">
                <div class="job-title">
                    <a href="${job.url}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(job.title)}
                    </a>
                </div>
                <div class="job-company">${escapeHtml(company)}</div>
                <div class="job-location">📍 ${escapeHtml(loc)}</div>
            </div>
            ${job.description ? `<div class="job-description">${escapeHtml(job.description.substring(0, 400))}</div>` : ''}
            <div class="job-meta">
                <span class="job-meta-item job-source">${escapeHtml(job.source || 'rssjobs.app')}</span>
                <span class="job-meta-item job-date">📅 ${date}</span>
            </div>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

