# 📝 Notely - Secure Topic-Based Notes

Notely is a simple, secure, and aesthetically pleasing "Topic-Based Notes" web application built with Python Flask and SQLite. It features a modern, minimal UI inspired by Notion, complete with a dark mode toggle and organized workspace.

## ✨ Features

- **Topic-Based Organization:** Create topics (Work, Personal, Ideas) and nest notes within them.
- **Secure Authentication:** User registration and login with hashed passwords (using `werkzeug.security`).
- **Data Isolation:** Users can only access and manage their own notes and topics.
- **Modern UI/UX:**
  - Clean, minimal design with rounded components and soft shadows.
  - Interactive sidebar for topic management.
  - Search functionality to quickly find notes across all topics.
  - **Dark Mode Support** with persistent theme selection.
- **CRUD Operations:** Create, Read, Update, and Delete both notes and topics.
- **Security First:**
  - CSRF Protection (via Flask-WTF).
  - SQL Injection prevention using parameterized queries.
  - Secure session handling.

## 🚀 Tech Stack

- **Backend:** [Python Flask](https://flask.palletsprojects.com/)
- **Database:** [SQLite](https://www.sqlite.org/) (Lightweight & Local)
- **Frontend:** HTML5, CSS3, [Tailwind CSS (CDN)](https://tailwindcss.com/), [Alpine.js (CDN)](https://alpinejs.dev/)
- **Security:** Flask-WTF, Werkzeug Security

## 🛠️ Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/Soutikkk/Notely.git
cd Notely
```

### 2. Install dependencies
It is recommended to use a virtual environment.
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
python app.py
```
The application will be available at `http://127.0.0.1:5000`.

## 📂 File Structure

```text
├── static/
│   ├── script.js      # Theme toggling & UI interactions
│   └── styles.css     # Theme variables & custom layout
├── templates/
│   ├── base.html      # Main layout & navigation
│   ├── dashboard.html # Notes & Topics workspace
│   ├── login.html     # Authentication
│   └── register.html  # Authentication
├── app.py             # Flask routes & logic
├── db.py              # SQLite connection & schema
├── requirements.txt   # Dependencies
└── database.db        # SQLite database (Auto-created)
```

## 🔐 Security Note
For production environments, ensure you change the `secret_key` in `app.py` to a long, random string and use environment variables for sensitive configurations.

---
Built with ❤️ for simple and secure note-taking.
