import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    g,
)

from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db, close_connection


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

# Use environment variable in production.
# Falls back to a development key for local testing.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-this-in-production"
)

# Enable CSRF protection for POST forms
csrf = CSRFProtect(app)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

with app.app_context():
    init_db(app)


# Close database connection after every request
app.teardown_appcontext(close_connection)


# ============================================================
# LOAD LOGGED-IN USER
# ============================================================

@app.before_request
def load_logged_in_user():
    """
    Load the currently logged-in user before every request.
    The user is stored in Flask's g object.
    """

    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
        return

    g.user = get_db().execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================

def login_required(view):
    """
    Protect routes that require authentication.
    """

    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))

        return view(**kwargs)

    return wrapped_view


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=("GET", "POST"))
def register():

    # Already logged in
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        error = None

        # -----------------------------
        # Validation
        # -----------------------------

        if not username:
            error = "Username is required."

        elif not password:
            error = "Password is required."

        elif len(username) < 3:
            error = "Username must be at least 3 characters long."

        elif len(password) < 6:
            error = "Password must be at least 6 characters long."

        # -----------------------------
        # Create User
        # -----------------------------

        if error is None:

            try:
                db.execute(
                    """
                    INSERT INTO users (username, password_hash)
                    VALUES (?, ?)
                    """,
                    (
                        username,
                        generate_password_hash(password),
                    ),
                )

                db.commit()

            except sqlite3.IntegrityError:
                error = f"User '{username}' is already registered."

            else:
                flash(
                    "Successfully registered! Please log in.",
                    "success"
                )

                return redirect(url_for("login"))

        flash(error, "error")

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=("GET", "POST"))
def login():

    # Already logged in
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        error = None

        # Find user
        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        # -----------------------------
        # Validate Login
        # -----------------------------

        if user is None:
            error = "Incorrect username."

        elif not check_password_hash(
            user["password_hash"],
            password
        ):
            error = "Incorrect password."

        # -----------------------------
        # Successful Login
        # -----------------------------

        if error is None:

            # Clear old session
            session.clear()

            # Store user ID
            session["user_id"] = user["id"]

            flash(
                "Logged in successfully!",
                "success"
            )

            return redirect(url_for("dashboard"))

        flash(error, "error")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/", methods=("GET",))
@login_required
def dashboard():

    db = get_db()

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    search_query = request.args.get("q", "").strip()

    # --------------------------------------------------------
    # GET USER'S TOPICS
    # --------------------------------------------------------

    topics = db.execute(
        """
        SELECT *
        FROM topics
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE
        """,
        (g.user["id"],),
    ).fetchall()

    # --------------------------------------------------------
    # SELECTED TOPIC
    # --------------------------------------------------------

    selected_topic_id = request.args.get(
        "topic_id",
        type=int
    )

    notes = []
    selected_topic = None

    # --------------------------------------------------------
    # SEARCH ALL NOTES
    # --------------------------------------------------------

    if search_query:

        search_pattern = f"%{search_query}%"

        notes = db.execute(
            """
            SELECT
                n.*,
                t.name AS topic_name
            FROM notes AS n
            JOIN topics AS t
                ON n.topic_id = t.id
            WHERE
                t.user_id = ?
                AND (
                    n.title LIKE ?
                    OR n.content LIKE ?
                )
            ORDER BY n.created_at DESC
            """,
            (
                g.user["id"],
                search_pattern,
                search_pattern,
            ),
        ).fetchall()

    # --------------------------------------------------------
    # DISPLAY NOTES FROM SELECTED TOPIC
    # --------------------------------------------------------

    elif topics:

        # If no topic selected,
        # automatically select the first topic.
        if selected_topic_id is None:
            selected_topic_id = topics[0]["id"]

        # Find selected topic from user's topics
        selected_topic = next(
            (
                topic
                for topic in topics
                if topic["id"] == selected_topic_id
            ),
            None,
        )

        # Make sure the topic belongs to the current user
        if selected_topic:

            notes = db.execute(
                """
                SELECT *
                FROM notes
                WHERE topic_id = ?
                ORDER BY created_at DESC
                """,
                (selected_topic["id"],),
            ).fetchall()

        else:
            selected_topic_id = None

    # --------------------------------------------------------
    # RENDER DASHBOARD
    # --------------------------------------------------------

    return render_template(
        "dashboard.html",
        topics=topics,
        notes=notes,
        selected_topic_id=selected_topic_id,
        selected_topic=selected_topic,
        search_query=search_query,
    )


# ============================================================
# CREATE TOPIC
# ============================================================

@app.route("/topic/create", methods=("POST",))
@login_required
def create_topic():

    name = request.form.get("name", "").strip()

    if not name:
        flash(
            "Topic name cannot be empty.",
            "error"
        )

        return redirect(url_for("dashboard"))

    db = get_db()

    try:

        cursor = db.execute(
            """
            INSERT INTO topics (user_id, name)
            VALUES (?, ?)
            """,
            (
                g.user["id"],
                name,
            ),
        )

        db.commit()

        # Get newly created topic ID
        new_topic_id = cursor.lastrowid

    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            "A topic with that name already exists.",
            "error"
        )

        return redirect(url_for("dashboard"))

    flash(
        f'Topic "{name}" created successfully.',
        "success"
    )

    return redirect(
        url_for(
            "dashboard",
            topic_id=new_topic_id
        )
    )


