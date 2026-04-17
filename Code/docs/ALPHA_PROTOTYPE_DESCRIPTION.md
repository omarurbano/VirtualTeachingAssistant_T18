# Alpha Prototype Implementation - TradeBuzz VTA

## Overview

The Virtual Teaching Assistant (VTA) alpha prototype establishes the core architecture for both student and instructor interfaces, with the backend API fully integrated with the Supabase database. The system demonstrates full CRUD operations for courses, enrollment management, and real-time learning analytics.

---

## 1. Backend API Server (server/index.js)

The Express.js server provides all core API endpoints on port 3000, connected to Supabase for data persistence.

**Authentication:**
- `POST /auth/register` - User registration with email, password hashing (SHA-256), and role assignment (student/instructor)
- Demo accounts: teacher@test.com, student@test.com (password: demo123)

**Course Management:**
- `GET /course` - Retrieves all courses with enrollment counts and material counts
- `POST /course` - Creates new courses with name, code, description
- `PUT /course/:id` - Updates course details
- `GET /course/:id` - Single course lookup
- `GET /course/code/:courseCode` - Course lookup by unique code

**Enrollment:**
- `POST /addCourse/:userId/:courseId` - Links student to course
- `GET /studentcourses/:userId` - Retrieves student's enrolled courses with course details

**Query Recording:**
- `POST /api/queries` - Records student questions with automatic topic extraction, confidence scores, and sources used
- Topics extracted from keywords: Backpropagation, Loss Functions, Neural Networks, CNNs, RNNs, Transformers, Optimization, Regularization

**Analytics Endpoints:**
- `GET /api/analytics/summary/:courseId` - Total queries, active students, average confidence score, 7-day engagement trend
- `GET /api/analytics/confusing-topics/:courseId` - Topics sorted by frequency with difficulty levels (HIGH >10, MEDIUM 5-10, LOW <5)
- `GET /api/analytics/at-risk/:courseId` - Students flagged when >30% of their queries have low confidence

**Course Materials & Google Drive:**
- `GET/POST /api/materials` - Course document management
- `POST/GET /api/drive` - Google Drive folder linking per course

**Status:** Fully operational and integrated with all frontend components.

---

## 2. Student Frontend (studentHome.html)

The student interface provides a streamlined course enrollment experience with WSU-themed styling.

**Header & Navigation:**
- Bootstrap 5 offcanvas sidebar listing enrolled courses
- Dynamic user welcome message showing student's name
- Logout button with session handling
- Hamburger menu toggle for course list

**Add Course Feature:**
- Modal dialog for entering course code
- Form validation with visual feedback
- Success/error toast notifications
- Card-based UI with stock book imagery

**Course Display:**
- Grid of enrolled courses with card interface
- Course name and code displayed
- Quick access to course content

**API Integration:**
- `GET /studentcourses/:userId` - Loads enrolled courses into sidebar
- `POST /addCourse/:userId/:courseId` - Enrolls student via course code lookup

**Progress:** ~90% complete. The AI-powered Q&A chat interface connecting to the query recording API remains for Phase 2.

---

## 3. Instructor Dashboard (dashboard.html)

The instructor dashboard features a terminal-inspired dark theme with cyan accents and JetBrains Mono font.

