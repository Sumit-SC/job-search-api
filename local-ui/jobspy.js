const JOBSPY_API_BASE_URL = (typeof window !== 'undefined' && window.location && window.location.origin)
    ? window.location.origin
    : 'http://localhost:8000';

const jobspyFetchBtn = document.getElementById('jobspy-fetch-btn');
const jobspyStatus = document.getElementById('jobspy-status');
const jobspyJobsContainer = document.getElementById('jobspy-jobs-container');
const jobspyResultsCount = document.getElementById('jobspy-results-count');

jobspyFetchBtn.addEventListener('click', fetchViaJobSpy);

async function fetchViaJobSpy() {
    const query = document.getElementById('jobspy-query').value.trim() || null;
    const location = document.getElementById('jobspy-location').value.trim() || null;
    const days = parseInt(document.getElementById('jobspy-days').value) || 3;
    const limit = parseInt(document.getElementById('jobspy-limit').value) || 100;

    const params = new URLSearchParams({
        days: days.toString(),
        limit: limit.toString(),
    });
    if (query) params.append('q', query);
    if (location) params.append('location', location);

    jobspyFetchBtn.disabled = true;
    jobspyFetchBtn.querySelector('.btn-text').style.display = 'none';
    jobspyFetchBtn.querySelector('.btn-loader').style.display = 'inline';

    jobspyStatus.className = 'status-message info show';
    jobspyStatus.textContent = '⏳ Fetching jobs via JobSpy backend...';

    jobspyJobsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading JobSpy results...</div>';

    try {
        const response = await fetch(`${JOBSPY_API_BASE_URL}/jobspy?${params}`);
        const data = await response.json();

        if (!data.ok) {
            throw new Error(data.error || 'JobSpy backend returned ok=false');
        }

        const jobs = Array.isArray(data.jobs) ? data.jobs : [];
        if (!jobs.length) {
            jobspyStatus.className = 'status-message info show';
            jobspyStatus.textContent = 'ℹ️ JobSpy returned 0 jobs. Try widening query, location, or days.';
            jobspyJobsContainer.innerHTML = '<div class="empty-state"><p>No jobs from JobSpy. Try a broader query or location.</p></div>';
            jobspyResultsCount.textContent = '';
            return;
        }

        jobspyStatus.className = 'status-message success show';
        jobspyStatus.textContent = `✅ JobSpy returned ${jobs.length} jobs`;
        jobspyResultsCount.textContent = `${jobs.length} jobs from JobSpy`;

        jobspyJobsContainer.innerHTML = jobs.map(renderJobSpyCard).join('');
    } catch (error) {
        jobspyStatus.className = 'status-message error show';
        jobspyStatus.textContent = `❌ Error calling /jobspy: ${error.message}`;
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

