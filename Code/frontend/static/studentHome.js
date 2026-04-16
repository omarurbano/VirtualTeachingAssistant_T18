//Student Page for VTA
//Loaded as soon as the page is rendered, it will get the user info and render the courses in the off canvas menu

const FLASK_BASE = 'http://localhost:5001';
const NODE_BASE  = 'http://localhost:3000';

// Check for authenticated session first
async function checkSession() {
    try {
        const response = await fetch(`${FLASK_BASE}/auth/me`);
        if (!response.ok) {
            // Not logged in, redirect to login
            window.location.href = '/login';
            return false;
        }
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        // Store user info in sessionStorage
        sessionStorage.setItem("user_id", data.user.id);
        sessionStorage.setItem("user_role", data.user.role);
        sessionStorage.setItem("user_name", data.user.full_name);
        return true;
    } catch (error) {
        console.error('Session check failed:', error);
        window.location.href = '/login';
        return false;
    }
}

// Initialize
(async function init() {
    const isAuthenticated = await checkSession();
    if (isAuthenticated) {
        getUserInfo();
        renderCourses();
    }
})();


//Adding event listener to form to add course to student schedule
document.getElementById("addCourseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    addCourse();
  });

document.getElementById("logoutBtn").addEventListener("click", (event) => {
    logout();
    //window.location.href = "http://localhost:5000/login";
});

//Rendering classes in the off canvas menu, each button will link to the VTA with the respective course loaded
async function renderCourses(){
    const userID = sessionStorage.getItem("user_id");
    if (!userID) {
        console.error("No user ID in session");
        return;
    }
    
    try {
        // Use Flask endpoint
        const response = await fetch(`${NODE_BASE}/studentcourses/${userID}`);
        if(response.ok)
        {
            const data = await response.json();
            const courses = data.courses || data;
            const courseList = document.getElementById("studentCourses");
            courseList.innerHTML = "";
            
            if (!courses || courses.length === 0) {
                courseList.innerHTML = '<li class="text-info-subtle">No courses enrolled</li>';
                return;
            }
            
            courses.forEach(course => {
                btn = document.createElement("button");
                btn.textContent = course.name || course.course_name || course.code;
                btn.onclick = () => {
                    // Pass course context via URL parameter
                    const courseId = course.id || course.course_id;
                    window.location.href = `/?course=${courseId}`; //Loads to VTA chat with course context
                };
                btn.classList.add("list-group-item","list-group-item-secondary","list-group-item-action", "text-info");
                courseList.appendChild(btn);
            });
        } else {
            console.error("Failed to fetch courses:", response.status);
        }
    } catch (error) {
        console.error("Error fetching courses:", error);
    }
}
//Fill in the name in the navbar based on the user id stored in session storage
function getUserInfo(){
    // Use sessionStorage which was set during authentication
    const userName = sessionStorage.getItem("user_name");
    const userId = sessionStorage.getItem("user_id");
    
    if (userName) {
        document.getElementById("userWelcome").textContent = `Welcome, ${userName}!`;
    } else if (userId) {
        // Fallback: fetch from API if not in session
        fetch(`${NODE_BASE}/users/${userId}`)
            .then(response => response.json())
            .then(user => {
                document.getElementById("userWelcome").textContent = `Welcome, ${user.full_name || user.first_name || 'Student'}!`;
            })
            .catch(error => {
                console.error("Error fetching user info:", error);
                document.getElementById("userWelcome").textContent = `Welcome, Student!`;
            });
    } else {
        document.getElementById("userWelcome").textContent = `Welcome, Student!`;
    }
}

//Checks to see if course code entered is a valid course code from a class
async function validCourseNumber(coursecode) {
    try {
        const response = await fetch(`${NODE_BASE}/course/code/${coursecode}`);
        if (response.ok) {
            const course = await response.json();
            return course;
        } else {
            console.error("Course not found");
            triggerToast("Course not found");
            return null;
        }
    } catch (error) {
        console.error("Course lookup failed:", error);
        triggerToast("Course lookup failed");
        return null;
    }
}

//Triggers a toast message with the provided message
function triggerToast(message) {
    const myToast = document.getElementById('myToast');
    const toastLabel = document.getElementById('toastmsg');
    toastLabel.textContent = message;

    const toast = new bootstrap.Toast(myToast);
    toast.show();

}

//Users is able to add a course by the code given to them by the professor, if the course code is valid, it will add the course 
//to their schedule and show a toast message confirming the addition
async function addCourse(){
    const courseCode = document.getElementById('courseCode').value;
    if (!courseCode) {
        triggerToast("Please enter a course code");
        return;
    }
    
    const validCourse = await validCourseNumber(courseCode);

    if (validCourse != null)
    {
        const userId = sessionStorage.getItem("user_id");
        const courseId = validCourse.id || validCourse.course_id;

        try {
            const response = await fetch(`${NODE_BASE}/addCourse/${userId}/${courseId}`, {
                method: 'POST'
            });

            if (response.ok) {
                const result = await response.json();
                document.getElementById('modalclosebtn').click();
                triggerToast("Course added successfully!");
                // Refresh the courses list
                renderCourses();
                // Clear the input
                document.getElementById('courseCode').value = '';
            } else {
                const error = await response.json();
                triggerToast(error.error || "Failed to add course");
            }
        } catch (error) {
            console.error("Add course failed:", error);
            triggerToast("Failed to add course");
        }
    }
}

function logout(){
    fetch(`${FLASK_BASE}/auth/logout`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            sessionStorage.clear();
            window.location.href = data.redirect || '/login';
        })
        .catch(err => {
            console.error('Logout failed:', err);
            // Clear session anyway and redirect
            sessionStorage.clear();
            window.location.href = '/login';
        });
}