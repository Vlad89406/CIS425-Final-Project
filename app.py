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
class User(db.Model):
    """
    Single user table with roles:
      - role = "employer", "faculty", or "student"
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # employer / faculty / student

    # Employer-specific
    company_name = db.Column(db.String(120))
    company_location = db.Column(db.String(120))
    company_website = db.Column(db.String(200))
    contact_phone = db.Column(db.String(40))

    # Faculty-specific
    department = db.Column(db.String(80))

    # Student-specific (kept for future expansion)
    major = db.Column(db.String(120))
    student_id = db.Column(db.String(40))
    year = db.Column(db.String(40))  # e.g., "Junior", "Senior"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Link each position to the employer who created it
    employer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

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

        # summary written by student
        "summary_text": (
            "Worked on front-end bug fixes and helped implement a feature "
            "for the internal dashboard. Learned agile workflow and code reviews."
        ),

        # faculty-entered fields
        "grade": None,
        "comment": "",

        # basic status flag (we'll also compute a richer status in the view)
        "summary_status": "Submitted",
    },
    {
        "id": 2,
        "name": "Jordan Smith",
        "major": "Software Engineering",
        "company": "Digital Dynamics",
        "position_title": "Frontend Developer Co-op",
        "department": "CIS",

        "summary_text": "",  # not submitted yet
        "grade": None,
        "comment": "",

        "summary_status": "Not Submitted",
    },
]


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def compute_counts_for_employer(employer_id: int):
    open_count = Position.query.filter_by(
        employer_id=employer_id, status="Open"
    ).count()
    pending_count = Position.query.filter_by(
        employer_id=employer_id, status="Pending"
    ).count()
    closed_count = Position.query.filter_by(
        employer_id=employer_id, status="Closed"
    ).count()
    return open_count, pending_count, closed_count


def get_current_user():
    """Return a dict with user info from session, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = User.query.get(user_id)
    if not user:
        return None

    # Display name depends on role
    display_name = user.name
    if user.role == "faculty" and user.department:
        display_name = f"{user.name} ({user.department} Coordinator)"
    elif user.role == "employer" and user.company_name:
        display_name = user.company_name

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
# Routes: generic / home / login / register
# --------------------------------------------------
@app.route("/")
def home():
    # Landing page = login
    return redirect(url_for("login"))


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
            elif user.role == "student":
                return redirect(url_for("student_dashboard"))
            else:
                session.clear()
                error = "Unknown user role."
        else:
            error = "Invalid email or password."

    return render_template(
        "login.html",
        user=None,
        error=error,
        title="Co-op Portal Login",
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        role = request.form.get("role")  # employer / faculty / student
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Employer fields
        company_name = request.form.get("company_name")
        company_location = request.form.get("company_location")
        company_website = request.form.get("company_website")
        contact_phone = request.form.get("contact_phone")

        # Faculty field
        department = request.form.get("department")

        # Student fields (for future expansion)
        major = request.form.get("major")
        student_id = request.form.get("student_id")
        year = request.form.get("year")

        if role not in ("employer", "faculty", "student"):
            error = "Please select a valid role."
        else:
            existing = User.query.filter_by(email=email).first()
            if existing:
                error = "An account with this email already exists."
            else:
                user = User(
                    name=name,
                    email=email,
                    role=role,
                    company_name=company_name if role == "employer" else None,
                    company_location=company_location if role == "employer" else None,
                    company_website=company_website if role == "employer" else None,
                    contact_phone=contact_phone if role == "employer" else None,
                    department=department if role == "faculty" else None,
                    major=major if role == "student" else None,
                    student_id=student_id if role == "student" else None,
                    year=year if role == "student" else None,
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

                # Log them in
                session["user_id"] = user.id

                # Redirect based on role
                if role == "employer":
                    return redirect(url_for("employer_dashboard"))
                elif role == "faculty":
                    return redirect(url_for("faculty_dashboard"))
                else:  # student
                    return redirect(url_for("student_dashboard"))

    return render_template(
        "register.html",
        user=None,
        error=error,
        title="Co-op Portal Registration",
    )


# --------------------------------------------------
# Routes: Employer
# --------------------------------------------------
@app.route("/employer/dashboard")
def employer_dashboard():
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    employer_id = current_user["id"]

    # Only positions for this employer
    positions = Position.query.filter_by(employer_id=employer_id).all()
    open_count, pending_count, closed_count = compute_counts_for_employer(employer_id)

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
            employer_id=current_user["id"],
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

    # Ensure employer only sees their own position
    position = Position.query.filter_by(
        id=position_id, employer_id=current_user["id"]
    ).first_or_404()

    # If there are no applicants yet, show an empty list
    if position.applicant_count == 0:
        applicants = []
    else:
        # Temporary sample applicants until student applying logic is added
        applicants = [
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
        applicants=applicants,
        title="Applicants",
    )


@app.route(
    "/employer/position/<int:position_id>/select/<int:applicant_id>", methods=["POST"]
)
def employer_select_applicant(position_id, applicant_id):
    current_user = get_current_user()
    if not current_user or current_user["role"] != "employer":
        return redirect(url_for("login"))

    position = Position.query.filter_by(
        id=position_id, employer_id=current_user["id"]
    ).first_or_404()
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

    faculty_dept = current_user["raw"].department

    # Only students in this faculty's department
    dept_students = [
        s for s in coop_students
        if s["department"] == faculty_dept
    ]

    # Compute status + badge color dynamically
    for s in dept_students:
        if not s["summary_text"]:
            s["computed_status"] = "Not Submitted"
            s["badge"] = "secondary"
        elif s["summary_text"] and not s["grade"]:
            s["computed_status"] = "Submitted – Awaiting Grade"
            s["badge"] = "warning"
        else:
            s["computed_status"] = "Graded"
            s["badge"] = "success"

    return render_template(
        "faculty_dashboard.html",
        user=current_user,
        students=dept_students,
        title="Faculty Dashboard",
    )


@app.route("/faculty/coop/<int:coop_id>", methods=["GET", "POST"])
def faculty_review_coop(coop_id):
    current_user = get_current_user()
    if not current_user or current_user["role"] != "faculty":
        return redirect(url_for("login"))

    student = get_coop_student_or_404(coop_id)

    if request.method == "POST":
        student["grade"] = request.form.get("grade") or None
        student["comment"] = request.form.get("comment") or ""

        # Basic status flag update (main display comes from computed_status)
        if student["summary_text"]:
            student["summary_status"] = "Submitted"
        else:
            student["summary_status"] = "Not Submitted"

        return redirect(url_for("faculty_dashboard"))

    return render_template(
        "faculty_review.html",
        user=current_user,
        student=student,
        title="Review Co-op Summary",
    )


# --------------------------------------------------
# Routes: Student (minimal placeholder)
# --------------------------------------------------
@app.route("/student/dashboard")
def student_dashboard():
    current_user = get_current_user()
    if not current_user or current_user["role"] != "student":
        return redirect(url_for("login"))

    # Simple placeholder for now
    return render_template(
        "student_dashboard.html",
        user=current_user,
        title="Student Dashboard",
    )


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=5002)
