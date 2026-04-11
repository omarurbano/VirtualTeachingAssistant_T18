const { createClient } = require("@supabase/supabase-js");

const supabaseUrl = "https://ehqjplwrrifezdwlsdbk.supabase.co";
const supabaseKey = "sb_publishable_rQZPfUr5fzxlGra3F1drJQ_qOUlx8Jo";

const supabase = createClient(supabaseUrl, supabaseKey);

module.exports = supabase;