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

var JOBSPY_ALL_BOARDS = [
    'indeed', 'linkedin', 'zip_recruiter', 'glassdoor', 'google',
    'dice', 'simplyhired', 'monster', 'careerbuilder', 'stepstone',
    'wellfound', 'jobscollider', 'bayt', 'naukri', 'bdjobs', 'internshala',
    'exa', 'upwork', 'builtin', 'snagajob', 'dribbble',
    'remoteok', 'remotive', 'weworkremotely', 'jobicy', 'himalayas', 'arbeitnow',
    'greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters',
    'rippling', 'workday', 'recruitee', 'teamtailor', 'bamboohr',
    'personio', 'jazzhr', 'icims', 'taleo', 'successfactors',
    'jobvite', 'adp', 'ukg', 'breezyhr', 'comeet', 'pinpoint',
    'amazon', 'apple', 'microsoft', 'nvidia', 'tiktok', 'uber',
    'cursor', 'google_careers', 'meta', 'netflix', 'stripe', 'openai',
    'usajobs', 'adzuna', 'reed', 'jooble', 'careerjet'
];

var JOBSPY_HINTS = {
    popular: '👉 Popular: Indeed, LinkedIn, Google, Glassdoor, ZipRecruiter. Best for general job hunt.',
    remote: '👉 Remote: RemoteOK, Remotive, WeWorkRemotely, Jobicy, Himalayas, Arbeitnow, Wellfound, Jobscollider. Use for remote-only roles.',
    all: '👉 All 65+ boards: job boards, remote boards, ATS (Greenhouse, Lever), company pages (Amazon, Google), aggregators. Slower but widest coverage.',
    manual: '👉 Select one or more boards above. Then click Fetch.'
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

    var params = new URLSearchParams({
        days: days.toString(),
        limit: limit.toString(),
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

    jobspyFetchBtn.disabled = true;
    jobspyFetchBtn.querySelector('.btn-text').style.display = 'none';
    jobspyFetchBtn.querySelector('.btn-loader').style.display = 'inline';

    jobspyStatus.className = 'status-message info show';
    jobspyStatus.textContent = '⏳ Fetching jobs via JobSpy (' + preset + ')...';

    jobspyJobsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading JobSpy results...</div>';

    try {
        var response = await fetch(JOBSPY_API_BASE_URL + '/jobspy?' + params.toString());
        var data = await response.json();

        if (!data.ok) {
            throw new Error(data.error || 'JobSpy backend returned ok=false');
        }

        var jobs = Array.isArray(data.jobs) ? data.jobs : [];
        if (!jobs.length) {
            jobspyStatus.className = 'status-message info show';
            jobspyStatus.textContent = 'ℹ️ JobSpy returned 0 jobs. Try widening query, location, or days.';
            jobspyJobsContainer.innerHTML = '<div class="empty-state"><p>No jobs from JobSpy. Try a broader query or location.</p></div>';
            jobspyResultsCount.textContent = '';
            return;
        }

        jobspyStatus.className = 'status-message success show';
        jobspyStatus.textContent = '✅ JobSpy returned ' + jobs.length + ' jobs';
        jobspyResultsCount.textContent = jobs.length + ' jobs from JobSpy';

        jobspyJobsContainer.innerHTML = jobs.map(renderJobSpyCard).join('');
    } catch (error) {
        jobspyStatus.className = 'status-message error show';
        jobspyStatus.textContent = '❌ Error calling /jobspy: ' + error.message;
        jobspyJobsContainer.innerHTML = '<div class="empty-state"><p>❌ Failed to fetch from /jobspy. Check that the API server is running and python-jobspy is installed.</p></div>';
        jobspyResultsCount.textContent = '';
        console.error('JobSpy UI error:', error);
    } finally {
        jobspyFetchBtn.disabled = false;
        jobspyFetchBtn.querySelector('.btn-text').style.display = 'inline';
        jobspyFetchBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

function renderJobSpyCard(job) {
    const date = job.date ? new Date(job.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    }) : 'Unknown date';

    const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
    const loc = job.location || 'Location not specified';

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

