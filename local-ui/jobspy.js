function getJobspyApiBase() {
    if (typeof window === 'undefined' || !window.location) return 'http://localhost:8000';
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get('api_base') || params.get('api');
    if (fromQuery && fromQuery.startsWith('http')) return fromQuery.replace(/\/$/, '');
    const origin = window.location.origin;
    if (origin && origin !== 'null' && origin !== 'file://') return origin;
    return 'https://job-search-api-production-5d5d.up.railway.app';
}
const JOBSPY_API_BASE_URL = getJobspyApiBase();

var JOBSPY_CLIENT_CACHE_TTL_MS = 5 * 60 * 1000; // 5 min
var JOBSPY_CACHE_KEY_PREFIX = 'jobspy_';

function jobspyClientCacheKey(params) {
    return JOBSPY_CACHE_KEY_PREFIX + params.toString();
}

function getJobspyClientCached(params) {
    try {
        var key = jobspyClientCacheKey(params);
        var raw = sessionStorage.getItem(key);
        if (!raw) return null;
        var entry = JSON.parse(raw);
        if (entry.expiresAt && Date.now() > entry.expiresAt) {
            sessionStorage.removeItem(key);
            return null;
        }
        return entry;
    } catch (e) {
        return null;
    }
}

function setJobspyClientCache(params, data, xCache) {
    try {
        var key = jobspyClientCacheKey(params);
        sessionStorage.setItem(key, JSON.stringify({
            data: data,
            xCache: xCache || null,
            cachedAt: Date.now(),
            expiresAt: Date.now() + JOBSPY_CLIENT_CACHE_TTL_MS
        }));
    } catch (e) { /* quota or disabled */ }
}

// python-jobspy supports only these 8 sites
var JOBSPY_ALL_BOARDS = [
    'indeed', 'linkedin', 'zip_recruiter', 'glassdoor', 'google',
    'bayt', 'naukri', 'bdjobs'
];

var JOBSPY_HINTS = {
    popular: 'Popular: Indeed, LinkedIn, ZipRecruiter, Google, Glassdoor.',
    remote: 'Same boards with remote-friendly search. Use location Remote or tick Remote only.',
    all: 'All 8 supported boards: Indeed, LinkedIn, ZipRecruiter, Glassdoor, Google, Bayt, Naukri, BDJobs.',
    manual: 'Select one or more boards above, then click Fetch.'
};

const jobspyFetchBtn = document.getElementById('jobspy-fetch-btn');
const jobspyStatus = document.getElementById('jobspy-status');
const jobspyJobsContainer = document.getElementById('jobspy-jobs-container');
const jobspyResultsCount = document.getElementById('jobspy-results-count');
const jobspyPreset = document.getElementById('jobspy-preset');
const jobspyManualWrap = document.getElementById('jobspy-manual-boards-wrap');
const jobspyManualBoards = document.getElementById('jobspy-manual-boards');
const jobspyNextHint = document.getElementById('jobspy-next-hint');

function renderPresetHint() {
    if (!jobspyNextHint) return;
    var preset = (jobspyPreset && jobspyPreset.value) || 'popular';
    jobspyNextHint.textContent = JOBSPY_HINTS[preset] || JOBSPY_HINTS.popular;
    jobspyNextHint.style.display = 'block';
}

function renderManualBoards() {
    if (!jobspyManualBoards) return;
    jobspyManualBoards.innerHTML = '';
    JOBSPY_ALL_BOARDS.forEach(function (id) {
        var label = document.createElement('label');
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = id;
        cb.name = 'jobspy-board';
        label.appendChild(cb);
        label.appendChild(document.createTextNode(id));
        jobspyManualBoards.appendChild(label);
    });
}

if (jobspyPreset) {
    jobspyPreset.addEventListener('change', function () {
        var showManual = jobspyPreset.value === 'manual';
        if (jobspyManualWrap) jobspyManualWrap.style.display = showManual ? 'block' : 'none';
        renderPresetHint();
    });
}

renderManualBoards();
renderPresetHint();
if (jobspyManualWrap) jobspyManualWrap.style.display = jobspyPreset && jobspyPreset.value === 'manual' ? 'block' : 'none';