# ============================================================
# ADD NOTE
# ============================================================

@app.route("/note/add", methods=("POST",))
@login_required
def add_note():

    topic_id = request.form.get("topic_id", "").strip()
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()

    db = get_db()

    # --------------------------------------------------------
    # Validate topic ID
    # --------------------------------------------------------

    if not topic_id.isdigit():

        flash(
            "Invalid topic.",
            "error"
        )

        return redirect(url_for("dashboard"))

    topic_id = int(topic_id)

    # --------------------------------------------------------
    # Check topic ownership
    # --------------------------------------------------------

    topic = db.execute(
        """
        SELECT user_id
        FROM topics
        WHERE id = ?
        """,
        (topic_id,),
    ).fetchone()

    if not topic or topic["user_id"] != g.user["id"]:

        flash(
            "Unauthorized action.",
            "error"
        )

        return redirect(url_for("dashboard"))

    # --------------------------------------------------------
    # Validate title
    # --------------------------------------------------------

    if not title:

        flash(
            "Note title is required.",
            "error"
        )

        return redirect(
            url_for(
                "dashboard",
                topic_id=topic_id
            )
        )

    # --------------------------------------------------------
    # Insert Note
    # --------------------------------------------------------

    db.execute(
        """
        INSERT INTO notes (topic_id, title, content)
        VALUES (?, ?, ?)
        """,
        (
            topic_id,
            title,
            content,
        ),
    )

    db.commit()

    flash(
        "Note added successfully.",
        "success"
    )

    return redirect(
        url_for(
            "dashboard",
            topic_id=topic_id
        )
    )


# ============================================================
# EDIT NOTE
# ============================================================

@app.route("/note/edit/<int:id>", methods=("POST",))
@login_required
def edit_note(id):

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()

    db = get_db()

    # --------------------------------------------------------
    # Check note ownership
    # --------------------------------------------------------

    note = db.execute(
        """
        SELECT
            n.topic_id,
            t.user_id
        FROM notes AS n
        JOIN topics AS t
            ON n.topic_id = t.id
        WHERE n.id = ?
        """,
        (id,),
    ).fetchone()

    if not note or note["user_id"] != g.user["id"]:

        flash(
            "Unauthorized action.",
            "error"
        )

        return redirect(url_for("dashboard"))

    # --------------------------------------------------------
    # Validate title
    # --------------------------------------------------------

    if not title:

        flash(
            "Note title cannot be empty.",
            "error"
        )

        return redirect(
            url_for(
                "dashboard",
                topic_id=note["topic_id"]
            )
        )

    # --------------------------------------------------------
    # Update note
    # --------------------------------------------------------

    db.execute(
        """
        UPDATE notes
        SET
            title = ?,
            content = ?
        WHERE id = ?
        """,
        (
            title,
            content,
            id,
        ),
    )

    db.commit()

    flash(
        "Note updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "dashboard",
            topic_id=note["topic_id"]
        )
    )


# ============================================================
# DELETE NOTE
# ============================================================

@app.route("/note/delete/<int:id>", methods=("POST",))
@login_required
def delete_note(id):

    db = get_db()

    # --------------------------------------------------------
    # Check note ownership
    # --------------------------------------------------------

    note = db.execute(
        """
        SELECT
            n.topic_id,
            t.user_id
        FROM notes AS n
        JOIN topics AS t
            ON n.topic_id = t.id
        WHERE n.id = ?
        """,
        (id,),
    ).fetchone()

    if not note or note["user_id"] != g.user["id"]:

        flash(
            "Unauthorized action.",
            "error"
        )

        return redirect(url_for("dashboard"))

    topic_id = note["topic_id"]

    # --------------------------------------------------------
    # Delete note
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM notes
        WHERE id = ?
        """,
        (id,),
    )

    db.commit()

    flash(
        "Note deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "dashboard",
            topic_id=topic_id
        )
    )


# ============================================================
# DELETE TOPIC
# ============================================================

@app.route("/topic/delete/<int:id>", methods=("POST",))
@login_required
def delete_topic(id):

    db = get_db()

    # --------------------------------------------------------
    # Check topic ownership
    # --------------------------------------------------------

    topic = db.execute(
        """
        SELECT user_id
        FROM topics
        WHERE id = ?
        """,
        (id,),
    ).fetchone()

    if not topic or topic["user_id"] != g.user["id"]:

        flash(
            "Unauthorized action.",
            "error"
        )

        return redirect(url_for("dashboard"))

    # --------------------------------------------------------
    # Delete topic
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM topics
        WHERE id = ?
        """,
        (id,),
    )

    db.commit()

    flash(
        "Topic deleted successfully.",
        "success"
    )

    return redirect(url_for("dashboard"))


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
    )
