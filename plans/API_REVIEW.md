# CPT_S 421 VTA - Complete API & Implementation Review

**Review Date:** April 10, 2026  
**Reviewer:** Code Review  
**Scope:** Full Stack - Frontend & Backend  
**Status:** BRUTALLY HONEST ASSESSMENT

---

## EXECUTIVE SUMMARY

**CRITICAL FINDING:** Your application has TWO backends:

1. **Python Flask Backend** (Code/backend/app.py) - Runs on port 5000 - Has COMPLETE implementation
2. **Node.js Backend** (server/index.js) - Runs on port 3000 - Has basic Supabase user/course endpoints

**THE PROBLEM:** The studentHome.js is calling port 3000 (Node.js) for EVERYTHING, but it should be calling port 5000 for proper auth. The instructor pages call almost NO API endpoints at all.

**Summary:**
- Main VTA chat features (upload/query) ARE implemented in Flask (port 5000) ✓
- Registration IS implemented in both ✓
- Login IS implemented in Flask ✓
- Auth/logout IS implemented in Flask ✓
- BUT studentHome.js uses wrong port and has hardcoded user_id=1 ❌
- Instructor pages have almost NO API integration - buttons don't work ❌

---

## PART 1: ARCHITECTURE ANALYSIS

### THE ARCHITECTURAL PROBLEM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    YOUR DUAL-BACKEND ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│   BACKEND 1: Node.js (server/index.js) - Port 3000              │
│   ├── /auth/register         ✓ WORKS                            │
│   ├── /users                ✓ WORKS                              │
│   ├── /users/:id            ✓ WORKS                             │
│   ├── /course               ✓ WORKS                              │
│   ├── /course/:id          ✓ WORKS                              │
│   ├── /course/code/:code   ✓ WORKS                              │
│   ├── /addCourse/:uid/:cid ✓ WORKS                             │
│   └── /studentcourses/:uid ✓ WORKS                             │
│                                                                          │
│   BACKEND 2: Python Flask (Code/backend/app.py) - Port 5000     │
│   ├── /login               ✓ WORKS (HTML page)                 │
│   ├── /auth/register      ✓ WORKS (API)                         │
│   ├── /auth/login         ✓ WORKS (API)                          │
│   ├── /auth/me            ✓ WORKS (API)                         │
│   ├── /auth/logout        ✓ WORKS (API)                         │
│   ├── /student/home      ✓ WORKS (HTML page)                    │
│   ├── /instructor/dashboard ✓ WORKS (HTML page)             │
│   ├── /instructor/course/:id ✓ WORKS (HTML page)                │
│   ├── /instructor/analytics/:id ✓ WORKS (HTML page)             │
│   ├── /api/health         ✓ IMPLEMENTED                         │
│   ├── /api/upload        ✓ IMPLEMENTED                          │
│   ├── /api/upload/image  ✓ IMPLEMENTED                          │
│   ├── /api/files         ✓ IMPLEMENTED                          │
│   ├── /api/images        ✓ IMPLEMENTED                          │
│   ├── /api/clear         ✓ IMPLEMENTED                          │
│   └── /api/query         ✓ IMPLEMENTED ◄── MAIN FEATURE       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## PART 2: FRONTEND/API MISMATCH ANALYSIS

### A. Login Page (login.html) - WORKS WITH FLASK

**VERDICT:** Login page works correctly when Flask backend (port 5000) is running.

- POST /auth/login → Returns session cookie ✓
- POST /auth/register → Returns user object ✓
- GET /auth/me → Returns user info ✓
- POST /auth/logout → Clears session ✓

---

### B. Main VTA Page (index.html + script.js) - WORKS WITH FLASK

**VERDICT:** Main VTA features ARE implemented in Flask backend!

- GET /api/health → Returns system status ✓
- POST /api/upload → Uploads and embeds document ✓
- POST /api/upload/image → Analyzes image with vision ✓
- GET /api/files → Returns stored files ✓
- DELETE /api/images/:id → Deletes image ✓
- POST /api/clear → Clears all documents ✓
- POST /api/query → Main Q&A RAG response ✓

