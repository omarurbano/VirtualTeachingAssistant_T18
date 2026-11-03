// MCQ practice mode for VTA
// One question at a time, instant feedback, hint ladder and session progress.
// Progress is kept in this browser tab only and is never sent to the server.

const state = {
    courseId: null,
    courseName: '',
    difficulty: 'easy',
    token: null,
    selected: null,
    answered: false,
    hintLevel: 0,
    hintCount: 0,
    recentSeeds: [],
    progress: { answered: 0, correct: 0, streak: 0 }
};

const els = {
    setupCard: document.getElementById('setupCard'),
    courseSelect: document.getElementById('courseSelect'),
    difficultyBtns: document.querySelectorAll('.difficulty-btn'),
    startBtn: document.getElementById('startBtn'),
    progressBar: document.getElementById('progressBar'),
    progAnswered: document.getElementById('progAnswered'),
    progCorrect: document.getElementById('progCorrect'),
    progStreak: document.getElementById('progStreak'),
    progMeta: document.getElementById('progMeta'),
    questionCard: document.getElementById('questionCard'),
    questionLoading: document.getElementById('questionLoading'),
    questionError: document.getElementById('questionError'),
    errorTitle: document.getElementById('errorTitle'),
    errorText: document.getElementById('errorText'),
    retryBtn: document.getElementById('retryBtn'),
    errorChangeBtn: document.getElementById('errorChangeBtn'),
    questionBody: document.getElementById('questionBody'),
    questionText: document.getElementById('questionText'),
    optionsList: document.getElementById('optionsList'),
    hintList: document.getElementById('hintList'),
    feedback: document.getElementById('feedback'),
    feedbackTitle: document.getElementById('feedbackTitle'),
    feedbackText: document.getElementById('feedbackText'),
    feedbackSource: document.getElementById('feedbackSource'),
    hintBtn: document.getElementById('hintBtn'),
    submitBtn: document.getElementById('submitBtn'),
    nextBtn: document.getElementById('nextBtn'),
    changeBtn: document.getElementById('changeBtn'),
    toastStack: document.getElementById('toastStack')
};

const ERROR_TITLES = {
    no_materials: 'No materials yet',
    model_unavailable: 'Practice is resting',
    bad_output: 'Let us try that again',
    not_enrolled: 'Class not available'
};

// ── Session ────────────────────────────────────────────────
async function checkSession() {
    try {
        const response = await fetch('/auth/me');
        const data = response.ok ? await response.json() : null;
        if (!data || !data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        sessionStorage.setItem("user_id", data.user.user_id || data.user.id);
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
    wireEvents();
    await loadCourses();
})();

function wireEvents() {
    els.courseSelect.addEventListener('change', () => {
        els.startBtn.disabled = !els.courseSelect.value;
    });

    els.difficultyBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            els.difficultyBtns.forEach(b => {
                b.classList.toggle('active', b === btn);
                b.setAttribute('aria-checked', b === btn ? 'true' : 'false');
            });
            state.difficulty = btn.dataset.difficulty;
        });
    });

    els.startBtn.addEventListener('click', startPractice);
    els.submitBtn.addEventListener('click', checkAnswer);
    els.hintBtn.addEventListener('click', showHint);
    els.nextBtn.addEventListener('click', loadQuestion);
    els.retryBtn.addEventListener('click', loadQuestion);
    els.changeBtn.addEventListener('click', showSetup);
    els.errorChangeBtn.addEventListener('click', showSetup);
}

