const RSSJOBS_API_BASE_URL = 'http://localhost:8000';

const rssFetchBtn = document.getElementById('rss-fetch-btn');
const rssStatus = document.getElementById('rss-status');
const rssJobsContainer = document.getElementById('rss-jobs-container');
const rssResultsCount = document.getElementById('rss-results-count');

rssFetchBtn.addEventListener('click', fetchFromRssJobs);

async function fetchFromRssJobs() {
    const role = document.getElementById('rss-role').value.trim() || 'analyst';
    const location = document.getElementById('rss-location').value.trim() || 'remote';
    const maxItems = parseInt(document.getElementById('rss-max').value) || 100;

    const feedUrl = `https://rssjobs.app/feeds?keywords=${encodeURIComponent(role)}&location=${encodeURIComponent(location)}`;

    rssFetchBtn.disabled = true;
    rssFetchBtn.querySelector('.btn-text').style.display = 'none';
    rssFetchBtn.querySelector('.btn-loader').style.display = 'inline';

    rssStatus.className = 'status-message info show';
    rssStatus.textContent = `⏳ Fetching from rssjobs.app via backend proxy...`;

    rssJobsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div>Loading RSS feed...</div>';

    try {
        // Use backend proxy endpoint (no CORS issues)
        const params = new URLSearchParams({
            keywords: role,
            location: location,
            limit: maxItems.toString(),
        });

        const response = await fetch(`${RSSJOBS_API_BASE_URL}/rssjobs?${params}`);
        const data = await response.json();

        if (!data.ok) {
            throw new Error(data.error || 'Backend returned ok=false');
        }

        const jobs = Array.isArray(data.jobs) ? data.jobs : [];

        if (!jobs.length) {
            rssStatus.className = 'status-message info show';
            rssStatus.textContent = 'ℹ️ No jobs found from rssjobs.app. Try different keywords or location.';
            rssJobsContainer.innerHTML = '<div class="empty-state"><p>No jobs found. Try adjusting keywords or location.</p></div>';
            rssResultsCount.textContent = '';
            return;
        }

        rssStatus.className = 'status-message success show';
        rssStatus.textContent = `✅ Fetched ${jobs.length} jobs from rssjobs.app`;

        rssJobsContainer.innerHTML = jobs.map(renderRssJobCard).join('');
        rssResultsCount.textContent = `${jobs.length} jobs from rssjobs.app`;
    } catch (error) {
        rssStatus.className = 'status-message error show';
        rssStatus.textContent = `❌ Error: ${error.message}. Make sure the API server is running on ${RSSJOBS_API_BASE_URL}`;
        rssJobsContainer.innerHTML = '<div class="empty-state"><p>❌ Failed to fetch from rssjobs.app. Check that the API server is running.</p></div>';
        rssResultsCount.textContent = '';
        console.error('rssjobs.app fetch error:', error);
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

