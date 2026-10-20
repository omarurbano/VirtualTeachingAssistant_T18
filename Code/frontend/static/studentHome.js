// Student dashboard for VTA
// Renders the greeting, learning stats, analytics chart and classroom list.

const state = {
    courses: [],
    analytics: null,
    chart: null
};

const els = {
    greeting: document.getElementById('dashGreeting'),
    greetingName: document.getElementById('greetingName'),
    chipName: document.getElementById('userChipName'),
    avatar: document.getElementById('userAvatar'),
    statClasses: document.getElementById('statClasses'),
    statMaterials: document.getElementById('statMaterials'),
    statQuestions: document.getElementById('statQuestions'),
    analyticsWrap: document.getElementById('analyticsChartWrap'),
    analyticsEmpty: document.getElementById('analyticsEmpty'),
    analyticsCanvas: document.getElementById('analyticsChart'),
    classroomGrid: document.getElementById('classroomGrid'),
    classroomsEmpty: document.getElementById('classroomsEmpty'),
    joinForm: document.getElementById('joinClassForm'),
    joinCode: document.getElementById('joinClassCode'),
    joinBtn: document.getElementById('joinClassBtn'),
    logoutBtn: document.getElementById('logoutBtn'),
    toastStack: document.getElementById('toastStack')
};

// ── Session ────────────────────────────────────────────────
async function checkSession() {
    try {
        const response = await fetch('/auth/me');
        if (!response.ok) {
            window.location.href = '/login';
            return false;
        }
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        sessionStorage.setItem("user_id", data.user.user_id || data.user.id);
        sessionStorage.setItem("user_role", data.user.role);
        sessionStorage.setItem("user_name", data.user.full_name);
        return true;
    } catch (error) {
        console.error('Session check failed:', error);
        window.location.href = '/login';
        return false;
    }
}

// ── Boot ───────────────────────────────────────────────────
(async function init() {
    if (!await checkSession()) return;

    getUserInfo();
    wireEvents();

    await Promise.all([loadAnalytics(), renderCourses()]);
})();

function wireEvents() {
    els.joinForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await joinCourse();
    });

    els.logoutBtn.addEventListener('click', () => logout());
}

// ── User info ──────────────────────────────────────────────
function getUserInfo() {
    const userName = sessionStorage.getItem("user_name");
    const userId = sessionStorage.getItem("user_id");
    const firstName = (userName || '').trim().split(/\s+/)[0] || 'Student';

    applyUserName(userName, firstName);

    if (!userName && userId) {
        // Fallback: fetch from API if not in session
        fetch(`/users/${userId}`)
            .then(response => response.json())
            .then(user => {
                applyUserName(user.full_name, (user.full_name || user.first_name || 'Student').split(/\s+/)[0]);
            })
            .catch(error => {
                console.error("Error fetching user info:", error);
                applyUserName(null, 'Student');
            });
    }
}

function applyUserName(fullName, firstName) {
    const hour = new Date().getHours();
    const partOfDay = hour < 12 ? 'Good morning' : (hour < 18 ? 'Good afternoon' : 'Good evening');
    const name = firstName || 'Student';

    els.greetingName.textContent = name;
    els.greeting.innerHTML = `${partOfDay}, <span class="accent">${escapeHtml(name)}</span> 👋`;
    els.chipName.textContent = fullName || name;
    els.avatar.textContent = name.charAt(0).toUpperCase() || 'S';
}

// ── Analytics (stats + 7 day trend) ────────────────────────
async function loadAnalytics() {
    try {
        const response = await fetch('/api/student/analytics');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        state.analytics = data;

        els.statClasses.textContent = data.classes_joined ?? 0;
        els.statMaterials.textContent = data.total_materials ?? 0;
        els.statQuestions.textContent = data.total_questions ?? 0;

        renderAnalyticsChart(data.daily || []);
    } catch (error) {
        console.error('Error loading analytics:', error);
        els.statClasses.textContent = '0';
        els.statMaterials.textContent = '0';
        els.statQuestions.textContent = '0';
        showEmptyAnalytics();
    }
}

function renderAnalyticsChart(daily) {
    const hasData = daily.some(day => (day.count || 0) > 0);

    if (!hasData || typeof Chart === 'undefined') {
        showEmptyAnalytics();
        return;
    }

    els.analyticsEmpty.hidden = true;
    els.analyticsWrap.hidden = false;

    if (state.chart) state.chart.destroy();

    const ctx = els.analyticsCanvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(47, 107, 237, 0.22)');
    gradient.addColorStop(1, 'rgba(47, 107, 237, 0)');

    state.chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: daily.map(day => day.label),
            datasets: [{
                label: 'Questions asked',
                data: daily.map(day => day.count || 0),
                borderColor: '#2f6bed',
                backgroundColor: gradient,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointBackgroundColor: '#ffffff',
                pointBorderColor: '#2f6bed',
                pointBorderWidth: 2,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#101828',
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: false,
                    titleFont: { family: "'Inter', sans-serif", size: 12 },
                    bodyFont: { family: "'Inter', sans-serif", size: 13 }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: { color: '#98a2b3', font: { family: "'Inter', sans-serif", size: 12 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#eef1f6' },
                    border: { display: false },
                    ticks: {
                        color: '#98a2b3',
                        font: { family: "'Inter', sans-serif", size: 12 },
                        precision: 0
                    }
                }
            }
        }
    });
}

