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