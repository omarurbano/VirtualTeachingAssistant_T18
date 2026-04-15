const express = require("express");
const cors = require("cors");
const supabase = require("./db");

const app = express();
app.use(cors());
app.use(express.json());

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// ============================================
// AUTH - Register
// ============================================

app.post("/auth/register", async (req, res) => {
    try {
        const { email, password, full_name, role } = req.body;
        
        // Hash password (simple SHA256 for demo - use bcrypt in production)
        const crypto = require('crypto');
        const password_hash = crypto.createHash('sha256').update(password).digest('hex');
        
        const { data, error } = await supabase
            .from("users")
            .insert([{ 
                email: email.toLowerCase(), 
                password_hash, 
                full_name, 
                role: role || 'student' 
            }])
            .select()
            .single();
        
        if (error) {
            // Check for duplicate email
            if (error.message.includes('duplicate')) {
                return res.status(400).json({ error: 'Email already registered' });
            }
            throw error;
        }
        
        res.status(201).json(data);
    } catch (err) {
        console.error('Register error:', err);
        res.status(500).json({ error: err.message });
    }
});

// ============================================
// USERS
// ============================================

// Get all users
app.get("/users", async (req, res) => {
    try {
        const { data, error } = await supabase
            .from("users")
            .select("*");
        
        if (error) throw error;
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get user by id
app.get("/users/:id", async (req, res) => {
    const { id } = req.params;
    try {
        const { data, error } = await supabase
            .from("users")
            .select("*")
            .eq("id", id)
            .single();
        
        if (error) throw error;
        if (!data) return res.status(404).send("User not found");
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// COURSES
// ============================================

// Get all courses
app.get("/course", async (req, res) => {
    try {
        const { data, error } = await supabase
            .from("courses")
            .select("*");
        
        if (error) throw error;
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get course by id
app.get("/course/:id", async (req, res) => {
    const { id } = req.params;
    try {
        const { data, error } = await supabase
            .from("courses")
            .select("*")
            .eq("id", id)
            .single();
        
        if (error) throw error;
        if (!data) return res.status(404).send("Course not found");
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get course by course code
app.get("/course/code/:courseCode", async (req, res) => {
    const { courseCode } = req.params;
    try {
        const { data, error } = await supabase
            .from("courses")
            .select("*")
            .eq("code", courseCode)
            .single();
        
        if (error) throw error;
        if (!data) return res.status(404).send("Course not found");
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// ENROLLMENTS
// ============================================

// Add course enrollment for user
app.post("/addCourse/:userId/:courseId", async (req, res) => {
    const { userId, courseId } = req.params;
    try {
        const { data, error } = await supabase
            .from("enrollments")
            .insert([{ student_id: userId, course_id: courseId }])
            .select()
            .single();
        
        if (error) throw error;
        res.json(data).status(200);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get enrolled courses for a student
app.get("/studentcourses/:userId", async (req, res) => {
    const { userId } = req.params;
    try {
        const { data, error } = await supabase
            .from("enrollments")
            .select(`
                courses (
                    name
                )
            `)
            .eq("student_id", userId);
        
        if (error) throw error;
        if (data.length === 0) return res.status(404).send("Courses not found");
        res.json(data).status(200);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// QUERIES - Track student questions for analytics
// ============================================

// Record a student query
app.post("/api/queries", async (req, res) => {
    try {
        const { course_id, student_id, question, answer, sources_used, confidence_score } = req.body;
        
        // Extract topics from question using simple keyword matching
        const topics = extractTopics(question);
        
        const { data, error } = await supabase
            .from("queries")
            .insert([{ 
                course_id, 
                student_id, 
                question, 
                answer, 
                sources_used: sources_used || [],
                confidence_score: confidence_score || 0,
                topics
            }])
            .select()
            .single();
        
        if (error) throw error;
        
        // Also update student progress
        await updateStudentProgress(course_id, student_id, true, false);
        
        res.status(201).json(data);
    } catch (err) {
        console.error('Query insert error:', err);
        res.status(500).json({ error: err.message });
    }
});

// Get queries for a course (for analytics)
app.get("/api/queries/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        const { data, error } = await supabase
            .from("queries")
            .select("*")
            .eq("course_id", courseId)
            .order("created_at", { ascending: false })
            .limit(100);
        
        if (error) throw error;
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get confusing topics for a course
app.get("/api/analytics/confusing-topics/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        // Get all queries for this course
        const { data: queries, error } = await supabase
            .from("queries")
            .select("topics, question, created_at")
            .eq("course_id", courseId);
        
        if (error) throw error;
        
        // Count topics
        const topicCounts = {};
        const recentQueries = queries.slice(-50); // Last 50 queries
        
        for (const q of recentQueries) {
            if (q.topics && Array.isArray(q.topics)) {
                for (const topic of q.topics) {
                    topicCounts[topic] = (topicCounts[topic] || 0) + 1;
                }
            }
        }
        
        // Sort by count and get top topics
        const sortedTopics = Object.entries(topicCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([topic, count]) => ({
                topic,
                count,
                difficulty: count > 10 ? 'HIGH' : count > 5 ? 'MEDIUM' : 'LOW'
            }));
        
        res.json(sortedTopics);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get at-risk students for a course
app.get("/api/analytics/at-risk/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        const { data: progress, error } = await supabase
            .from("student_progress")
            .select("*")
            .eq("course_id", courseId);
        
        if (error) throw error;
        
        // Determine at-risk criteria:
        // 1. No session in 7+ days = low engagement
        // 2. Failed queries > 50% = struggling
        // 3. Total queries < 3 = disengaged
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        
        const atRisk = progress.filter(s => {
            const lastSession = s.last_session ? new Date(s.last_session) : null;
            const failedRatio = s.total_queries > 0 ? s.failed_queries / s.total_queries : 0;
            
            return (
                (lastSession && lastSession < sevenDaysAgo) || // No activity in 7 days
                (failedRatio > 0.5) || // More than 50% failed
                (s.total_queries < 3 && lastSession) // Very few queries
            );
        }).map(s => ({
            student_id: s.student_id,
            reason: (() => {
                const reasons = [];
                const lastSession = s.last_session ? new Date(s.last_session) : null;
                const failedRatio = s.total_queries > 0 ? s.failed_queries / s.total_queries : 0;
                
                if (lastSession && lastSession < sevenDaysAgo) reasons.push('LOW_ACTIVITY');
                if (failedRatio > 0.5) reasons.push('STRUGGLING');
                if (s.total_queries < 3 && lastSession) reasons.push('DISENGAGED');
                return reasons;
            })(),
            total_queries: s.total_queries,
            failed_queries: s.failed_queries,
            last_session: s.last_session
        }));
        
        res.json(atRisk);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// Get analytics summary for a course
app.get("/api/analytics/summary/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        // Get query counts
        const { data: queries, error } = await supabase
            .from("queries")
            .select("created_at, confidence_score")
            .eq("course_id", courseId);
        
        if (error) throw error;
        
        // Get unique students
        const uniqueStudents = new Set(queries.map(q => q.student_id));
        
        // Calculate stats
        const totalQueries = queries.length;
        const avgConfidence = queries.reduce((sum, q) => sum + (q.confidence_score || 0), 0) / (totalQueries || 1);
        
        // Get engagement trend (queries per day, last 7 days)
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        
        const engagementTrend = [];
        for (let i = 6; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            const dateStr = date.toISOString().split('T')[0];
            
            const dayQueries = queries.filter(q => 
                q.created_at && q.created_at.startsWith(dateStr)
            );
            
            engagementTrend.push({
                date: dateStr,
                count: dayQueries.length
            });
        }
        
        res.json({
            total_queries: totalQueries,
            active_students: uniqueStudents.size,
            avg_confidence: Math.round(avgConfidence * 100) / 100,
            engagement_trend: engagementTrend
        });
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// COURSE MATERIALS - Track vectorized documents
// ============================================

// Add course material (after vectorization)
app.post("/api/materials", async (req, res) => {
    try {
        const { course_id, source_type, file_name, chunks_count, file_id } = req.body;
        
        const { data, error } = await supabase
            .from("course_materials")
            .insert([{ 
                course_id, 
                source_type, 
                file_name, 
                chunks_count,
                file_id
            }])
            .select()
            .single();
        
        if (error) throw error;
        res.status(201).json(data);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// Get materials for a course
app.get("/api/materials/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        const { data, error } = await supabase
            .from("course_materials")
            .select("*")
            .eq("course_id", courseId)
            .order("embedded_at", { ascending: false });
        
        if (error) throw error;
        res.json(data);
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// STUDENT PROGRESS - Track engagement
// ============================================

// Get or create student progress
async function updateStudentProgress(course_id, student_id, queryMade, failed) {
    try {
        // Check if exists
        const { data: existing } = await supabase
            .from("student_progress")
            .select("*")
            .eq("course_id", course_id)
            .eq("student_id", student_id)
            .single();
        
        if (existing) {
            // Update
            await supabase
                .from("student_progress")
                .update({
                    total_queries: existing.total_queries + (queryMade ? 1 : 0),
                    failed_queries: existing.failed_queries + (failed ? 1 : 0),
                    last_session: new Date().toISOString()
                })
                .eq("id", existing.id);
        } else {
            // Create
            await supabase
                .from("student_progress")
                .insert([{
                    course_id,
                    student_id,
                    total_queries: queryMade ? 1 : 0,
                    failed_queries: failed ? 1 : 0
                }]);
        }
    } catch (err) {
        console.error('Update progress error:', err);
    }
}

// Get student progress
app.get("/api/progress/:courseId/:studentId", async (req, res) => {
    const { courseId, studentId } = req.params;
    try {
        const { data, error } = await supabase
            .from("student_progress")
            .select("*")
            .eq("course_id", courseId)
            .eq("student_id", studentId)
            .single();
        
        if (error) throw error;
        res.json(data || { total_queries: 0, failed_queries: 0 });
    } catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

// ============================================
// HELPER FUNCTIONS
// ============================================

// Extract topics from question using keyword matching
function extractTopics(question) {
    const questionLower = question.toLowerCase();
    const topics = [];
    
    // Common CS/ML topics
    const topicKeywords = {
        'Backpropagation': ['backprop', 'gradient', 'chain rule'],
        'Loss Functions': ['loss', 'cost', 'error', 'mse', 'cross entropy'],
        'Neural Networks': ['neural', 'network', 'neuron', 'layer'],
        'Activation Functions': ['activation', 'relu', 'sigmoid', 'tanh', 'softmax'],
        'Optimization': ['optimization', 'optimizer', 'adam', 'sgd', 'learning rate'],
        'Regularization': ['regularization', 'dropout', 'l1', 'l2', 'overfit'],
        'CNNs': ['cnn', 'convolutional', 'convolution', 'filter', 'kernel'],
        'RNNs': ['rnn', 'recurrent', 'lstm', 'gru', 'sequence'],
        'Transformers': ['transformer', 'attention', 'bert', 'gpt', 'token'],
        'Data Preprocessing': ['preprocessing', 'normalization', 'scaling', 'feature'],
        'Model Evaluation': ['accuracy', 'precision', 'recall', 'f1', 'confusion matrix'],
        'Hyperparameters': ['hyperparameter', 'batch', 'epoch', 'learning rate']
    };
    
    for (const [topic, keywords] of Object.entries(topicKeywords)) {
        for (const keyword of keywords) {
            if (questionLower.includes(keyword)) {
                topics.push(topic);
                break;
            }
        }
    }
    
    // Default to 'General' if no topics found
    if (topics.length === 0) {
        topics.push('General');
    }
    
    return topics;
}

// ============================================
// GOOGLE DRIVE INTEGRATION
// ============================================

// Store Google Drive tokens for a course
app.post("/api/drive/connect", async (req, res) => {
    try {
        const { course_id, teacher_id, refresh_token, folder_url } = req.body;
        
        // Check if already exists
        const { data: existing } = await supabase
            .from("google_drive_links")
            .select("*")
            .eq("course_id", course_id)
            .single();
        
        let data, error;
        if (existing) {
            // Update
            ({ data, error } = await supabase
                .from("google_drive_links")
                .update({ refresh_token, folder_url, connected_at: new Date().toISOString() })
                .eq("course_id", course_id)
                .select()
                .single());
        } else {
            // Insert
            ({ data, error } = await supabase
                .from("google_drive_links")
                .insert([{ course_id, teacher_id, refresh_token, folder_url }])
                .select()
                .single());
        }
        
        if (error) throw error;
        res.status(201).json(data);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// Get Google Drive connection for a course
app.get("/api/drive/:courseId", async (req, res) => {
    const { courseId } = req.params;
    try {
        const { data, error } = await supabase
            .from("google_drive_links")
            .select("*")
            .eq("course_id", courseId)
            .single();
        
        if (error) throw error;
        res.json(data || null);
    } catch (err) {
        res.json(null);
    }
});

// ============================================
// START SERVER
// ============================================

// Update existing test users with correct password hash
async function seedUsers() {
    const crypto = require('crypto');
    const password_hash = crypto.createHash('sha256').update('demo123').digest('hex');
    
    // Update teacher
    await supabase.from('users').update({ password_hash }).eq('email', 'teacher@test.com');
    // Update student  
    await supabase.from('users').update({ password_hash }).eq('email', 'student@test.com');
    console.log('Updated password hashes');
}

seedUsers().then(() => {
    const PORT = 3000;
    const server = app.listen(PORT, () => {
        console.log(`Server running on http://localhost:${PORT}`);
    });

    // Keep process alive
    process.on('SIGINT', () => {
        console.log('\nShutting down...');
        server.close(() => {
            console.log('Server closed');
            process.exit(0);
        });
    });

    process.on('SIGTERM', () => {
        server.close(() => {
            process.exit(0);
        });
    });
});