# Route Connectivity Analysis

**Date:** April 9, 2026  
**Analyzed by:** OpenCode Assistant

---

## Executive Summary

This document analyzes the connectivity between frontend routes, backend API endpoints, and identifies gaps in the authentication and role-based routing system. The application has a Flask-based RAG backend, an HTML/JavaScript frontend, and a Node.js/PostgreSQL server that are **NOT currently connected**.

---

## How to Run the Application

### Starting the Flask Backend

```bash
cd Code/backend
pip install -r requirements.txt
python app.py
```

- Application runs at: **http://localhost:5000**
- Login page: **http://localhost:5000/login**
- Main RAG page: **http://localhost:5000/**

### Starting the Node.js Server (Separate - Not Integrated)

```bash
cd server
node index.js
```

- Runs at: **http://localhost:5433** (PostgreSQL port used)
- Note: This server exists but is NOT connected to the Flask backend

---

## Current Route Map

### Existing Flask Routes (backend/app.py)

| Route | Method | Status | Description |
|-------|--------|--------|------------|
| `/login` | GET | ✅ Implemented | Renders login.html template |
| `/` | GET | ✅ Implemented | Renders main RAG page (index.html) |
| `/api/health` | GET | ✅ Implemented | Health check endpoint |
| `/api/initialize` | POST | ✅ Implemented | Initialize RAG application |
| `/api/upload` | POST | ✅ Implemented | Upload document files |
| `/api/upload/image` | POST | ✅ Implemented | Upload image files |
| `/api/query` | POST | ✅ Implemented | Query the RAG system |
| `/api/files` | GET | ✅ Implemented | List uploaded files |
| `/api/clear` | POST | ✅ Implemented | Clear all uploaded files |
| `/api/images` | GET | ✅ Implemented | List extracted images |
| `/api/images/<file_id>` | DELETE | ✅ Implemented | Delete extracted image |
| `/auth/login` | POST | ❌ **MISSING** | Login endpoint |
| `/auth/register` | POST | ❌ **MISSING** | Register new user |
| `/auth/me` | GET | ❌ **MISSING** | Get current user session |
| `/instructor/dashboard` | GET | ❌ Not Connected | Instructor dashboard |
| `/instructor/course/<course_id>` | GET | ❌ Not Connected | Instructor course view |
| `/instructor/analytics/<course_id>` | GET | ❌ Not Connected | Instructor analytics |
| `/student/home` | GET | ❌ **MISSING** | Student home page |

### Frontend Templates

| File | Status | Notes |
|------|--------|-------|
| `templates/login.html` | ✅ Implemented | Full login/register UI with role selection |
| `templates/index.html` | ✅ Implemented | Main RAG chat interface |
| `instructor/templates/instructor/dashboard.html` | ⚠️ Disconnected | Separate Flask app but not integrated |
| `instructor/templates/instructor/course.html` | ⚠️ Disconnected | Separate Flask app but not integrated |
| `instructor/templates/instructor/analytics.html` | ⚠️ Disconnected | Separate Flask app but not integrated |
| `templates/studentHome.html` | ⚠️ Exists | Not routed from any endpoint |

### Required But Missing Endpoints

| Endpoint | Purpose | Priority |
|---------|--------|---------|
| `POST /auth/login` | Authenticate user, return role | **HIGH** |
| `POST /auth/register` | Create new user account | **HIGH** |
| `GET /auth/me` | Get current user info | **HIGH** |
| `POST /auth/logout` | Logout user | **MEDIUM** |
| `GET /student/home` | Student dashboard | **HIGH** |
| `/api/user/courses` | Get user enrolled courses | **MEDIUM** |

---

## Authentication Flow Analysis

### Current State (login.html)

The `login.html` frontend expects the following API endpoints:

1. **Sign In Flow**
   - Calls: `POST /auth/login`
   - Expects: `{ email, password }` → `{ user: { user_id, email, role, full_name }, token? }`
   - On success: Redirect to `/` (main page)

2. **Sign Up Flow**
   - Calls: `POST /auth/register`
   - Expects: `{ full_name, email, password, role }`
   - On success: Redirect to `/` (main page)

3. **Session Check**
   - Calls: `GET /auth/me`
   - On auth: Redirect to `/`

### Problems Identified

