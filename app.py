import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'imo_real_chat_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Faýllar saklanjak papkasy
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- SQLite Bazasy ---
def init_db():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            color TEXT DEFAULT '#38bdf8'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            sender_color TEXT DEFAULT '#38bdf8',
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def get_chat_history(user1, user2):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    if user2 == 'Gizlin Topar':
        cursor.execute(
            'SELECT sender, receiver, message, msg_type, sender_color, timestamp FROM messages WHERE receiver = ? ORDER BY id ASC',
            ('Gizlin Topar',))
    else:
        cursor.execute('''
            SELECT sender, receiver, message, msg_type, sender_color, timestamp FROM messages 
            WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
            ORDER BY id ASC
        ''', (user1, user2, user2, user1))
    rows = cursor.fetchall()
    conn.close()
    return [
        {'sender': r[0], 'receiver': r[1], 'message': r[2], 'msg_type': r[3], 'sender_color': r[4], 'timestamp': r[5]}
        for r in rows]


def save_message(sender, receiver, message, msg_type, color, timestamp):
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO messages (sender, receiver, message, msg_type, sender_color, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
        (sender, receiver, message, msg_type, color, timestamp))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, color FROM users ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [{'username': r[0], 'color': r[1]} for r in rows]


@app.route('/')
def index():
    return render_template('chat.html')


# --- Faýl Ýüklemek üçin REST API ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return {'success': False, 'message': 'Faýl tapylmady'}, 400

    file = request.files['file']
    if file.filename == '':
        return {'success': False, 'message': 'Faýl saýlanmady'}, 400

    filename = secure_filename(file.filename)
    # Faýlyň adyny täýtmezlik üçin wagt goşýarys
    timestamp_prefix = datetime.now().strftime("%Y%m%d%H%M%S_")
    saved_filename = timestamp_prefix + filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(file_path)

    # Faýl tipini kesgitlemek
    ext = filename.split('.')[-1].lower()
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        file_type = 'image'
    elif ext in ['mp4', 'webm', 'ogg', 'mov']:
        file_type = 'video'
    elif ext in ['mp3', 'wav', 'm4a']:
        file_type = 'audio'
    else:
        file_type = 'file'

    file_url = f"/static/uploads/{saved_filename}"
    return {'success': True, 'url': file_url, 'file_type': file_type, 'filename': filename}


# --- WebSocket ---
@socketio.on('register_or_login')
def handle_login(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    color = data.get('color', '#38bdf8')

    if not username or not password:
        emit('auth_result', {'success': False, 'message': 'At we parol ýazyň!'})
        return

    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password, color) VALUES (?, ?, ?)', (username, password, color))
    except sqlite3.IntegrityError:
        cursor.execute('UPDATE users SET password = ?, color = ? WHERE username = ?', (password, color, username))

    conn.commit()
    conn.close()

    emit('auth_result', {'success': True, 'username': username, 'color': color})
    emit('update_users_list', get_all_users(), broadcast=True)


@socketio.on('load_users')
def handle_load_users():
    emit('update_users_list', get_all_users())


@socketio.on('load_history')
def handle_load_history(data):
    my_name = data.get('my_name')
    active_chat = data.get('active_chat')
    if my_name and active_chat:
        history = get_chat_history(my_name, active_chat)
        emit('chat_history', history)


@socketio.on('send_message')
def handle_send_msg(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '').strip()
    msg_type = data.get('msg_type', 'text')
    color = data.get('color', '#38bdf8')

    if text and sender and receiver:
        now = datetime.now().strftime("%H:%M")
        save_message(sender, receiver, text, msg_type, color, now)

        # Hat ugradylandan soň täze hat maglumatyny ähli tarapa ýaýratmak
        emit('receive_message', {
            'sender': sender,
            'receiver': receiver,
            'message': text,
            'msg_type': msg_type,
            'sender_color': color,
            'timestamp': now
        }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
