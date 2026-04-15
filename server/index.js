const express = require("express");
const cors = require("cors");
const supabase = require("./db");

const app = express();
app.use(cors());
app.use(express.json());

// Error handling
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// ============================================
// ALL EXISTING ROUTES
// ============================================

// AUTH - Register
app.post("/auth/register", async (req, res) => {
    const { email, password, full_name, role } = req.body;
    const crypto = require('crypto');
    const password_hash = crypto.createHash('sha256').update(password).digest('hex');
    
    const { data, error } = await supabase
        .from("users")
        .insert([{ email: email.toLowerCase(), password_hash, full_name, role: role || 'student' }])
        .select().single();
    
    if (error) return res.status(400).json({ error: error.message.includes('duplicate') ? 'Email already registered' : error.message });
    res.status(201).json(data);
});

// USERS
app.get("/users", async (req, res) => {
    const { data, error } = await supabase.from("users").select("*");
    if (error) return res.status(500).send("Server error");
    res.json(data);
});

app.get("/users/:id", async (req, res) => {
    const { id } = req.params;
    const { data, error } = await supabase.from("users").select("*").eq("id", id).single();
    if (error) return res.status(404).send("User not found");
    res.json(data);
});

// COURSES
app.get("/course", async (req, res) => {
    const { data, error } = await supabase.from("courses").select("*");
    if (error) return res.status(500).send("Server error");
    res.json(data);
});

app.get("/course/:id", async (req, res) => {
    const { id } = req.params;
    const { data, error } = await supabase.from("courses").select("*").eq("id", id).single();
    if (error) return res.status(404).send("Course not found");
    res.json(data);
});

app.get("/course/code/:courseCode", async (req, res) => {
    const { courseCode } = req.params;
    const { data, error } = await supabase.from("courses").select("*").eq("code", courseCode).single();
    if (error) return res.status(404).send("Course not found");
    res.json(data);
});

// ENROLLMENTS
app.post("/addCourse/:userId/:courseId", async (req, res) => {
    const { userId, courseId } = req.params;
    const { data, error } = await supabase.from("enrollments").insert([{ student_id: userId, course_id: courseId }]).select().single();
    if (error) return res.status(500).send("Server error");
    res.json(data);
});

app.get("/studentcourses/:userId", async (req, res) => {
    const { userId } = req.params;
    const { data, error } = await supabase.from("enrollments").select("courses(name)").eq("student_id", userId);
    if (error) return res.status(404).send("Courses not found");
    res.json(data);
});

// QUERIES - Record student questions
app.post("/api/queries", async (req, res) => {
    const { course_id, student_id, question, answer, sources_used, confidence_score } = req.body;
    const topics = extractTopics(question);
    const { data, error } = await supabase.from("queries").insert([{ course_id, student_id, question, answer, sources_used: sources_used || [], confidence_score: confidence_score || 0, topics }]).select().single();
    if (error) return res.status(500).json({ error: error.message });
    res.status(201).json(data);
});

// ============================================
// LIVE ANALYTICS ENDPOINTS
// ============================================

// Get all queries for a course
app.get("/api/queries/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("queries").select("*").eq("course_id", courseId).order("created_at", { ascending: false }).limit(100);
    if (error) return res.status(500).json({ error: error.message });
    res.json(data);
});

// Analytics summary - live stats
app.get("/api/analytics/summary/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("queries").select("student_id, confidence_score, created_at").eq("course_id", courseId);
    if (error) return res.status(500).json({ error: error.message });
    
    const uniqueStudents = [...new Set(data.map(q => q.student_id))];
    const avgConfidence = data.reduce((sum, q) => sum + (q.confidence_score || 0), 0) / (data.length || 1);
    
    // Engagement trend (last 7 days)
    const trend = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        const dateStr = date.toISOString().split('T')[0];
        const count = data.filter(q => q.created_at && q.created_at.startsWith(dateStr)).length;
        trend.push({ date: dateStr, count });
    }
    
    res.json({ total_queries: data.length, active_students: uniqueStudents.length, avg_confidence: Math.round(avgConfidence * 100) / 100, engagement_trend: trend });
});

