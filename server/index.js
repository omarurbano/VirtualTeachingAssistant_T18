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
    const { data: courses, error } = await supabase.from("courses").select("*");
    if (error) return res.status(500).send("Server error");
    
    // Get enrollment counts and material counts for each course
    const { data: enrollments } = await supabase.from("enrollments").select("course_id, student_id");
    const { data: materials } = await supabase.from("course_materials").select("course_id");
    
    const enrollmentCounts = {};
    const materialCounts = {};
    
    enrollments.forEach(e => {
        enrollmentCounts[e.course_id] = (enrollmentCounts[e.course_id] || 0) + 1;
    });
    
    materials.forEach(m => {
        materialCounts[m.course_id] = (materialCounts[m.course_id] || 0) + 1;
    });
    
    const coursesWithCounts = courses.map(c => ({
        ...c,
        students_count: enrollmentCounts[c.id] || 0,
        materials_count: materialCounts[c.id] || 0
    }));
    
    res.json(coursesWithCounts);
});

// Create new course (for instructor dashboard)
app.post("/course", async (req, res) => {
    const { name, code, description, teacher_id } = req.body;
    const { data, error } = await supabase
        .from("courses")
        .insert([{ 
            name, 
            code, 
            description: description || '', 
            teacher_id: teacher_id || 1,
            is_active: true 
        }])
        .select()
        .single();
    
    if (error) return res.status(500).json({ error: error.message });
    res.status(201).json(data);
});

// Update course
app.put("/course/:id", async (req, res) => {
    const { id } = req.params;
    const { name, code, description, is_active } = req.body;
    
    const updates = {};
    if (name !== undefined) updates.name = name;
    if (code !== undefined) updates.code = code;
    if (description !== undefined) updates.description = description;
    if (is_active !== undefined) updates.is_active = is_active;
    updates.updated_at = new Date().toISOString();
    
    const { data, error } = await supabase
        .from("courses")
        .update(updates)
        .eq("id", id)
        .select()
        .single();
    
    if (error) return res.status(500).json({ error: error.message });
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
    console.log('Adding enrollment:', userId, courseId);
    
    const { data, error } = await supabase.from("enrollments").insert([{ 
        student_id: parseInt(userId), 
        course_id: parseInt(courseId),
        status: 'active'
    }]).select().single();
    
    if (error) {
        console.error('Enrollment error details:', JSON.stringify(error));
        return res.status(500).json({ error: error.message, details: error });
    }
    res.json(data);
});

app.get("/studentcourses/:userId", async (req, res) => {
    const { userId } = req.params;
    const { data, error } = await supabase
        .from("enrollments")
        .select(`
            course_id,
            status,
            enrolled_at,
            courses (name, code)
        `)
        .eq("student_id", parseInt(userId))
        .eq("status", "active");
    
    if (error) {
        console.error('Get student courses error:', error);
        return res.status(404).json({ error: error.message });
    }
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

// Get students enrolled in a course
app.get("/api/courses/:courseId/students", async (req, res) => {
    console.log('Students API endpoint hit for courseId:', req.params.courseId);
    const courseId = req.params.courseId;
    
    // Get enrollments with user details
    const { data: enrollments, error } = await supabase
        .from("enrollments")
        .select("student_id, enrolled_at, status")
        .eq("course_id", courseId)
        .eq("status", "active");
    
    if (error) {
        console.error('Error fetching students:', error);
        return res.status(500).json({ error: error.message });
    }
    
    // Get user details for each student
    const studentIds = enrollments.map(e => e.student_id);
    if (studentIds.length === 0) {
        return res.json([]);
    }
    
    const { data: users } = await supabase
        .from("users")
        .select("id, full_name, email")
        .in("id", studentIds);
    
    // Combine enrollment data with user data
    const students = enrollments.map(e => {
        const user = users ? users.find(u => u.id === e.student_id) : null;
        return {
            id: e.student_id,
            student_id: e.student_id,
            full_name: user ? user.full_name : 'Unknown',
            email: user ? user.email : '',
            enrolled_at: e.enrolled_at,
            status: e.status
        };
    });
    
    res.json(students);
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
    const { data, error } = await supabase.from("google_drive_links").select("*").eq("course_id", courseId);
    if (error) return res.status(500).json({ error: error.message });
    // Return first result or null if no results
    res.json(data && data.length > 0 ? data[0] : null);
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
// VECTOR CHUNKS API - Persistent storage
// ============================================

// Save vector chunks to database
app.post('/api/vector-chunks', async (req, res) => {
    const { chunks } = req.body;
    if (!chunks || !Array.isArray(chunks)) {
        return res.status(400).json({ error: 'chunks array required' });
    }
    
    try {
        // Delete existing chunks for this file first
        const fileId = chunks[0]?.file_id;
        if (fileId) {
            await supabase.from('vector_chunks').delete().eq('file_id', fileId);
        }
        
        // Insert new chunks
        const records = chunks.map(c => ({
            course_id: c.course_id,
            file_id: c.file_id,
            file_name: c.file_name,
            chunk_text: c.text ? c.text.substring(0, 10000) : '', // Limit text length
            chunk_index: c.chunk_index,
            embedding: c.embedding ? Buffer.from(new Float32Array(c.embedding).buffer) : null, // Convert to buffer
            metadata: c.metadata || {}
        }));
        
        const { data, error } = await supabase.from('vector_chunks').insert(records);
        if (error) throw error;
        
        res.json({ success: true, count: records.length });
    } catch (err) {
        console.error('Save vector chunks error:', err);
        res.status(500).json({ error: err.message });
    }
});

// Get vector chunks for a course (all chunks, for loading into vector store)
app.get('/api/vector-chunks/:courseId', async (req, res) => {
    const { courseId } = req.params;
    
    try {
        const { data, error } = await supabase
            .from('vector_chunks')
            .select('*')
            .eq('course_id', courseId);
        
        if (error) throw error;
        
        // Convert buffer back to array
        const chunks = data.map(row => ({
            course_id: row.course_id,
            file_id: row.file_id,
            file_name: row.file_name,
            text: row.chunk_text,
            chunk_index: row.chunk_index,
            embedding: Array.from(new Float32Array(row.embedding)),
            metadata: row.metadata
        }));
        
        res.json(chunks);
    } catch (err) {
        console.error('Get vector chunks error:', err);
        res.status(500).json({ error: err.message });
    }
});

// Get all vector chunks (for loading all at startup)
app.get('/api/vector-chunks', async (req, res) => {
    try {
        const { data, error } = await supabase
            .from('vector_chunks')
            .select('*');
        
        if (error) throw error;
        
        const chunks = data.map(row => ({
            course_id: row.course_id,
            file_id: row.file_id,
            file_name: row.file_name,
            text: row.chunk_text,
            chunk_index: row.chunk_index,
            embedding: Array.from(new Float32Array(row.embedding)),
            metadata: row.metadata
        }));
        
        res.json(chunks);
    } catch (err) {
        console.error('Get all vector chunks error:', err);
        res.status(500).json({ error: err.message });
    }
});

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