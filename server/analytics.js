const express = require('express');
const cors = require('cors');
const supabase = require('./db');

const app = express();
app.use(cors());
app.use(express.json());

// ============================================
// ANALYTICS ENDPOINTS
// ============================================

// Record a student query
app.post('/api/queries', async (req, res) => {
  const { course_id, student_id, question, answer, sources_used, confidence_score } = req.body;
  
  const topics = extractTopics(question);
  
  const { data, error } = await supabase
    .from('queries')
    .insert([{ course_id, student_id, question, answer, sources_used: sources_used || [], confidence_score: confidence_score || 0, topics }])
    .select()
    .single();
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// Get queries for a course
app.get('/api/queries/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('queries')
    .select('*')
    .eq('course_id', courseId)
    .order('created_at', { ascending: false })
    .limit(100);
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// Get analytics summary
app.get('/api/analytics/summary/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('queries')
    .select('student_id, confidence_score, created_at')
    .eq('course_id', courseId);
  
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
  
  res.json({
    total_queries: data.length,
    active_students: uniqueStudents.length,
    avg_confidence: Math.round(avgConfidence * 100) / 100,
    engagement_trend: trend
  });
});

// Get confusing topics
app.get('/api/analytics/confusing-topics/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('queries')
    .select('topics, question')
    .eq('course_id', courseId);
  
  if (error) return res.status(500).json({ error: error.message });
  
  const topicCounts = {};
  for (const q of data.slice(-50)) {
    if (q.topics) {
      for (const topic of q.topics) {
        topicCounts[topic] = (topicCounts[topic] || 0) + 1;
      }
    }
  }
  
  const sorted = Object.entries(topicCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([topic, count]) => ({
      topic,
      count,
      difficulty: count > 10 ? 'HIGH' : count > 5 ? 'MEDIUM' : 'LOW'
    }));
  
  res.json(sorted);
});

// Get at-risk students
app.get('/api/analytics/at-risk/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('queries')
    .select('student_id, confidence_score, created_at')
    .eq('course_id', courseId);
  
  if (error) return res.status(500).json({ error: error.message });
  
  // Students with low confidence or no recent activity
  const studentStats = {};
  for (const q of data) {
    if (!studentStats[q.student_id]) {
      studentStats[q.student_id] = { queries: 0, failed: 0, last: null };
    }
    studentStats[q.student_id].queries++;
    if (q.confidence_score < 0.5) studentStats[q.student_id].failed++;
    studentStats[q.student_id].last = q.created_at;
  }
  
  const atRisk = Object.entries(studentStats)
    .filter(([_, stats]) => stats.failed / stats.queries > 0.3)
    .map(([student_id, stats]) => ({
      student_id,
      total_queries: stats.queries,
      failed_queries: stats.failed,
      reason: stats.failed / stats.queries > 0.5 ? 'STRUGGLING' : 'NEEDS_HELP'
    }));
  
  res.json(atRisk);
});

// Add course material
app.post('/api/materials', async (req, res) => {
  const { course_id, source_type, file_name, chunks_count, file_id } = req.body;
  
  const { data, error } = await supabase
    .from('course_materials')
    .insert([{ course_id, source_type, file_name, chunks_count, file_id }])
    .select()
    .single();
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// Get materials
app.get('/api/materials/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('course_materials')
    .select('*')
    .eq('course_id', courseId);
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(data);
});

// Drive connect
app.post('/api/drive/connect', async (req, res) => {
  const { course_id, teacher_id, folder_url, access_token, refresh_token } = req.body;
  
  const { data: existing } = await supabase
    .from('google_drive_links')
    .select('*')
    .eq('course_id', course_id)
    .single();
  
  let result, error;
  if (existing) {
    ({ data: result, error } = await supabase
      .from('google_drive_links')
      .update({ folder_url, access_token, refresh_token, connected_at: new Date().toISOString() })
      .eq('course_id', course_id)
      .select()
      .single());
  } else {
    ({ data: result, error } = await supabase
      .from('google_drive_links')
      .insert([{ course_id, teacher_id, folder_url, access_token, refresh_token }])
      .select()
      .single());
  }
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(result);
});

// Drive get
app.get('/api/drive/:courseId', async (req, res) => {
  const { courseId } = req.params;
  const { data, error } = await supabase
    .from('google_drive_links')
    .select('*')
    .eq('course_id', courseId)
    .single();
  
  if (error) return res.status(500).json({ error: error.message });
  res.json(data || null);
});

// Helper: Extract topics from question
function extractTopics(question) {
  const q = question.toLowerCase();
  const topics = [];
  const topicKeywords = {
    'Backpropagation': ['backprop', 'gradient', 'chain rule'],
    'Loss Functions': ['loss', 'cost', 'mse', 'cross entropy'],
    'Neural Networks': ['neural', 'network', 'neuron'],
    'CNNs': ['cnn', 'convolutional', 'filter'],
    'RNNs': ['rnn', 'recurrent', 'lstm'],
    'Transformers': ['transformer', 'attention', 'bert'],
    'Optimization': ['optimizer', 'adam', 'learning rate'],
    'Regularization': ['dropout', 'l1', 'l2', 'overfit']
  };
  
  for (const [topic, keywords] of Object.entries(topicKeywords)) {
    if (keywords.some(k => q.includes(k))) topics.push(topic);
  }
  
  return topics.length ? topics : ['General'];
}

// Start server
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Analytics API running on http://localhost:${PORT}`);
});

// Handle process cleanup
process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));