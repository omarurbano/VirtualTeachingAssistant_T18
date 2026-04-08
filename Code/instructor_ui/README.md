# VTA Instructor UI — Mock

A frontend-only mock of the instructor interface for the **Virtual Teaching Assistant (VTA)** platform. Built with Flask (template serving only), vanilla HTML/CSS/JS, and Bootstrap. No database, no authentication, no backend logic — all data is hardcoded.

---

## Requirements

- Python 3.8 or higher
- That's it.

---

## Setup

```bash
# 1. Unzip and enter the project folder
unzip "Instuctor UI Mock.zip"
cd "Instuctor UI Mock"

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate it
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app
python3 app.py
```

Open your browser to **http://127.0.0.1:5000/instructor/dashboard**

---

## Demo Flow

The mock covers three pages with six interactive areas:

1. **Dashboard** (`/instructor/dashboard`) — course card grid with sidebar navigation. Click **$ create new course** to open the modal, fill in a course name and subject tag, and a class code is generated on submit.

2. **Course — Materials tab** (`/instructor/course/<course_id>`) — browse the uploaded materials list. Use the upload panel at the bottom to simulate adding a file (select a file + type, click **$ upload & embed**), or paste a Google Drive URL and click **$ link drive folder**.

3. **Course — Students tab** — view the anonymized roster. Click **$ export list** to download a `.csv`.

4. **Course — Settings tab** — edit the course name, regenerate the class code, or toggle the archive switch.

5. **Analytics — Overview + Heatmap** (`/instructor/analytics/<course_id>`) — review the status bar and confusion heatmap. Click any topic row to filter the Query Explorer to that topic; click again or hit **$ clear filter** to reset.

6. **Analytics — Query Explorer + At-Risk** — expand any query row to see the full response and source citation. Rows marked `[FAILED]` indicate queries the system could not answer.

---

## Notes

- **All data is hardcoded.** No database or API calls are made anywhere.
- Changing a course name, regenerating a code, or archiving a course updates the UI only — nothing is persisted between page loads.
- The app runs with `debug=True`. Do not deploy this to production.

---

## Project Structure

```
.
├── app.py                          # Flask routes (dashboard, course, analytics)
├── requirements.txt
├── static/
│   └── css/
│       └── instructor.css          # All styles — terminal aesthetic, shared tokens
└── templates/
    └── instructor/
        ├── dashboard.html          # Course grid + create-course modal
        ├── course.html             # Materials / Students / Settings tabs
        └── analytics.html          # Full analytics dashboard with Chart.js
```
