(function () {
    var PREP_STORAGE_KEY = 'interview_prep_planner';
    var ROLE_STORAGE_KEY = 'interview_prep_role';

    var defaultChecklist = [
        { id: 'research_company', label: 'Research company (product, culture, recent news)' },
        { id: 'read_jd', label: 'Re-read job description and match your experience' },
        { id: 'star_stories', label: 'Prepare 3–5 STAR stories (Situation, Task, Action, Result)' },
        { id: 'technical_basics', label: 'Review technical basics for the role' },
        { id: 'questions_to_ask', label: 'Prepare 3–5 questions to ask the interviewer' },
        { id: 'mock_once', label: 'Do at least one mock interview (here or with AI)' },
        { id: 'outfit_tech', label: 'Test tech (camera, mic, link) if remote' },
    ];

    function getStoredChecklist() {
        var base = defaultChecklist.map(function (x) { return { id: x.id, label: x.label, done: false }; });
        try {
            var raw = localStorage.getItem(PREP_STORAGE_KEY);
            if (raw) {
                var parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    parsed.forEach(function (s) {
                        var b = base.find(function (x) { return x.id === s.id; });
                        if (b) b.done = !!s.done;
                    });
                }
            }
        } catch (e) {}
        return base;
    }

    function saveChecklist(items) {
        try {
            localStorage.setItem(PREP_STORAGE_KEY, JSON.stringify(items));
        } catch (e) {}
    }

    function getStoredRole() {
        try {
            var raw = localStorage.getItem(ROLE_STORAGE_KEY);
            if (raw) return JSON.parse(raw);
        } catch (e) {}
        return { role: '', company: '', date: '' };
    }

    function saveRole(role, company, date) {
        try {
            localStorage.setItem(ROLE_STORAGE_KEY, JSON.stringify({ role: role, company: company, date: date }));
        } catch (e) {}
    }

    function renderChecklist() {
        var list = document.getElementById('prep-checklist');
        if (!list) return;
        var items = getStoredChecklist();
        list.innerHTML = items.map(function (item) {
            return '<li class="prep-checklist-item">' +
                '<label><input type="checkbox" data-id="' + escapeHtml(item.id) + '" ' + (item.done ? 'checked' : '') + '> ' + escapeHtml(item.label) + '</label>' +
                '</li>';
        }).join('');
        list.querySelectorAll('input[type=checkbox]').forEach(function (cb) {
            cb.addEventListener('change', function () {
                var id = cb.getAttribute('data-id');
                var items = getStoredChecklist().map(function (i) {
                    if (i.id === id) i.done = cb.checked;
                    return i;
                });
                saveChecklist(items);
            });
        });
    }

    function updateDaysLeft() {
        var dateInput = document.getElementById('prep-date');
        var el = document.getElementById('prep-days-left');
        if (!el || !dateInput || !dateInput.value) {
            if (el) el.textContent = '';
            return;
        }
        var d = new Date(dateInput.value);
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        d.setHours(0, 0, 0, 0);
        var diff = Math.ceil((d - today) / (1000 * 60 * 60 * 24));
        if (diff < 0) el.textContent = 'Interview date was in the past.';
        else if (diff === 0) el.textContent = '📅 Interview is today. Good luck!';
        else el.textContent = '📅 ' + diff + ' day(s) until interview.';
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // --- Questions bank ---
    var questions = {
        behavioral: [
            'Tell me about yourself and why you want this role.',
            'Describe a time you disagreed with a teammate. How did you handle it?',
            'Tell me about a project that failed or didn’t go as planned. What did you learn?',
            'Give an example of when you had to meet a tight deadline.',
            'Describe a situation where you had to learn something new quickly.',
            'Tell me about a time you took the lead on something.',
            'How do you prioritize when you have multiple urgent tasks?',
            'Describe a time you had to work with a difficult stakeholder.',
            'Tell me about a time you improved a process or outcome.',
            'How do you handle feedback or criticism?',
        ],
        technical: [
            'Walk me through a technical project you’re proud of.',
            'How do you approach debugging a problem you’ve never seen before?',
            'Explain [a key concept for this role] to a non-technical person.',
            'Describe your experience with [tool/stack from JD].',
            'How do you stay updated with changes in your field?',
            'Tell me about a time you had to make a trade-off between speed and quality.',
            'How do you document and share knowledge with your team?',
            'Describe a time you had to simplify a complex system or problem.',
        ],
        company: [
            'Why do you want to join our company?',
            'What do you know about our product and our users?',
            'Where do you see yourself in 2–3 years?',
            'What’s your expected salary or range? (Practice answering calmly.)',
            'When can you start?',
            'Do you have any questions for us?',
            'What would you want to achieve in your first 90 days here?',
        ],
    };

    function getRoleCategory(role) {
        var r = (role || '').toLowerCase();
        if (/engineer|developer|software|backend|frontend|fullstack|sre|devops/i.test(r)) return 'Software Engineer';
        if (/data analyst|analytics|bi |business intelligence/i.test(r)) return 'Data Analyst';
        if (/data scientist|machine learning|ml|ai /i.test(r)) return 'Data Scientist';
        if (/product manager|pm\b/i.test(r)) return 'Product Manager';
        if (/design|ux|ui /i.test(r)) return 'Design';
        return 'General';
    }

    var roleTips = {
        'Software Engineer': ['Review data structures & algorithms if relevant.', 'Be ready to explain past projects and your role.', 'Know the stack in the JD (e.g. React, Python, AWS).', 'Prepare for system design if senior.'],
        'Data Analyst': ['Know SQL and how you’d explore a new dataset.', 'Be ready to explain metrics and KPIs you’ve used.', 'Have 1–2 examples of storytelling with data.', 'Mention tools: Excel, SQL, BI tools (Tableau, Looker, etc.).'],
        'Data Scientist': ['Be ready to explain a model or analysis end-to-end.', 'Know basics: bias/variance, validation, metrics.', 'Prepare for “how would you approach…” questions.', 'Mention Python/R, SQL, and any ML frameworks.'],
        'Product Manager': ['Prepare framework for prioritization (e.g. RICE).', 'Have examples of balancing user needs and business goals.', 'Be ready to discuss a product you use and how you’d improve it.', 'Prepare questions about roadmap and team structure.'],
        'Design': ['Have your portfolio ready and a couple of case studies.', 'Be ready to walk through your process (research, ideation, iteration).', 'Prepare for “how do you work with engineers?”.', 'Know the company’s product and design patterns.'],
        'General': ['Match your stories to the job description.', 'Prepare 3–5 questions to ask them.', 'Research the company and recent news.', 'Practice out loud and time yourself.'],
    };

    function getTipsForRole(role) {
        var cat = getRoleCategory(role);
        return roleTips[cat] || roleTips.General;
    }

    function pickQuestion(category, role) {
        var pool = [];
        if (category === 'mixed') {
            pool = questions.behavioral.concat(questions.technical).concat(questions.company);
        } else {
            pool = (questions[category] || questions.behavioral).slice();
            if (category === 'technical' && role) {
                var r = (role || '').toLowerCase();
                pool = pool.map(function (q) {
                    return q.replace(/\[.*?\]/g, function (m) {
                        if (/data analyst|analytics/i.test(r)) return 'a key metric or dashboard you built';
                        if (/engineer|developer|software/i.test(r)) return 'a design or code decision you made';
                        return 'a key concept for this role';
                    });
                });
            }
        }
        return pool[Math.floor(Math.random() * pool.length)];
    }

    function setQuestionText(text) {
        var el = document.getElementById('prep-question-text');
        if (el) el.textContent = text || 'Click "Next question" to start.';
    }

    function buildAIPrompt(role, company) {
        var r = role || 'this role';
        var c = company ? (' at ' + company) : '';
        return 'You are an interviewer. I am preparing for an interview for the position of "' + r + '"' + c + '.\n\n' +
            'Ask me one question at a time (behavioral, technical, or fit). Wait for my answer, then give brief constructive feedback and ask the next question. Keep it concise. After 5–7 questions, give a short overall prep tip.';
    }

    function updateAIPromptText() {
        var role = document.getElementById('prep-role') && document.getElementById('prep-role').value.trim();
        var company = document.getElementById('prep-company') && document.getElementById('prep-company').value.trim();
        var ta = document.getElementById('prep-ai-prompt-text');
        if (ta) ta.value = buildAIPrompt(role, company);
    }

    function copyPrompt(forChat) {
        var text = forChat
            ? buildAIPrompt(
                document.getElementById('prep-role') && document.getElementById('prep-role').value.trim(),
                document.getElementById('prep-company') && document.getElementById('prep-company').value.trim()
            )
            : (document.getElementById('prep-ai-prompt-text') && document.getElementById('prep-ai-prompt-text').value);
        if (!text) return;
        navigator.clipboard.writeText(text).then(function () {
            alert('Copied to clipboard. Paste into ChatGPT or Claude to start the mock.');
        }).catch(function () {
            var ta = document.getElementById('prep-ai-prompt-text');
            if (ta) { ta.select(); document.execCommand('copy'); alert('Copied.'); }
        });
    }

    function renderTips() {
        var role = document.getElementById('prep-role') && document.getElementById('prep-role').value.trim();
        var container = document.getElementById('prep-tips-content');
        if (!container) return;
        var tips = getTipsForRole(role);
        container.innerHTML = '<ul class="prep-tips-list">' + tips.map(function (t) { return '<li>' + escapeHtml(t) + '</li>'; }).join('') + '</ul>';
    }

    // --- URL params (e.g. from "Prep for this" on a job card) ---
    function applyUrlParams() {
        var params = new URLSearchParams(window.location.search);
        var role = params.get('role') || params.get('title') || params.get('q');
        var company = params.get('company');
        if (role) {
            var roleEl = document.getElementById('prep-role');
            if (roleEl) roleEl.value = decodeURIComponent(role);
        }
        if (company) {
            var companyEl = document.getElementById('prep-company');
            if (companyEl) companyEl.value = decodeURIComponent(company);
        }
        saveRole(
            document.getElementById('prep-role') && document.getElementById('prep-role').value,
            document.getElementById('prep-company') && document.getElementById('prep-company').value,
            document.getElementById('prep-date') && document.getElementById('prep-date').value
        );
        updateAIPromptText();
        renderTips();
    }

    // --- Init ---
    function init() {
        var stored = getStoredRole();
        var roleEl = document.getElementById('prep-role');
        var companyEl = document.getElementById('prep-company');
        var dateEl = document.getElementById('prep-date');
        if (roleEl) roleEl.value = stored.role || '';
        if (companyEl) companyEl.value = stored.company || '';
        if (dateEl) dateEl.value = stored.date || '';

        applyUrlParams();

        roleEl && roleEl.addEventListener('input', function () {
            saveRole(roleEl.value, companyEl && companyEl.value, dateEl && dateEl.value);
            updateAIPromptText();
            renderTips();
        });
        companyEl && companyEl.addEventListener('input', function () {
            saveRole(roleEl && roleEl.value, companyEl.value, dateEl && dateEl.value);
            updateAIPromptText();
        });
        dateEl && dateEl.addEventListener('change', function () {
            saveRole(roleEl && roleEl.value, companyEl && companyEl.value, dateEl.value);
            updateDaysLeft();
        });

        renderChecklist();
        updateDaysLeft();
        updateAIPromptText();
        renderTips();

        document.getElementById('prep-next-q') && document.getElementById('prep-next-q').addEventListener('click', function () {
            var cat = document.getElementById('prep-category') && document.getElementById('prep-category').value;
            var role = document.getElementById('prep-role') && document.getElementById('prep-role').value.trim();
            setQuestionText(pickQuestion(cat, role));
        });

        document.getElementById('prep-copy-prompt') && document.getElementById('prep-copy-prompt').addEventListener('click', function () {
            copyPrompt(true);
        });

        document.getElementById('prep-copy-ai-prompt') && document.getElementById('prep-copy-ai-prompt').addEventListener('click', function () {
            copyPrompt(false);
        });
    }

    init();
})();