jobspyFetchBtn.addEventListener('click', fetchViaJobSpy);

async function fetchViaJobSpy() {
    var query = document.getElementById('jobspy-query').value.trim() || null;
    var location = document.getElementById('jobspy-location').value.trim() || null;
    var days = parseInt(document.getElementById('jobspy-days').value, 10) || 3;
    var limit = parseInt(document.getElementById('jobspy-limit').value, 10) || 100;
    var preset = (jobspyPreset && jobspyPreset.value) || 'popular';
    var countryEl = document.getElementById('jobspy-country');
    var country = (countryEl && countryEl.value) ? countryEl.value : 'usa';
    var remoteOnly = document.getElementById('jobspy-remote-only');
    var isRemote = remoteOnly && remoteOnly.checked;

    var params = new URLSearchParams({
        days: days.toString(),
        limit: limit.toString(),
        country: country,
        is_remote: isRemote.toString(),
    });
    if (query) params.set('q', query);
    if (location) params.set('location', location);

    if (preset === 'manual' && jobspyManualBoards) {
        var checked = jobspyManualBoards.querySelectorAll('input[name="jobspy-board"]:checked');
        var sites = [];
        for (var i = 0; i < checked.length; i++) sites.push(checked[i].value);
        if (sites.length) params.set('sites', sites.join(','));
        else preset = 'popular';
    }
    if (preset !== 'manual' || !params.has('sites')) params.set('preset', preset);

    var skipCache = document.getElementById('jobspy-skip-cache');
    if (skipCache && skipCache.checked) params.set('skip_cache', 'true');

    var clientCached = !params.has('skip_cache') ? getJobspyClientCached(params) : null;
    if (clientCached && clientCached.data && Array.isArray(clientCached.data.jobs) && clientCached.data.jobs.length > 0) {
        var jobs = clientCached.data.jobs;
        var mins = Math.round((Date.now() - clientCached.cachedAt) / 60000);
        jobspyStatus.className = 'status-message info show';
        jobspyStatus.textContent = '📦 Showing cached results (' + mins + ' min ago). Click Fetch again to refresh.';
        if (clientCached.xCache === 'HIT') jobspyStatus.textContent += ' (server cache hit)';
        jobspyResultsCount.textContent = jobs.length + ' jobs';
        jobspyJobsContainer.innerHTML = jobs.map(renderJobSpyCard).join('');
        return;
    }

    jobspyFetchBtn.disabled = true;
    jobspyFetchBtn.querySelector('.btn-text').style.display = 'none';
    jobspyFetchBtn.querySelector('.btn-loader').style.display = 'inline';

    jobspyStatus.className = 'status-message info show';
    jobspyStatus.textContent = '⏳ Fetching jobs via JobSpy (' + preset + ')...';

    jobspyJobsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading JobSpy results...</div>';

    try {
        var response = await fetch(JOBSPY_API_BASE_URL + '/jobspy?' + params.toString());
        var xCache = response.headers.get('X-Cache') || null;
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
            throw new Error(data.error || 'JobSpy backend returned ok=false');
        }

        var jobs = Array.isArray(data.jobs) ? data.jobs : [];
        setJobspyClientCache(params, data, xCache);

        if (!jobs.length) {
            window.lastJobspyJobs = [];
            jobspyStatus.className = 'status-message info show';
            jobspyStatus.textContent = 'ℹ️ JobSpy returned 0 jobs. Try widening query, location, or days.';
            jobspyJobsContainer.innerHTML = '<div class="empty-state"><p>No jobs from JobSpy. Try a broader query or location.</p></div>';
            jobspyResultsCount.textContent = '';
            return;
        }

        jobspyStatus.className = 'status-message success show';
        jobspyStatus.textContent = '✅ JobSpy returned ' + jobs.length + ' jobs';
        if (xCache === 'HIT') jobspyStatus.textContent += ' (from server cache)';
        jobspyResultsCount.textContent = jobs.length + ' jobs from JobSpy';

        window.lastJobspyJobs = jobs;
        jobspyJobsContainer.innerHTML = jobs.map(function (job, i) { return renderJobSpyCard(job, i); }).join('');
    } catch (error) {
        jobspyStatus.className = 'status-message error show';
        jobspyStatus.textContent = '❌ Error: ' + error.message;
        jobspyJobsContainer.innerHTML = '<div class="empty-state"><p>❌ ' + (error.message || 'Failed to fetch.') + '</p><p><button type="button" class="btn btn-primary" id="jobspy-retry-btn">Retry</button></p></div>';
        jobspyResultsCount.textContent = '';
        console.error('JobSpy UI error:', error);
        var retryBtn = document.getElementById('jobspy-retry-btn');
        if (retryBtn) retryBtn.addEventListener('click', fetchViaJobSpy);
    } finally {
        jobspyFetchBtn.disabled = false;
        jobspyFetchBtn.querySelector('.btn-text').style.display = 'inline';
        jobspyFetchBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

function buildChatGPTPrepPrompt(job) {
    var role = job.title || 'this role';
    var company = job.company || '';
    var location = job.location || '';
    var desc = String(job.description || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
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

function renderJobSpyCard(job, index) {
    const date = job.date ? new Date(job.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    }) : 'Unknown date';

    const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
    const loc = job.location || 'Location not specified';
    const dataIndex = typeof index === 'number' ? index : '';

    return `
        <div class="job-card">
            <div class="job-header">
                <div class="job-title">
                    <a href="${job.url}" target="_blank" rel="noopener noreferrer">
                        ${escapeHtml(job.title || '')}
                    </a>
                </div>
                <div class="job-company">${escapeHtml(job.company || 'Unknown Company')}</div>
                <div class="job-location">📍 ${escapeHtml(loc)}</div>
            </div>
            ${job.description ? `<div class="job-description">${escapeHtml(String(job.description).substring(0, 400))}</div>` : ''}
            <div class="job-meta">
                <span class="job-meta-item job-source">${escapeHtml(job.source || 'jobspy')}</span>
                <span class="job-meta-item job-date">📅 ${date}</span>
                ${salary ? `<span class="job-meta-item">💰 ${salary}</span>` : ''}
                <a href="interview-prep.html?role=${encodeURIComponent(job.title || '')}&company=${encodeURIComponent(job.company || '')}" class="job-meta-item job-prep-link" title="Open interview prep for this role">🎯 Prep</a>
                <button type="button" class="job-meta-item job-copy-chatgpt-btn" data-job-index="${dataIndex}" title="Copy JD + prompt and open ChatGPT/Gemini">📋 Copy for ChatGPT</button>
            </div>
        </div>
    `;
}

function formatSalary(min, max, currency) {
    if (min == null && max == null) return null;
    const curr = currency || 'USD';
    const fmt = (n) => {
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
        return n.toString();
    };
    if (min != null && max != null && min === max) return `${curr} ${fmt(min)}`;
    if (min == null) return `Up to ${curr} ${fmt(max)}`;
    if (max == null) return `${curr} ${fmt(min)}+`;
    return `${curr} ${fmt(min)}-${fmt(max)}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

if (jobspyJobsContainer) {
    jobspyJobsContainer.addEventListener('click', function (e) {
        var btn = e.target.closest('.job-copy-chatgpt-btn');
        if (!btn || !window.lastJobspyJobs || !window.lastJobspyJobs.length) return;
        var idx = parseInt(btn.getAttribute('data-job-index'), 10);
        if (isNaN(idx) || idx < 0 || idx >= window.lastJobspyJobs.length) return;
        var job = window.lastJobspyJobs[idx];
        var prompt = buildChatGPTPrepPrompt(job);
        navigator.clipboard.writeText(prompt).then(function () {
            window.open('https://chat.openai.com/', '_blank', 'noopener');
            alert('Prompt copied. Paste it in the new ChatGPT tab. The AI will ask about your background first, then run a mock interview based on this JD.');
        }).catch(function () {
            window.prompt('Copy this prompt and paste into ChatGPT or Gemini:', prompt);
        });
    });
}

