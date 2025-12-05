from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    session,
    abort,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --------------------------------------------------
# Flask & DB setup
# --------------------------------------------------
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///coop_portal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "change-me-to-something-random"  # for sessions

db = SQLAlchemy(app)


# --------------------------------------------------
# Models
# --------------------------------------------------
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    weeks = db.Column(db.Integer, nullable=False)
    hours_per_week = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="Open")  # Open / Pending / Closed
    applicant_count = db.Column(db.Integer, default=0)

    salary = db.Column(db.String(80))
    job_type = db.Column(db.String(40))
    majors = db.Column(db.String(200))
    required_skills = db.Column(db.Text)
    preferred_skills = db.Column(db.Text)
    description = db.Column(db.Text)


class User(db.Model):
    """
    Single user table with roles:
      - role = "employer" or "faculty"
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # employer / faculty

    # Optional metadata
    company_name = db.Column(db.String(120))
    department = db.Column(db.String(80))

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


# --------------------------------------------------
# Sample data for co-op students (faculty view only)
# --------------------------------------------------
coop_students = [
    {
        "id": 1,
        "name": "Alex Johnson",
        "major": "Computer & Information Science",
        "company": "Tech Solutions Inc.",
        "position_title": "Software Engineer Co-op",
        "department": "CIS",
        "summary_status": "Submitted",
        "grade": None,
        "summary_text": (
            "Worked on front-end bug fixes and helped implement a feature "
            "for the internal dashboard. Learned agile workflow and code reviews."
        ),
    },
    {
        "id": 2,
        "name": "Jordan Smith",
        "major": "Software Engineering",
        "company": "Digital Dynamics",
        "position_title": "Frontend Developer Co-op",
        "department": "CIS",
        "summary_status": "Not Submitted",
        "grade": None,
        "summary_text": "",
    },
]


# --------------------------------------------------
# Seed functions
# --------------------------------------------------
def seed_positions_if_empty():
    """Create a couple of example positions if table is empty (for demo)."""
    if Position.query.count() == 0:
        p1 = Position(
            title="Software Engineer Co-op",
            location="Remote",
            weeks=10,
            hours_per_week=20,
            status="Open",
            applicant_count=5,
            salary="$25–30/hr",
            job_type="Part-time",
            majors="CIS, CS",
            required_skills="Python, Git, basic web development",
            preferred_skills="Flask, React",
            description="Work with our dev team on web applications.",
        )
        p2 = Position(
            title="Data Analyst Intern",
            location="Boston, MA",
            weeks=8,
            hours_per_week=15,
            status="Pending",
            applicant_count=2,
            salary="$22–28/hr",
            job_type="Part-time",
            majors="Data Science, CIS",
            required_skills="SQL, Excel",
            preferred_skills="Power BI",
            description="Assist with dashboards and ad-hoc analysis.",
        )
        db.session.add_all([p1, p2])
        db.session.commit()


def seed_users_if_empty():
    """Seed one employer and one faculty user if none exist."""
    if User.query.count() == 0:
        # Employer user
        emp = User(
            name="Acme Corp",
            email="employer@example.com",
            role="employer",
            company_name="Acme Corp",
        )
        emp.set_password("password123")

        # Faculty user
        fac = User(
            name="Dr. Lee",
            email="faculty@example.com",
            role="faculty",
            department="CIS",
        )
        fac.set_password("password123")

        db.session.add_all([emp, fac])
        db.session.commit()


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def compute_counts():
    open_count = Position.query.filter_by(status="Open").count()
    pending_count = Position.query.filter_by(status="Pending").count()
    closed_count = Position.query.filter_by(status="Closed").count()
    return open_count, pending_count, closed_count


def get_current_user():
    """Return a dict with user info from session, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = User.query.get(user_id)
    if not user:
        return None

    display_name = user.name
    if user.role == "faculty" and user.department:
        display_name = f"{user.name} ({user.department} Coordinator)"

    return {
        "id": user.id,
        "role": user.role,
        "name": display_name,
        "raw": user,
    }


def get_coop_student_or_404(coop_id: int):
    for s in coop_students:
        if s["id"] == coop_id:
            return s
    abort(404)