| Issue | Impact | Severity |
|-------|--------|----------|
| `/auth/login` endpoint not implemented | Cannot log in at all | **CRITICAL** |
| `/auth/register` endpoint not implemented | Cannot create accounts | **CRITICAL** |
| No password hashing | Security vulnerability | **HIGH** |
| No session management | Cannot maintain login state | **HIGH** |
| No database integration for users | Where are credentials stored? | **HIGH** |

---

## Role-Based Routing Analysis

### Current期望 Flow

```
User logs in with credentials
       ↓
Backend validates username/password
       ↓
Check user role (teacher/student)
       ↓
    ┌──────────────┐
    ↓            ↓
Teacher     Student
    ↓            ↓
/instructor  /student/home
dashboard   (or /)
```

### Problems

| Issue | Current State | Required |
|-------|-------------|----------|
| No role returned from login | N/A | Need `/auth/login` to return role |
| No routing logic after login | Hardcoded to `/` | Need role-based redirect |
| Instructor UI separate | Not connected | Integrate into main app |
| Student UI | Uses same `/` | May need dedicated student view |

---

## Database Integration

### Node.js Server (PostgreSQL)

**Location:** `server/index.js`  
**Port:** 5433 (PostgreSQL connection)  
**Database:** `vta26`

**Existing Tables:**
- `users` - User accounts
- `course` - Course information
- `user_courses` - Enrollment mapping

**Current Endpoints:**
- `GET /users` - All users
- `GET /users/:id` - Get user by ID
- `GET /course` - All courses
- `GET /course/:id` - Course by ID
- `GET /course/code/:courseCode` - Course by code
- `GET /studentcourses/:userId` - Student's enrolled courses
- `POST /addCourse/:userId/:courseId` - Enroll in course

### Issues

| Issue | Description |
|-------|-----------|
| Not connected to Flask | Express server runs on 5433, Flask on 5000 |
| No API calls from Flask | No `fetch()` to Node.js server |
| No user table integration | Flask cannot query users |

---

## Missing Features Summary

### High Priority (Blocking Login)

1. **Implement Authentication Endpoints**
   - `POST /auth/login` - Verify credentials, return user + role
   - `POST /auth/register` - Create new user in database
   - `GET /auth/me` - Get current session
   - `POST /auth/logout` - Clear session

2. **Database Integration**
   - Connect Flask to PostgreSQL user table
   - Or implement user storage in Flask

3. **Role-Based Routing After Login**
   - Teachers → `/instructor/dashboard`
   - Students → `/student/home` or `/`

### Medium Priority (Enhancement)

4. **Instructor UI Integration**
   - Connect to main authentication system
   - Use same user session

5. **Student Dashboard**
   - Implement `/student/home` route
   - Show enrolled courses

6. **Session Management**
   - JWT tokens or session cookies
   - Persistent login state

---

## Recommendations

### Quick Fix Path

1. **Option A: Add Flask Authentication** (Recommended for quick start)
   - Implement `/auth/*` endpoints in Flask
   - Use SQLite or existing PostgreSQL
   - Add role-based redirect in frontend

2. **Option B: Use Node.js Auth** (Better for production)
   - Move all auth to Express server
   - Add JWT authentication
   - Connect Flask to Express for user data

### Minimum Viable Implementation

To make login work, at minimum implement:

1. ✅ Keep existing login.html frontend
2. ✅ Add `POST /auth/login` in Flask that:
   - Accepts `{ email, password }`
   - Returns `{ user: { role, full_name } }`
   - If role = teacher → redirect to instructor dashboard
   - If role = student → redirect to main app

3. ✅ Store users somewhere:
   - Use existing PostgreSQL (best), or
   - Use simple JSON file for testing

---

## Files That Need Changes

| File | Changes Needed |
|------|--------------|
| `app.py` | Add `/auth/*` routes, user database |
| `login.html` | May need minor updates |
| `index.html` | Add role check after login |
| `instructor/app.py` | Integrate auth or share session |
| Create `student_routes.py` | New student dashboard |

---

## Conclusion

The application has a polished frontend for login/signup but **no backend authentication system**. To make login work:

1. **Immediate:** Add `/auth/login`, `/auth/register`, `/auth/me` endpoints to Flask
2. **Database:** Connect user storage (PostgreSQL or Flask-based)
3. **Routing:** Implement role-based redirect after login
4. **Integration:** Connect instructor and student UIs to auth system

The Node.js server and instructor Flask app exist but are completely disconnected from the main authentication flow.