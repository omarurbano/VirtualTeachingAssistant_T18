//Student Page for VTA
//Loaded as soon as the page is rendered, it will get the user info and render the courses in the off canvas menu
sessionStorage.setItem("user_id", 1)
getUserInfo();
renderCourses();


//Adding event listener to form to add course to student schedule
document.getElementById("addCourseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    addCourse();
  });

document.getElementById("logoutBtn").addEventListener("click", (event) => {
    logout();
    //window.location.href = "http://localhost:5000/login";
});

//Rendering classes in the off canvas menu, each button will link to the VTA with the repspective course loaded
async function renderCourses(){
    const userID = sessionStorage.getItem("user_id");
    const response = await fetch(`http://localhost:3000/studentcourses/${userID}`);
    console.log(response);
    if(response.ok)
    {
        console.log(response);
        const courses = await response.json();
        const courseList = document.getElementById("studentCourses");
        courseList.innerHTML = "";
        courses.forEach(course => {
            btn = document.createElement("button");
            btn.textContent = course.course_name;
            btn.onclick = () => {
                window.location.href = "http://localhost:5000/"; //Loads to VTA chat
            };
            btn.classList.add("list-group-item","list-group-item-secondary","list-group-item-action", "active", "text-info");
            courseList.appendChild(btn);
        });
    }
}
//Fill in the name in the navbar based on the user id stored in session storage
function getUserInfo(){
    const userId = sessionStorage.getItem("user_id");
    fetch(`http://localhost:3000/users/${userId}`)
        .then(response => response.json())
        .then(user => {
            document.getElementById("userWelcome").textContent = `Welcome, ${user.first_name}!`;
        })
        .catch(error => console.error("Error fetching user info:", error));
}

//Checks to see if course code entered is a valid course code from a class
async function validCourseNumber(coursecode) {
    const response = await fetch(`http://localhost:3000/course/code/${coursecode}`);
    if (response.ok) {
        const course = await response.json();
        return course;
    } else {
        console.error("Course not found");
        triggerToast("Course not found");
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
    console.log(courseCode);
    const validCourse = await validCourseNumber(courseCode);

    if (validCourse != null)
    {
        console.log(validCourse);
        const userId = sessionStorage.getItem("user_id");
        const courseId = validCourse.course_id;

        const response = await fetch(`http://localhost:3000/addCourse/${userId}/${courseId}`, {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            console.log(result);
            document.getElementById('modalclosebtn').click();
            triggerToast("Course added successfully!");
            setTimeout(() => {
                window.location.href = "http://localhost:5000/studenthome"
            }, 2000);
        } else {
            triggerToast("Failed to add course");
        }
    }
    
}

function logout(){
    sessionStorage.clear();
    //window.location.href = "http://localhost:5000/login";
}