function showEmptyAnalytics() {
    els.analyticsWrap.hidden = true;
    els.analyticsEmpty.hidden = false;
}

// ── Classrooms ─────────────────────────────────────────────
async function renderCourses() {
    const userID = sessionStorage.getItem("user_id");
    if (!userID) {
        console.error("No user ID in session");
        return;
    }

    try {
        const response = await fetch(`/studentcourses/${userID}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        const courses = data.courses || data || [];
        state.courses = Array.isArray(courses) ? courses : [];

        const byCourse = new Map(
            ((state.analytics && state.analytics.courses) || []).map(c => [String(c.course_id), c])
        );

        if (state.courses.length === 0) {
            els.classroomGrid.innerHTML = '';
            els.classroomsEmpty.hidden = false;
            return;
        }

        els.classroomsEmpty.hidden = true;
        els.classroomGrid.innerHTML = state.courses.map(course => {
            const meta = Array.isArray(course.courses) ? (course.courses[0] || {}) : (course.courses || {});
            const name = meta.name || course.name || course.course_name || course.code || "Unknown Course";
            const code = meta.code || course.code || '';
            const courseId = course.course_id || course.id || meta.id;
            const stats = byCourse.get(String(courseId)) || {};

            const metaParts = [];
            if (code) metaParts.push(code);
            if (stats.questions) metaParts.push(`${stats.questions} question${stats.questions === 1 ? '' : 's'}`);
            if (stats.materials) metaParts.push(`${stats.materials} material${stats.materials === 1 ? '' : 's'}`);

            return `
                <button class="classroom-card" type="button" data-course-id="${escapeHtml(String(courseId ?? ''))}">
                    <span class="icon-tile" aria-hidden="true">
                        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                        </svg>
                    </span>
                    <span class="classroom-body">
                        <span class="classroom-name">${escapeHtml(name)}</span>
                        <span class="classroom-meta">${escapeHtml(metaParts.join(' · ') || 'Open to start learning')}</span>
                    </span>
                    <span class="classroom-go" aria-hidden="true">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M5 12h14M13 6l6 6-6 6"/>
                        </svg>
                    </span>
                </button>
            `;
        }).join('');

        els.classroomGrid.querySelectorAll('.classroom-card').forEach(card => {
            card.addEventListener('click', () => {
                const courseId = card.dataset.courseId;
                if (courseId) window.location.href = `/?course=${encodeURIComponent(courseId)}`;
            });
        });

    } catch (error) {
        console.error("Error fetching courses:", error);
        els.classroomGrid.innerHTML = '';
        els.classroomsEmpty.hidden = false;
        showToast('Error loading classrooms', 'error');
    }
}

// ── Join a class ───────────────────────────────────────────
async function validCourseNumber(courseCode) {
    try {
        const response = await fetch(`/course/code/${encodeURIComponent(courseCode)}`);
        if (response.ok) {
            return await response.json();
        }
        showToast('Class code not found', 'error');
        return null;
    } catch (error) {
        console.error("Course lookup failed:", error);
        showToast('Class lookup failed', 'error');
        return null;
    }
}

async function joinCourse() {
    const courseCode = els.joinCode.value.trim().toUpperCase();
    if (!courseCode) {
        showToast('Please enter a class code', 'error');
        return;
    }

    els.joinBtn.disabled = true;

    const course = await validCourseNumber(courseCode);
    if (!course) {
        els.joinBtn.disabled = false;
        return;
    }

    const userId = sessionStorage.getItem("user_id");
    const courseId = course.id || course.course_id;

    try {
        const response = await fetch(`/addCourse/${userId}/${courseId}`, { method: 'POST' });

        if (response.ok) {
            showToast('Class joined successfully', 'success');
            els.joinCode.value = '';
            await Promise.all([loadAnalytics(), renderCourses()]);
        } else {
            let message = 'Failed to join class';
            try {
                const error = await response.json();
                message = error.error || message;
            } catch (_) { /* non-json error body */ }
            showToast(message, 'error');
        }
    } catch (error) {
        console.error("Add course failed:", error);
        showToast('Failed to join class', 'error');
    } finally {
        els.joinBtn.disabled = false;
    }
}

// ── Toast ──────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `app-toast ${type}`;
    toast.setAttribute('role', 'status');

    const icon = type === 'success'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
        : type === 'error'
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>';

    toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
    els.toastStack.appendChild(toast);

    setTimeout(() => toast.remove(), 3200);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// ── Logout ─────────────────────────────────────────────────
function logout() {
    fetch('/auth/logout', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            sessionStorage.clear();
            window.location.href = data.redirect || '/login';
        })
        .catch(err => {
            console.error('Logout failed:', err);
            sessionStorage.clear();
            window.location.href = '/login';
        });
}