// Confusing topics - what students struggle with
app.get("/api/analytics/confusing-topics/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("queries").select("topics").eq("course_id", courseId);
    if (error) return res.status(500).json({ error: error.message });
    
    const topicCounts = {};
    for (const q of data.slice(-50)) {
        if (q.topics) { for (const topic of q.topics) { topicCounts[topic] = (topicCounts[topic] || 0) + 1; } }
    }
    const sorted = Object.entries(topicCounts).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([topic, count]) => ({ topic, count, difficulty: count > 10 ? 'HIGH' : count > 5 ? 'MEDIUM' : 'LOW' }));
    res.json(sorted);
});

// At-risk students
app.get("/api/analytics/at-risk/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("queries").select("student_id, confidence_score").eq("course_id", courseId);
    if (error) return res.status(500).json({ error: error.message });
    
    const studentStats = {};
    for (const q of data) {
        if (!studentStats[q.student_id]) studentStats[q.student_id] = { queries: 0, failed: 0 };
        studentStats[q.student_id].queries++;
        if (q.confidence_score < 0.5) studentStats[q.student_id].failed++;
    }
    const atRisk = Object.entries(studentStats).filter(([_, s]) => s.failed / s.queries > 0.3).map(([student_id, stats]) => ({ student_id, total_queries: stats.queries, failed_queries: stats.failed, reason: stats.failed / stats.queries > 0.5 ? 'STRUGGLING' : 'NEEDS_HELP' }));
    res.json(atRisk);
});

// Course materials
app.get("/api/materials/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("course_materials").select("*").eq("course_id", courseId);
    if (error) return res.status(500).json({ error: error.message });
    res.json(data);
});

app.post("/api/materials", async (req, res) => {
    const { course_id, source_type, file_name, chunks_count, file_id } = req.body;
    const { data, error } = await supabase.from("course_materials").insert([{ course_id, source_type, file_name, chunks_count, file_id }]).select().single();
    if (error) return res.status(500).json({ error: error.message });
    res.json(data);
});

// Google Drive
app.post("/api/drive/connect", async (req, res) => {
    const { course_id, teacher_id, folder_url, access_token, refresh_token } = req.body;
    const { data: existing } = await supabase.from("google_drive_links").select("*").eq("course_id", course_id).single();
    let result, error;
    if (existing) {
        ({ data: result, error } = await supabase.from("google_drive_links").update({ folder_url, access_token, refresh_token, connected_at: new Date().toISOString() }).eq("course_id", course_id).select().single());
    } else {
        ({ data: result, error } = await supabase.from("google_drive_links").insert([{ course_id, teacher_id, folder_url, access_token, refresh_token }]).select().single());
    }
    if (error) return res.status(500).json({ error: error.message });
    res.json(result);
});

app.get("/api/drive/:courseId", async (req, res) => {
    const { courseId } = req.params;
    const { data, error } = await supabase.from("google_drive_links").select("*").eq("course_id", courseId).single();
    if (error) return res.status(500).json({ error: error.message });
    res.json(data || null);
});

// ============================================
// HELPER FUNCTIONS
// ============================================

function extractTopics(question) {
    const q = question.toLowerCase();
    const topics = [];
    const topicKeywords = { 'Backpropagation': ['backprop', 'gradient', 'chain rule'], 'Loss Functions': ['loss', 'cost', 'mse', 'cross entropy'], 'Neural Networks': ['neural', 'network', 'neuron'], 'CNNs': ['cnn', 'convolutional', 'filter'], 'RNNs': ['rnn', 'recurrent', 'lstm'], 'Transformers': ['transformer', 'attention', 'bert'], 'Optimization': ['optimizer', 'adam', 'learning rate'], 'Regularization': ['dropout', 'l1', 'l2', 'overfit'] };
    for (const [topic, keywords] of Object.entries(topicKeywords)) { if (keywords.some(k => q.includes(k))) topics.push(topic); }
    return topics.length ? topics : ['General'];
}

// ============================================
// START SERVER
// ============================================

// Update test users
async function seedUsers() {
    const crypto = require('crypto');
    const password_hash = crypto.createHash('sha256').update('demo123').digest('hex');
    await supabase.from('users').update({ password_hash }).eq('email', 'teacher@test.com');
    await supabase.from('users').update({ password_hash }).eq('email', 'student@test.com');
    console.log('Updated password hashes');
}

seedUsers().then(() => {
    const PORT = 3000;
    const server = app.listen(PORT, () => {
        console.log(`Server running on http://localhost:${PORT}`);
    });

    process.on('SIGINT', () => { console.log('\nShutting down...'); server.close(() => { console.log('Server closed'); process.exit(0); }); });
    process.on('SIGTERM', () => { server.close(() => { process.exit(0); }); });
});