// ── Courses ────────────────────────────────────────────────
async function loadCourses() {
    const userId = sessionStorage.getItem("user_id");
    try {
        const response = await fetch(`/studentcourses/${encodeURIComponent(userId)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const courses = Array.isArray(data) ? data : [];

        if (courses.length === 0) {
            els.courseSelect.innerHTML = '<option value="">Join a class first</option>';
            return;
        }

        els.courseSelect.innerHTML = '<option value="">Select a class</option>';
        courses.forEach(course => {
            const meta = Array.isArray(course.courses) ? (course.courses[0] || {}) : (course.courses || {});
            const option = document.createElement('option');
            option.value = String(course.course_id);
            option.textContent = meta.code ? `${meta.name} (${meta.code})` : (meta.name || 'Class');
            els.courseSelect.appendChild(option);
        });

        // Preselect a class passed as ?course=<id>
        const preset = new URLSearchParams(window.location.search).get('course');
        if (preset && courses.some(c => String(c.course_id) === preset)) {
            els.courseSelect.value = preset;
        } else if (courses.length === 1) {
            els.courseSelect.value = String(courses[0].course_id);
        }
        els.startBtn.disabled = !els.courseSelect.value;
    } catch (error) {
        console.error('Error loading classes:', error);
        els.courseSelect.innerHTML = '<option value="">Could not load classes</option>';
        showToast('Error loading classes', 'error');
    }
}

// ── Flow ───────────────────────────────────────────────────
function startPractice() {
    if (!els.courseSelect.value) return;
    state.courseId = els.courseSelect.value;
    state.courseName = els.courseSelect.options[els.courseSelect.selectedIndex].textContent;
    state.progress = { answered: 0, correct: 0, streak: 0 };
    state.recentSeeds = [];

    els.setupCard.hidden = true;
    els.progressBar.hidden = false;
    els.questionCard.hidden = false;
    renderProgress();
    loadQuestion();
}

function showSetup() {
    els.questionCard.hidden = true;
    els.progressBar.hidden = true;
    els.setupCard.hidden = false;
}

async function loadQuestion() {
    showPanel('loading');
    state.token = null;
    state.selected = null;
    state.answered = false;
    state.hintLevel = 0;

    try {
        const response = await fetch('/api/practice/question', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                course_id: state.courseId,
                difficulty: state.difficulty,
                exclude: state.recentSeeds
            })
        });
        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        if (!response.ok || !data.success) {
            showError(data.code, data.error || 'Could not get a question. Please try again.');
            return;
        }

        state.token = data.token;
        state.hintCount = data.hint_count || 0;
        state.recentSeeds = [data.seed_id, ...state.recentSeeds].slice(0, 20);
        renderQuestion(data);
    } catch (error) {
        console.error('Question request failed:', error);
        showError(null, 'Could not reach the server. Please check your connection and try again.');
    }
}

function renderQuestion(data) {
    els.questionText.textContent = data.question;
    els.optionsList.innerHTML = '';
    els.hintList.innerHTML = '';
    els.feedback.hidden = true;
    els.feedback.className = 'practice-feedback';

    data.options.forEach((text, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'option-btn';
        btn.setAttribute('role', 'radio');
        btn.setAttribute('aria-checked', 'false');
        btn.dataset.index = String(index);

        const letter = document.createElement('span');
        letter.className = 'option-letter';
        letter.textContent = 'ABCD'[index];
        const label = document.createElement('span');
        label.className = 'option-text';
        label.textContent = text;
        btn.append(letter, label);

        btn.addEventListener('click', () => selectOption(index));
        els.optionsList.appendChild(btn);
    });

    els.submitBtn.hidden = false;
    els.submitBtn.disabled = true;
    els.hintBtn.hidden = false;
    els.hintBtn.disabled = state.hintCount === 0;
    els.hintBtn.textContent = 'Get a hint';
    els.nextBtn.hidden = true;
    els.changeBtn.hidden = true;
    showPanel('question');
}

function selectOption(index) {
    if (state.answered) return;
    state.selected = index;
    els.optionsList.querySelectorAll('.option-btn').forEach(btn => {
        const isSelected = Number(btn.dataset.index) === index;
        btn.classList.toggle('selected', isSelected);
        btn.setAttribute('aria-checked', isSelected ? 'true' : 'false');
    });
    els.submitBtn.disabled = false;
}

async function showHint() {
    if (!state.token || state.answered || state.hintLevel >= state.hintCount) return;
    els.hintBtn.disabled = true;

    try {
        const response = await fetch('/api/practice/hint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: state.token, level: state.hintLevel })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            showToast(data.error || 'Could not get a hint', 'error');
            els.hintBtn.disabled = false;
            return;
        }

        const item = document.createElement('div');
        item.className = 'hint-item';
        const label = document.createElement('span');
        label.className = 'hint-label';
        label.textContent = `Hint ${data.level + 1}`;
        const text = document.createElement('span');
        text.textContent = data.hint;
        item.append(label, text);
        els.hintList.appendChild(item);

        state.hintLevel = data.level + 1;
        els.hintBtn.disabled = !data.has_more;
        els.hintBtn.textContent = data.has_more ? 'Another hint' : 'No more hints';
    } catch (error) {
        console.error('Hint request failed:', error);
        showToast('Could not get a hint', 'error');
        els.hintBtn.disabled = false;
    }
}

async function checkAnswer() {
    if (state.selected === null || state.answered || !state.token) return;
    els.submitBtn.disabled = true;

    try {
        const response = await fetch('/api/practice/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: state.token, choice: state.selected })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            showToast(data.error || 'Could not check your answer', 'error');
            els.submitBtn.disabled = false;
            return;
        }

        state.answered = true;
        state.progress.answered += 1;
        if (data.correct) {
            state.progress.correct += 1;
            state.progress.streak += 1;
        } else {
            state.progress.streak = 0;
        }
        renderProgress();
        renderFeedback(data);
    } catch (error) {
        console.error('Check request failed:', error);
        showToast('Could not check your answer', 'error');
        els.submitBtn.disabled = false;
    }
}

function renderFeedback(data) {
    els.optionsList.querySelectorAll('.option-btn').forEach(btn => {
        const index = Number(btn.dataset.index);
        btn.disabled = true;
        if (index === data.correct_index) btn.classList.add('correct');
        else if (index === state.selected) btn.classList.add('wrong');
    });

    els.feedback.className = `practice-feedback ${data.correct ? 'is-correct' : 'is-wrong'}`;
    els.feedbackTitle.textContent = data.correct ? 'Great job! That is correct.' : 'Not quite. Here is the right answer.';
    els.feedbackText.textContent = data.explanation || '';

    const source = data.source || {};
    const parts = [];
    if (source.file_name) parts.push(source.file_name);
    if (source.page_number) parts.push(`page ${source.page_number}`);
    els.feedbackSource.textContent = parts.length ? `From: ${parts.join(', ')}` : '';
    els.feedback.hidden = false;

    els.submitBtn.hidden = true;
    els.hintBtn.hidden = true;
    els.nextBtn.hidden = false;
    els.changeBtn.hidden = false;
    els.nextBtn.focus();
}

// ── Rendering helpers ──────────────────────────────────────
function showPanel(name) {
    els.questionLoading.hidden = name !== 'loading';
    els.questionError.hidden = name !== 'error';
    els.questionBody.hidden = name !== 'question';
}

function showError(code, message) {
    els.errorTitle.textContent = ERROR_TITLES[code] || 'Something went wrong';
    els.errorText.textContent = message;
    els.retryBtn.hidden = code === 'no_materials' || code === 'not_enrolled';
    showPanel('error');
}

function renderProgress() {
    const p = state.progress;
    els.progAnswered.textContent = p.answered;
    els.progCorrect.textContent = p.correct;
    els.progStreak.textContent = p.streak;
    const level = state.difficulty.charAt(0).toUpperCase() + state.difficulty.slice(1);
    els.progMeta.textContent = `${state.courseName} · ${level}`;
}

// ── Toast ──────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `app-toast ${type}`;
    toast.setAttribute('role', 'status');
    const text = document.createElement('span');
    text.textContent = message;
    toast.appendChild(text);
    els.toastStack.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}
