import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", "super-secret-key")
bcrypt = Bcrypt(app)

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "registration"),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation checks
        if not name:
            flash("Name is required", "error")
        elif not email:
            flash("Email is required", "error")
        elif not password:
            flash("Password is required", "error")
        elif not confirm_password:
            flash("Confirm password is required", "error")
        elif password != confirm_password:
            flash("Passwords do not match", "error")
        else:
            pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    sql = "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s);"
                    cursor.execute(sql, (email, name, pw_hash))
                    user_id = cursor.lastrowid
                conn.commit()
                session["user_id"] = user_id
                session["name"] = name
                return redirect(url_for("todos"))
            except pymysql.err.IntegrityError:
                flash("Email Already Exists", "error")
            finally:
                conn.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email:
            flash("Email is required", "error")
        elif not password:
            flash("Password is required", "error")
        else:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    sql = "SELECT user_id, name, password_hash FROM users WHERE email = %s;"
                    cursor.execute(sql, (email,))
                    user = cursor.fetchone()

                if user and bcrypt.check_password_hash(user["password_hash"], password):
                    session["user_id"] = user["user_id"]
                    session["name"] = user["name"]
                    return redirect(url_for("todos"))
                else:
                    flash("Invalid email or password", "error")
            finally:
                conn.close()

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/todos")
def todos():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get search and filter parameters from the URL
    search_query = request.args.get("search", "").strip()
    filter_status = request.args.get("filter", "all")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Base query
            sql = "SELECT todo_id, title, is_done, created_at FROM todos WHERE user_id = %s"
            params = [session["user_id"]]

            # Apply open/done filters
            if filter_status == "open":
                sql += " AND is_done = 0"
            elif filter_status == "done":
                sql += " AND is_done = 1"

            # Apply search filter
            if search_query:
                sql += " AND title LIKE %s"
                params.append(f"%{search_query}%")

            sql += " ORDER BY todo_id DESC;"
            
            cursor.execute(sql, tuple(params))
            todo_list = cursor.fetchall()
    finally:
        conn.close()

    return render_template(
        "todos.html", 
        todos=todo_list, 
        user_name=session.get("name"),
        current_filter=filter_status,
        search_query=search_query
    )

@app.route("/todos/add", methods=["POST"])
def add_todo():
    if "user_id" not in session:
        return redirect(url_for("login"))

    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required (an empty title or only spaces)", "error")
    elif len(title) > 200:
        flash("Title is too long (200 characters at most)", "error")
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "INSERT INTO todos (user_id, title) VALUES (%s, %s);"
                cursor.execute(sql, (session["user_id"], title))
            conn.commit()
        finally:
            conn.close()

    return redirect(url_for("todos"))

@app.route("/todos/<int:todo_id>/edit", methods=["POST"])
def edit_todo(todo_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required (an empty title or only spaces)", "error")
    elif len(title) > 200:
        flash("Title is too long (200 characters at most)", "error")
    else:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE todos SET title = %s WHERE todo_id = %s AND user_id = %s;"
                cursor.execute(sql, (title, todo_id, session["user_id"]))
            conn.commit()
        finally:
            conn.close()

    return redirect(url_for("todos"))

@app.route("/todos/<int:todo_id>/toggle", methods=["POST"])
def toggle_todo(todo_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    new_status = request.form.get("is_done", "0")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE todos SET is_done = %s WHERE todo_id = %s AND user_id = %s;"
            cursor.execute(sql, (new_status, todo_id, session["user_id"]))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("todos"))

@app.route("/todos/<int:todo_id>/delete", methods=["POST"])
def delete_todo(todo_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM todos WHERE todo_id = %s AND user_id = %s;"
            cursor.execute(sql, (todo_id, session["user_id"]))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("todos"))

if __name__ == "__main__":
    app.run(debug=True)