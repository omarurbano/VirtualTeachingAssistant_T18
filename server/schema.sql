-- ============================================
-- SUPABASE DATABASE SCHEMA FOR VTA
-- ============================================
-- Run these SQL statements in the Supabase SQL Editor
-- https://supabase.com/dashboard/project/ehqjplwrrifezdwlsdbk/sql
-- ============================================

-- 1. QUERIES TABLE - Track all student questions
CREATE TABLE IF NOT EXISTS queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT,
    sources_used TEXT[],
    confidence_score FLOAT DEFAULT 0,
    topics TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for faster analytics
CREATE INDEX IF NOT EXISTS idx_queries_course ON queries(course_id);
CREATE INDEX IF NOT EXISTS idx_queries_student ON queries(student_id);
CREATE INDEX IF NOT EXISTS idx_queries_created ON queries(created_at DESC);

-- 2. STUDENT PROGRESS TABLE - Track student engagement
CREATE TABLE IF NOT EXISTS student_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    total_queries INTEGER DEFAULT 0,
    failed_queries INTEGER DEFAULT 0,
    last_session TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(course_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_progress_course ON student_progress(course_id);
CREATE INDEX IF NOT EXISTS idx_progress_student ON student_progress(student_id);

-- 3. COURSE MATERIALS TABLE - Track vectorized documents
CREATE TABLE IF NOT EXISTS course_materials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id TEXT NOT NULL,
    source_type TEXT, -- 'upload' or 'google_drive'
    file_name TEXT,
    chunks_count INTEGER DEFAULT 0,
    file_id TEXT,
    embedded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_materials_course ON course_materials(course_id);

-- 4. GOOGLE DRIVE LINKS TABLE - Track Drive connections
CREATE TABLE IF NOT EXISTS google_drive_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id TEXT NOT NULL UNIQUE,
    teacher_id TEXT NOT NULL,
    folder_url TEXT,
    refresh_token TEXT,
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- ENABLE POSTGIS/pgvector IF NEEDED
-- ============================================

-- Note: For vector storage, we store metadata in these tables.
-- The actual embeddings are stored in the Flask in-memory vector store
-- with course_id scoping.

-- ============================================
-- ROW LEVEL SECURITY (Optional - for production)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE google_drive_links ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust as needed)
CREATE POLICY "Allow read queries for course participants" ON queries
    FOR SELECT USING (true);

CREATE POLICY "Allow insert on queries" ON queries
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow read progress for teachers" ON student_progress
    FOR SELECT USING (true);

CREATE POLICY "Allow update progress" ON student_progress
    FOR UPDATE USING (true);

CREATE POLICY "Allow read materials for course" ON course_materials
    FOR SELECT USING (true);

CREATE POLICY "Allow insert materials" ON course_materials
    FOR INSERT WITH CHECK (true);

-- ============================================
-- VERIFY TABLES CREATED
-- ============================================

SELECT 
    'queries' as table_name, 
    count(*) as rows 
FROM queries 
UNION ALL
SELECT 
    'student_progress', 
    count(*) 
FROM student_progress 
UNION ALL
SELECT 
    'course_materials', 
    count(*) 
FROM course_materials 
UNION ALL
SELECT 
    'google_drive_links', 
    count(*) 
FROM google_drive_links;