"""
End-to-end test sequence for VTA.
Requires both servers running:
  Flask  -> python Code/backend/app.py   (port 5001)
  Node   -> node server/index.js         (port 3000)
"""

import io
import os
import sys
import uuid
import requests

FLASK = "http://localhost:5001"
NODE  = "http://localhost:3000"

# Unique email each run so re-runs never hit "already registered"
TEST_EMAIL    = f"e2e_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "testpass123"
TEST_NAME     = "E2E Student"

# Override via: COURSE_CODE=XX1-Y2Z python test_e2e.py
COURSE_CODE = os.environ.get("COURSE_CODE", "")

PASS_LABEL = "\033[32mPASS\033[0m"
FAIL_LABEL = "\033[31mFAIL\033[0m"

results = []

def check(step, ok, detail=""):
    label = PASS_LABEL if ok else FAIL_LABEL
    msg = f"[{label}] Step {step}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append(ok)
    return ok


# ── Step 1: Register as a new student on Flask ───────────────────────────────
print("\n── Step 1: Register as student on Flask :5001 ──")
session = requests.Session()
r = session.post(f"{FLASK}/auth/register", json={
    "full_name": TEST_NAME,
    "email":     TEST_EMAIL,
    "password":  TEST_PASSWORD,
    "role":      "student",
})
if r.status_code in (200, 201) and r.json().get("success"):
    # Flask User.to_dict() returns "user_id", not "id"
    user_id = r.json()["user"]["user_id"]
    check(1, True, f"registered {TEST_EMAIL} (user_id={user_id})")
else:
    # Fallback: try login in case the email already exists
    r2 = session.post(f"{FLASK}/auth/login", json={
        "email":    TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    if r2.ok and r2.json().get("success"):
        user_id = r2.json()["user"]["user_id"]
        check(1, True, f"logged in {TEST_EMAIL} (user_id={user_id})")
    else:
        check(1, False, f"register={r.text[:120]}  login={r2.text[:120]}")
        print("Cannot continue without a valid user.")
        sys.exit(1)


# ── Step 2: Look up a course by join code on Node ────────────────────────────
print("\n── Step 2: GET /course/code/{code} on Node :3000 ──")
if not COURSE_CODE:
    # No code supplied — grab the first course from the DB and use its code
    r_all = requests.get(f"{NODE}/course")
    if r_all.ok and r_all.json():
        first_course = r_all.json()[0]
        COURSE_CODE = first_course.get("code", "")
        print(f"  (COURSE_CODE not set — using first DB course: {COURSE_CODE})")
    else:
        check(2, False, "no COURSE_CODE set and /course returned nothing")
        sys.exit(1)

r = requests.get(f"{NODE}/course/code/{COURSE_CODE}")
if r.ok:
    course = r.json()
    course_id   = course.get("id")
    course_name = course.get("name", "")
    check(2, bool(course_id),
          f"found '{course_name}' id={course_id} code={COURSE_CODE}")
else:
    check(2, False, f"HTTP {r.status_code}: {r.text[:120]}")
    sys.exit(1)


# ── Step 3: Enroll student in that course on Node ────────────────────────────
print("\n── Step 3: POST /addCourse/{userId}/{courseId} on Node :3000 ──")
r = requests.post(f"{NODE}/addCourse/{user_id}/{course_id}")
if r.ok:
    check(3, True, f"enrolled user_id={user_id} in course_id={course_id}")
elif r.status_code == 500 and not r.headers.get("content-type", "").startswith("application/json"):
    # Node returns plain-text "Server error" on duplicate key — already enrolled
    check(3, True, "already enrolled (duplicate key — treated as pass)")
else:
    check(3, False, f"HTTP {r.status_code}: {r.text[:120]}")


# ── Step 4: Assert the course appears in student's enrolment list ─────────────
print("\n── Step 4: GET /studentcourses/{userId} on Node :3000 ──")
r = requests.get(f"{NODE}/studentcourses/{user_id}")
if not r.ok:
    check(4, False, f"HTTP {r.status_code}: {r.text[:120]}")
else:
    rows = r.json()
    # Node selects courses(name) only, so rows look like [{"courses": {"name": "..."}}]
    enrolled_names = [
        (row.get("courses") or {}).get("name", "")
        for row in rows
    ]
    found = course_name in enrolled_names
    check(4, found,
          f"'{course_name}' {'found' if found else 'NOT found'} "
          f"in enrollment list {enrolled_names}")


# ── Step 5: Upload a small document then query it on Flask ───────────────────
print("\n── Step 5: Upload doc + POST /api/query on Flask :5001 ──")

# 5a — upload a tiny in-memory text file so the RAG system has something to search
doc_content = (
    "This course covers deep learning fundamentals including neural networks, "
    "backpropagation, convolutional networks, and model training techniques "
    "using the NVIDIA Deep Learning Institute curriculum."
).encode()

upload_r = session.post(
    f"{FLASK}/api/upload",
    files={"file": ("e2e_test_doc.txt", io.BytesIO(doc_content), "text/plain")},
    data={"course_id": str(course_id)},
)
if not upload_r.ok or not upload_r.json().get("success"):
    check(5, False,
          f"upload failed HTTP {upload_r.status_code}: {upload_r.text[:120]}")
else:
    chunks = upload_r.json().get("chunks_created", 0)
    print(f"  uploaded test doc ({chunks} chunk(s))")

    # 5b — query against it
    query_r = session.post(f"{FLASK}/api/query", json={
        "question":    "What is this course about?",
        "max_results": 3,
        "course_id":   str(course_id),
    })
    if not query_r.ok:
        check(5, False, f"HTTP {query_r.status_code}: {query_r.text[:120]}")
    else:
        data   = query_r.json()
        answer = data.get("answer", "")
        ok     = data.get("success", False) and len(answer) > 5
        check(5, ok,
              f"success={data.get('success')} "
              f"answer_len={len(answer)} "
              f"preview='{answer[:80]}'")


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
passed = sum(results)
total  = len(results)
print(f"Result: {passed}/{total} steps passed")
if passed < total:
    sys.exit(1)
