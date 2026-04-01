from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db, close_connection
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = 'very_secure_secret_key_for_notely_app_change_in_production'
csrf = CSRFProtect(app)

# Initialize Database when the app starts
with app.app_context():
    init_db(app)

# Register teardown function to close DB after request
app.teardown_appcontext(close_connection)

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

def login_required(view):
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return view(**kwargs)
    wrapped_view.__name__ = view.__name__
    return wrapped_view

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                flash('Successfully registered! Please log in.', 'success')
                return redirect(url_for('login'))

        flash(error, 'error')

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password_hash'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))

        flash(error, 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/', methods=('GET',))
@login_required
def dashboard():
    db = get_db()
    
    # Handle Search feature via query param ?q=
    search_query = request.args.get('q', '')
    
    topics = db.execute(
        'SELECT * FROM topics WHERE user_id = ? ORDER BY name COLLATE NOCASE',
        (g.user['id'],)
    ).fetchall()

    # Get selected topic from args to display notes for it. If search is active, show matching in all topics
    selected_topic_id = request.args.get('topic_id', type=int)
    notes = []
    selected_topic = None

    if search_query:
        # Search all notes owned by the user
        notes = db.execute('''
            SELECT n.*, t.name as topic_name 
            FROM notes n 
            JOIN topics t ON n.topic_id = t.id 
            WHERE t.user_id = ? AND (n.title LIKE ? OR n.content LIKE ?)
            ORDER BY n.created_at DESC
        ''', (g.user['id'], f'%{search_query}%', f'%{search_query}%')).fetchall()
    elif topics:
        # Select first topic if none is selected
        if not selected_topic_id:
            selected_topic_id = topics[0]['id']
        
        selected_topic = next((t for t in topics if t['id'] == selected_topic_id), None)
        
        if selected_topic:
            notes = db.execute(
                'SELECT * FROM notes WHERE topic_id = ? ORDER BY created_at DESC',
                (selected_topic['id'],)
            ).fetchall()
        else:
            selected_topic_id = None

    return render_template(
        'dashboard.html', 
        topics=topics, 
        notes=notes, 
        selected_topic_id=selected_topic_id, 
        selected_topic=selected_topic,
        search_query=search_query
    )


@app.route('/topic/create', methods=('POST',))
@login_required
def create_topic():
    name = request.form['name']
    if name:
        db = get_db()
        db.execute(
            'INSERT INTO topics (user_id, name) VALUES (?, ?)',
            (g.user['id'], name)
        )
        db.commit()
        flash(f'Topic "{name}" created successfully.', 'success')
        
        # Get the new topic ID to redirect to it
        new_topic_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return redirect(url_for('dashboard', topic_id=new_topic_id))

    flash('Topic name cannot be empty.', 'error')
    return redirect(url_for('dashboard'))


@app.route('/note/add', methods=('POST',))
@login_required
def add_note():
    topic_id = request.form['topic_id']
    title = request.form['title']
    content = request.form['content']
    
    # Basic Authorization check for the topic ownership
    db = get_db()
    topic = db.execute('SELECT user_id FROM topics WHERE id = ?', (topic_id,)).fetchone()
    if not topic or topic['user_id'] != g.user['id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('dashboard'))

    if title:
        db.execute(
            'INSERT INTO notes (topic_id, title, content) VALUES (?, ?, ?)',
            (topic_id, title, content)
        )
        db.commit()
    else:
        flash('Note title is required.', 'error')

    return redirect(url_for('dashboard', topic_id=topic_id))


@app.route('/note/edit/<int:id>', methods=('POST',))
@login_required
def edit_note(id):
    title = request.form['title']
    content = request.form['content']

    db = get_db()
    
    # Check ownership
    note = db.execute('''
        SELECT n.topic_id, t.user_id 
        FROM notes n 
        JOIN topics t ON n.topic_id = t.id 
        WHERE n.id = ?
    ''', (id,)).fetchone()
    
    if not note or note['user_id'] != g.user['id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('dashboard'))
        
    if title:
        db.execute(
            'UPDATE notes SET title = ?, content = ? WHERE id = ?',
            (title, content, id)
        )
        db.commit()
        flash('Note updated successfully.', 'success')
    else:
        flash('Note title cannot be empty.', 'error')

    return redirect(url_for('dashboard', topic_id=note['topic_id']))


@app.route('/note/delete/<int:id>', methods=('POST',))
@login_required
def delete_note(id):
    db = get_db()
    
    # Check ownership
    note = db.execute('''
        SELECT n.topic_id, t.user_id 
        FROM notes n 
        JOIN topics t ON n.topic_id = t.id 
        WHERE n.id = ?
    ''', (id,)).fetchone()
    
    if not note or note['user_id'] != g.user['id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('dashboard'))
        
    db.execute('DELETE FROM notes WHERE id = ?', (id,))
    db.commit()
    flash('Note deleted.', 'success')
    
    return redirect(url_for('dashboard', topic_id=note['topic_id']))


@app.route('/topic/delete/<int:id>', methods=('POST',))
@login_required
def delete_topic(id):
    db = get_db()
    
    # Check ownership
    topic = db.execute('SELECT user_id FROM topics WHERE id = ?', (id,)).fetchone()
    if not topic or topic['user_id'] != g.user['id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('dashboard'))
        
    db.execute('DELETE FROM topics WHERE id = ?', (id,))
    db.commit()
    flash('Topic deleted.', 'success')
    
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
