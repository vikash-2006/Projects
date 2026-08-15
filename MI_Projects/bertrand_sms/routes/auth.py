from flask import Blueprint, request, jsonify, redirect, url_for, render_template, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import execute_query

auth_bp = Blueprint('auth', __name__)

class User:
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('login.html')

    data = request.get_json(silent=True) or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        if request.is_json:
            return jsonify({'error': 'Username and password are required'}), 400
        flash('Username and password are required', 'danger')
        return render_template('login.html')

    user_row = execute_query("SELECT * FROM users WHERE username = %s", (username,), fetch_one=True)
    if user_row and check_password_hash(user_row['password'], password):
        user_obj = User(user_row['id'], user_row['username'], user_row['role'])
        login_user(user_obj)
        if request.is_json:
            return jsonify({'success': True, 'redirect': '/'})
        return redirect(url_for('index'))

    if request.is_json:
        return jsonify({'error': 'Invalid username or password'}), 401
    flash('Invalid username or password', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/auth/me')
def me():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'role': current_user.role
            }
        })
    return jsonify({'authenticated': False}), 200
