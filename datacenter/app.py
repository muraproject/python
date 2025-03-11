from flask import Flask, request, render_template, send_from_directory, redirect, url_for, jsonify
import os
import shutil
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

# Konfigurasi
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'html', 'css', 'js', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max-limit
app.config['SECRET_KEY'] = 'dev-key-please-change'

# Buat folder uploads jika belum ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    elif ext in ['doc', 'docx']:
        return 'document'
    elif ext in ['xls', 'xlsx']:
        return 'spreadsheet'
    elif ext in ['pdf']:
        return 'pdf'
    elif ext in ['zip', 'rar']:
        return 'archive'
    return 'other'

def get_file_info(path, filename):
    stats = os.stat(path)
    return {
        'name': filename,
        'size': stats.st_size,
        'formatted_size': format_size(stats.st_size),
        'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'type': get_file_type(filename),
        'path': os.path.join(UPLOAD_FOLDER, filename)
    }

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(path):
            files.append(get_file_info(path, filename))
    return jsonify(files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        return jsonify(get_file_info(path, filename))
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True})
    return jsonify({'error': 'File not found'}), 404

@app.route('/rename', methods=['POST'])
def rename_file():
    old_name = request.form.get('old_name')
    new_name = secure_filename(request.form.get('new_name'))
    
    if not old_name or not new_name:
        return jsonify({'error': 'Missing filename'}), 400
    
    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_name)
    new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_name)
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        return jsonify(get_file_info(new_path, new_name))
    return jsonify({'error': 'File not found'}), 404

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/preview/<filename>')
def preview_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/search')
def search_files():
    query = request.args.get('q', '').lower()
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if query in filename.lower():
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(path):
                files.append(get_file_info(path, filename))
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)