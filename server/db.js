const { Pool } = require("pg");
const db_pass = process.env.DB_PASS;

const pool = new Pool({
  user: "postgres",
  host: "localhost",
  database: "vta26",
  password: db_pass,
  port: 5433,
});

module.exports = pool;