---

### C. Student Home Page (studentHome.js) - CALLING WRONG SERVER

**CRITICAL ISSUES FOUND:**

1. **Hardcoded user_id = 1** (Line 3 in studentHome.js):
   ```javascript
   sessionStorage.setItem("user_id", 1)  // SECURITY HOLE!
   ```
   Anyone can pretend to be user ID 1.

2. **Wrong port for user API** (Lines 22, 44, 54, 89):
   ```javascript
   fetch(`http://localhost:3000/users/${userId}`)  // Node.js backend
   ```
   But Flask also has /users endpoint. Which one is correct?

3. **Port mismatch for logout** (Line 109):
   ```javascript
   fetch('/auth/logout', { method: 'POST' })  // Expected on Flask (port 5000)
   ```
   This will work IF the Flask server is running.

**Current behavior:**
- GET /studentcourses/1 → 200 from Node.js ✓
- GET /course/code/:code → 200 from Node.js ✓
- POST /addCourse/:id/:id → 200 from Node.js ✓
- logout → Should work on Flask ✓

---

### D. Instructor Dashboard (instructor/dashboard.html) - NO BACKEND FOR COURSES

**CRITICAL:** Dashboard has NO backend integration!

**DISCONNECTED BUTTONS:**

| Button | What's Supposed to Happen | What Actually Happens |
|--------|----------------------|---------------------|
| `create new course` | Should POST to Flask /course | **TOTALLY CLIENT-SIDE** - Just shows a modal, then generates a code locally in JavaScript |

```javascript
// Lines 284-289 - Creates code locally, NEVER SAVES IT
function generateClassCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const seg = (n) => Array.from(...).join('');
    return `${seg(2)}...`;  // Generated in browser only!
}
```

The modal shows "Success" message but doesn't actually call any API to create the course.

---

### E. Instructor Course Page (instructor/course.html) - NO BACKEND

**CRITICAL:** Materials upload button has NO API integration!

**DISCONNECTED BUTTONS:**

| Button | Expected Action | What Actually Happens |
|--------|---------------|---------------------|
| `upload & embed` | POST /api/upload | **ONLY SHOWS MESSAGE** - No fetch call at all |
| `$ link drive folder` | OAuth flow | Just shows error message |
| `$ save` (course name) | PUT /api/course/:id | Just shows message |
| `$ regenerate code` | POST /api/course/:id/code | Just shows message |
| Archive toggle | PATCH /api/course/:id | Just shows message |

```javascript
// Lines 389-403 - Just shows a message, NO ACTUAL UPLOAD
document.getElementById('uploadBtn').addEventListener('click', () => {
    if (!file || !type) {
        showFeedback(fb, '> ERROR: select file and type', 'error');
        return;
    }
    // NO fetch() call - just shows fake success!
    showFeedback(fb, `> Queued "${file.name}" for embedding... OK`, 'success');
});
```

The materials table is also ALL HARDCODED in HTML (lines 61-129).

---

### F. Instructor Analytics Page (instructor/analytics.html) - NO BACKEND AT ALL

**CRITICAL:** EVERYTHING IS HARDCODED - NO API calls to fetch analytics.

```javascript
// Lines 519-532 - ALL FAKE DATA
const QUERIES = [
    { topic:'Backpropagation', time:'2025-04-06 15:41', student:'STU_7F2A', ...},
    { topic:'Loss Functions', time:'2025-04-06 15:29', ...},
    // ... 30+ fake query entries
];
```

The heatmap, engagement stats, at-risk students, and all charts use hardcoded fake data.

---

## PART 3: SUMMARY - WHAT WORKS vs WHAT'S BROKEN

### WORKS (Backend implemented properly)

| Feature | Backend | Status |
|---------|---------|--------|
| User Registration | Flask | ✓ WORKS |
| User Login | Flask | ✓ WORKS |
| Session Check | Flask | ✓ WORKS |
| Logout | Flask | ✓ WORKS |
| VTA Document Upload | Flask | ✓ WORKS |
| VTA Image Analysis | Flask | ✓ WORKS |
| VTA Query/Ask | Flask | ✓ WORKS |
| Student Course Enrollment | Node.js | ✓ WORKS |

### PARTIALLY WORKS

| Feature | Backend | Status | Issue |
|---------|---------|--------|-------|
| Student Home | Flask + Node.js | Mixed | Wrong port calls, hardcoded user_id=1 |
| Course lookup | Node.js | Works | Should be using Flask |

### DOESN'T WORK (No backend integration)

| Feature | Expected Backend | Status |
|---------|-----------------|--------|
| Instructor Create Course | Flask /course POST | **NOT CONNECTED** - Button doesn't call API |
| Instructor Upload Materials | Flask /api/upload | **NOT CONNECTED** - Button doesn't call API |
| Instructor Course Settings | Flask /course/:id PUT | **NOT CONNECTED** - Button doesn't call API |
| Instructor Analytics | Flask /analytics/* | **TOTALLY HARDCODED** - No API calls |

---

## PART 4: DISCONNECTED BUTTONS CHART

### Teacher (Instructor)

| Button/Interaction | Calls API? | Status |
|--------------------|-----------|--------|
| `$ sign in` (login) | Yes - Flask /auth/login | ✓ SHOULD WORK |
| `$ logout` (any page) | Yes - Flask /auth/logout | ✓ SHOULD WORK |
| `$ create new course` | **NO** - Pure client-side | ❌ BROKEN |
| `$ open course` | N/A - Navigation only | ✓ OK |
| `$ view analytics` | N/A - Navigation only | ✓ OK |
| `upload & embed` | **NO** - Just shows message | ❌ BROKEN |
| `$ link drive folder` | **NO** - Just shows message | ❌ BROKEN |
| Export list button | N/A - Client-side CSV | ✓ Works (fake data) |
| `$ save` (course name) | **NO** - Just shows message | ❌ BROKEN |
| `$ regenerate code` | **NO** - Just shows message | ❌ BROKEN |
| Archive toggle | **NO** - Just shows message | ❌ BROKEN |

### Student

| Button/Interaction | Status | Issue |
|-------------------|--------|-------|
| Sign In | ✓ Should work (Flask) | - |
| Sign Out/Logout | ✓ Should work (Flask) | - |
| Click course in sidebar | ⚠️ Goes to VTA but no course context passed | |
| Add Course | ✓ Works (Node.js) | Should use Flask |

### Main VTA Chat

| Button/Interaction | Status |
|-------------------|--------|
| upload button | ✓ Should work (Flask) |
| image button | ✓ Should work (Flask) |
| clear documents | ✓ Should work (Flask) |
| Enter + query | ✓ Should work (Flask) |

---

## PART 5: SECURITY ISSUES

1. **Hardcoded user_id = 1 in studentHome.js**
   - Any student can access any other student's data
   - Should use session token from Flask login

2. **Dual-backend confusion**
   - Unclear which backend manages what
   - Node.js has course/enrollment
   - Flask has auth/VTA
   - Need proper session management between both

3. **Instructor has no authentication check**
   - Anyone can access instructor dashboard
   - Should add @login_required decorator for Flask routes

---

## FINAL VERDICT

| Category | Status |
|----------|--------|
| Login/Auth (Flask) | ✓ WORKS |
| VTA Upload/Query (Flask) | ✓ WORKS |
| Student Course Functions (Node.js) | ✓ WORKS |
| Instructor Course Creation | ❌ BROKEN - No API call |
| Instructor Materials Upload | ❌ BROKEN - No API call |
| Instructor Analytics | ❌ BROKEN - All hardcoded |

**What works:** The core VTA features (document upload, image analysis, asking questions) ARE implemented in Flask. The login system IS implemented.

**What doesn't work:** The instructor-facing features have almost NO backend integration. The "create course" button just creates a code locally and never saves it. The "upload materials" button just shows a fake success message. Analytics is 100% hardcoded fake data.

**The backend DOES exist and works - the frontend just doesn't call it for instructor features.**