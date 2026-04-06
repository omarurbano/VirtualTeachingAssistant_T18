const express = require("express");
const cors = require("cors");
const pool = require("./db");

const app = express();
app.use(cors());
app.use(express.json());

//add routes here

//All users
app.get("/users", async (req, res) => {
    try {
      const result = await pool.query("SELECT * FROM users");
      res.json(result.rows);
    } catch (err) {
      console.error(err);
      res.status(500).send("Server error");
    }
  });

//Get user by id
app.get("/users/:id", async (req, res) => {
    const { id } = req.params;
    try {
      const result = await pool.query("SELECT * FROM users WHERE user_id = $1", [id]);
      if (result.rows.length === 0) {
        return res.status(404).send("User not found");
      }
      res.json(result.rows[0]);
    } catch (err) {
      console.error(err);
      res.status(500).send("Server error");
    }
});

//Get all courses
app.get("/course", async (req, res) => {
try {
    const result = await pool.query("SELECT * FROM course");
    res.json(result.rows);
} catch (err) {
    console.error(err);
    res.status(500).send("Server error");
}
});

//Get course by id
app.get("/course/:id", async (req, res) => {
    const { id } = req.params;
    try {
      const result = await pool.query("SELECT * FROM course WHERE course_id = $1", [id]);
      if (result.rows.length === 0) {
        return res.status(404).send("Course not found");
      }
      res.json(result.rows[0]);
    } catch (err) {
      console.error(err);
      res.status(500).send("Server error");
    }
});

//Get course by coursecode
app.get("/course/code/:courseCode", async (req, res) => {
    const { courseCode } = req.params;
    try {
      const result = await pool.query("SELECT * FROM course WHERE course_code = $1", [courseCode]);
      if (result.rows.length === 0) {
        return res.status(404).send("Course not found");
      }
      res.json(result.rows[0]);
    } catch (err) {
      console.error(err);
      res.status(500).send("Server error");
    }
});

//Add course by id and user
app.post("/addCourse/:userId/:courseId", async (req, res) => {
    const { userId, courseId } = req.params;
    try {
      const result = await pool.query("INSERT INTO user_courses (user_id, course_id) VALUES ($1, $2) RETURNING *", [userId, courseId]);
      res.json(result.rows[0]);
    } catch (err) {
      console.error(err);
      res.status(500).send("Server error");
    }
});

//Get enrolled courses based on userID
app.get("/studentcourses/:userId", async (req, res) => {
    const{ userId } = req.params;
    try{
        const result = await pool.query('SELECT c.course_name FROM user_courses uc, course c WHERE uc.course_id = c.course_id AND uc.user_id = $1', [userId])
        if (result.rows.length === 0) {
            return res.status(404).send("Course not found");
          }
        res.json(result.rows).status(200);

    }
    catch (err) {
        console.error(err);
        res.status(500).send("Server error");
    }
});

app.listen(3000, () => {
  console.log("Server running on http://localhost:5433");
});