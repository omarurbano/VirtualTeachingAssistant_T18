//Student Page for VTA
//Loaded as soon as the page is rendered, it will get the user info and render the courses in the off canvas menu

// Check for authenticated session first
async function checkSession() {
    try {
        const response = await fetch('/auth/me');
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
        const response = await fetch(`/studentcourses/${userID}`);
        if(response.ok)
        {
            const data = await response.json();
            // Handle different response formats from Express
            const courses = data.courses || data;
            const courseList = document.getElementById("studentCourses");
            courseList.innerHTML = "";
            
            if (!courses || courses.length === 0) {
                courseList.innerHTML = '<li class="text-info p-3">No courses enrolled</li>';
                return;
            }
            
            courses.forEach(course => {
                // Handle nested structure from Express: {courses: {name: "..."}}
                const courseName = course.courses?.name || course.name || course.course_name || course.code || "Unknown Course";
                const courseId = course.course_id || course.id || course.courses?.id;
                
                const btn = document.createElement("button");
                btn.textContent = courseName;
                btn.onclick = () => {
                    window.location.href = `/?course=${courseId}`;
                };
                btn.classList.add("course-btn");
                courseList.appendChild(btn);
            });
        } else {
            console.error("Failed to fetch courses:", response.status);
            document.getElementById("studentCourses").innerHTML = '<li class="text-danger p-3">Error loading courses</li>';
        }
    } catch (error) {
        console.error("Error fetching courses:", error);
        document.getElementById("studentCourses").innerHTML = '<li class="text-danger p-3">Error loading courses</li>';
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
        fetch(`/users/${userId}`)
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
        const response = await fetch(`/course/code/${coursecode}`);
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
            const response = await fetch(`/addCourse/${userId}/${courseId}`, {
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
    fetch('/auth/logout', { method: 'POST' })
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