# --------------------------------------------------
# Routes: generic / login
# --------------------------------------------------
@app.route("/test")
def test_page():
    # Simple test page for layout
    return render_template("test_page.html", user=None, title="Test Portal")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            # Route based on role
            if user.role == "employer":
                return redirect(url_for("employer_dashboard"))
            elif user.role == "faculty":
                return redirect(url_for("faculty_dashboard"))
            else:
                session.clear()
                error = "Unknown user role."
        else:
            error = "Invalid email or password."

    return render_template("login.html", user=None, error=error, title="Co-op Portal Login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------
# Routes: Employer
# --------------------------------------------------
@app.route("/employer/dashboard")
def employer_dashboard():
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    positions = Position.query.all()
    open_count, pending_count, closed_count = compute_counts()

    return render_template(
        "employer_dashboard.html",
        user=current_user,
        positions=positions,
        open_count=open_count,
        pending_count=pending_count,
        closed_count=closed_count,
        title="Employer Dashboard",
    )


@app.route("/employer/new", methods=["GET", "POST"])
def employer_new_position():
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        location = request.form.get("location")
        weeks = int(request.form.get("weeks") or 0)
        hours_per_week = int(request.form.get("hours_per_week") or 0)
        salary = request.form.get("salary")
        job_type = request.form.get("job_type")
        majors = request.form.get("majors")
        required_skills = request.form.get("required_skills")
        preferred_skills = request.form.get("preferred_skills")
        description = request.form.get("description")

        new_position = Position(
            title=title,
            location=location,
            weeks=weeks,
            hours_per_week=hours_per_week,
            status="Open",
            applicant_count=0,
            salary=salary,
            job_type=job_type,
            majors=majors,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            description=description,
        )
        db.session.add(new_position)
        db.session.commit()

        return redirect(url_for("employer_dashboard"))

    return render_template(
        "employer_new_position.html",
        user=current_user,
        title="Post New Internship",
    )


@app.route("/employer/position/<int:position_id>/apps")
def employer_view_applicants(position_id):
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    position = Position.query.get_or_404(position_id)

    # Sample applicants (could be replaced with real DB models later)
    sample_applicants = [
        {
            "id": 101,
            "name": "Alex Johnson",
            "major": "Computer & Information Science",
            "gpa": 3.6,
            "credits_completed": 60,
            "applied_date": "2025-11-15",
            "status": "Interview Scheduled",
            "status_color": "green",
            "resume_url": "#",
        },
        {
            "id": 102,
            "name": "Jordan Smith",
            "major": "Software Engineering",
            "gpa": 3.4,
            "credits_completed": 48,
            "applied_date": "2025-11-10",
            "status": "Under Review",
            "status_color": "blue",
            "resume_url": "#",
        },
    ]

    return render_template(
        "employer_applicants.html",
        user=current_user,
        position=position,
        applicants=sample_applicants,
        title="Applicants",
    )


@app.route("/employer/position/<int:position_id>/select/<int:applicant_id>", methods=["POST"])
def employer_select_applicant(position_id, applicant_id):
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    position = Position.query.get_or_404(position_id)
    position.status = "Pending"
    db.session.commit()

    print(f"Selected applicant {applicant_id} for position {position_id}")
    return redirect(url_for("employer_view_applicants", position_id=position_id))


# --------------------------------------------------
# Routes: Faculty
# --------------------------------------------------
@app.route("/faculty/dashboard")
def faculty_dashboard():
    current_user = get_current_user()
    if not current_user or current_user["role"] != "faculty":
        return redirect(url_for("login"))

    total = len(coop_students)
    submitted = sum(1 for s in coop_students if s["summary_status"] == "Submitted")
    graded = sum(1 for s in coop_students if s["grade"] is not None)

    return render_template(
        "faculty_dashboard.html",
        user=current_user,
        students=coop_students,
        total_count=total,
        submitted_count=submitted,
        graded_count=graded,
        title="Faculty Dashboard",
    )


@app.route("/faculty/coop/<int:coop_id>", methods=["GET", "POST"])
def faculty_review_coop(coop_id):
    current_user = get_current_user()
    if not current_user or current_user["role"] != "faculty":
        return redirect(url_for("login"))

    student = get_coop_student_or_404(coop_id)

    if request.method == "POST":
        new_grade = request.form.get("grade")
        student["grade"] = new_grade or None
        return redirect(url_for("faculty_dashboard"))

    return render_template(
        "faculty_review.html",
        user=current_user,
        student=student,
        title="Review Co-op Summary",
    )


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_positions_if_empty()
        seed_users_if_empty()

    app.run(debug=True, port=5002)