**Visual Design:**
- Command-line aesthetic with $ prompt styling
- Dark surface (#111) with cyan accent (#00bcd4)
- Sidebar with course list (ls ./courses style)
- Top bar showing welcome message and logout

**Course Grid:**
- Dynamic cards showing: course name, code, student count, material count
- Live/idle status indicators (● / ○)
- Quick action buttons: "Open Course" and "View Analytics"
- Cards load dynamically from API

**Create Course Modal:**
- Terminal-style form fields
- Auto-generates course code in format XX-X-XX (e.g., AB2-C3D)
- Step-by-step success output showing code generation
- Error handling for empty fields

**Sidebar Features:**
- Course list with active state management
- "create new course" button in footer
- Scrollable list for multiple courses

**API Integration:**
- `GET /api/courses` - Fetches all courses with stats
- `POST /api/courses` - Creates new course

**Progress:** ~95% complete - fully functional course management.

---

## 4. Instructor Analytics (analytics.html)

The analytics dashboard provides real-time learning insights through interactive visualizations powered by Chart.js.

**Overview Bar (Full Width):**
- Live display of: course code, student count, document count, query count, date range
- Dynamic updates from analytics API

**Section 2 - Confusion Heatmap:**
- Table showing topics students ask about most, sorted by frequency
- Difficulty badges: HIGH (red), MEDIUM (yellow), LOW (green)
- Horizontal bar chart visualizing topic distribution
- Click-to-filter: clicking a topic filters the query list

**Section 3 - Engagement Statistics:**
- 2x2 grid displaying: Total Queries, Active Students, Avg Session Length, Docs Uploaded
- Line chart showing weekly engagement trend (last 7 days)
- Real-time data from analytics summary endpoint

**Section 4 - Module Breakdown:**
- Table with columns: Module, Queries, Avg Difficulty, Most Confused Concept
- Doughnut chart showing query distribution by module
- Example: Neural Networks (120 queries, Backpropagation most confused)

**Section 5 - Query Explorer:**
- Scrollable list of recent queries with timestamps
- Expandable rows showing full question, AI response, and sources
- Filter by clicking topics in the heatmap
- Failed query handling with distinct styling

**Section 6 - At-Risk Detection:**
- Flagged students by type: STRUGGLING, REPEATED CONFUSION, LOW INTERACTION
- Anonymized IDs (e.g., STU_3A9F) for privacy
- Associated problematic topics for each student
- Based on >30% query failure rate or 14+ days without interaction

**Section 7 - Figure Confusion Report:**
- Bar visualizations of course figures causing most questions
- Percentage rates showing confusion frequency
- Example: Figure 3 (Backprop diagram) - 60% confusion rate

**API Integration:**
- `/api/analytics/summary/:courseId` - Main stats
- `/api/analytics/confusing-topics/:courseId` - Topic data
- `/api/analytics/at-risk/:courseId` - At-risk students
- `/api/queries/:courseId` - Query history (last 100)

**Charts Implemented:**
- Topic frequency horizontal bar chart
- Weekly engagement trend line chart
- Module distribution doughnut chart

**Progress:** ~90% complete - all visualizations functional with live data.

---

## 5. Database Schema (schema.sql)

Core Supabase tables:

| Table | Purpose |
|-------|---------|
| users | User accounts with email, password_hash, full_name, role |
| courses | Course info: name, code, description, teacher_id, is_active |
| enrollments | Student-course links with status and enrolled_at |
| queries | Student questions with topics, answer, confidence_score, sources |
| course_materials | Uploaded documents with course_id, file_name, chunks_count |
| google_drive_links | Drive folder connections per course |

All tables have proper foreign key relationships and timestamps.

---

## 6. System Integration

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Student   │────►│   Express API    │────►│   Supabase DB   │
│  Frontend   │     │   (port 3000)    │     │                 │
└─────────────┘     └────────┬─────────┘     └─────────────────┘
                             │
┌─────────────┐             │
│  Instructor │─────────────┘
│  Dashboard  │
└─────────────┘
                             │
┌─────────────┐             │
│  Analytics  │─────────────┘
│    Page     │
└─────────────┘
```

**Completed:**
- Authentication (register, login)
- Course CRUD operations
- Student enrollment
- Analytics APIs (summary, confusing topics, at-risk)
- Query recording and topic extraction
- Google Drive folder linking

**Pending (Phase 2):**
- AI/ML-powered Q&A chat interface
- Real-time WebSocket updates
- Predictive analytics model

---

## 7. Summary

| Component | Status | Completion |
|-----------|--------|------------|
| Backend API Server | Complete | 95% |
| Student Frontend | Complete | 90% |
| Instructor Dashboard | Complete | 95% |
| Analytics Dashboard | Complete | 90% |
| Database Schema | Complete | 100% |
| Google Drive Integration | Complete | 85% |
| AI/ML Chat Interface | Pending | 0% |

The alpha prototype demonstrates a fully functional system for course management, student enrollment, and real-time learning analytics. The instructor-facing components are production-ready with live data visualization, while the AI-powered Q&A chat interface connecting to the query recording endpoints remains the primary deliverable for Phase 2.