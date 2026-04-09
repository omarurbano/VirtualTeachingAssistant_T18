from flask import Flask, render_template

app = Flask(__name__)
app.config['DEBUG'] = True


@app.route('/instructor/dashboard')
def dashboard():
    return render_template('instructor/dashboard.html')


@app.route('/instructor/course/<course_id>')
def course(course_id):
    return render_template('instructor/course.html', course_id=course_id)


@app.route('/instructor/analytics/<course_id>')
def analytics(course_id):
    return render_template('instructor/analytics.html', course_id=course_id)


if __name__ == '__main__':
    app.run(debug=True)
