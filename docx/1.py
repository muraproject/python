from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for, session
import os
import zipfile
import tempfile
from werkzeug.utils import secure_filename
from docx import Document
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Folder untuk menyimpan file
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

# Buat folder jika belum ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Word Find & Replace</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h1, h2 {
            color: #333;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input, textarea, button, select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #007bff;
            color: white;
            cursor: pointer;
            border: none;
        }
        button:hover {
            background-color: #0056b3;
        }
        .btn-danger {
            background-color: #dc3545;
        }
        .btn-danger:hover {
            background-color: #c82333;
        }
        .btn-success {
            background-color: #28a745;
        }
        .btn-success:hover {
            background-color: #218838;
        }
        .replace-pair {
            border: 1px solid #eee;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            background-color: #f8f9fa;
        }
        .replace-pair input {
            margin-bottom: 5px;
        }
        .file-list {
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .alert {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .alert-success {
            background-color: #d4edda;
            border-color: #c3e6cb;
            color: #155724;
        }
        .alert-error {
            background-color: #f8d7da;
            border-color: #f5c6cb;
            color: #721c24;
        }
        .inline-form {
            display: inline-block;
            margin-right: 10px;
        }
        .result-files {
            background-color: #e9ecef;
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .download-link {
            display: inline-block;
            margin: 5px 10px 5px 0;
            padding: 5px 10px;
            background-color: #17a2b8;
            color: white;
            text-decoration: none;
            border-radius: 3px;
        }
        .download-link:hover {
            background-color: #138496;
            text-decoration: none;
            color: white;
        }
    </style>
</head>
<body>
    <h1>Word Find & Replace Tool</h1>
    
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-success">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <!-- Upload Files -->
    <div class="container">
        <h2>1. Upload File Word</h2>
        <form method="post" enctype="multipart/form-data" action="/upload">
            <div class="form-group">
                <label>Pilih File Word (.docx):</label>
                <input type="file" name="files" multiple accept=".docx" required>
            </div>
            <button type="submit">Upload File</button>
        </form>
        
        {% if uploaded_files %}
        <div class="file-list">
            <h3>File yang sudah diupload:</h3>
            {% for file in uploaded_files %}
                <div>
                    📄 {{ file }}
                    <form method="post" action="/delete_file/{{ file }}" class="inline-form">
                        <button type="submit" class="btn-danger" onclick="return confirm('Hapus file ini?')">Hapus</button>
                    </form>
                </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>

    <!-- Find & Replace Rules -->
    <div class="container">
        <h2>2. Atur Find & Replace</h2>
        
        <!-- Add new rule -->
        <form method="post" action="/add_rule">
            <div class="replace-pair">
                <label>Find Text (cari):</label>
                <input type="text" name="find_text" required>
                <label>Replace Text (ganti dengan):</label>
                <input type="text" name="replace_text" required>
                <button type="submit" class="btn-success">Tambah Rule</button>
            </div>
        </form>

        <!-- Existing rules -->
        {% if replace_rules %}
        <h3>Rules yang sudah dibuat:</h3>
        {% for i, rule in replace_rules %}
        <form method="post" action="/update_rule/{{ i }}">
            <div class="replace-pair">
                <label>Find Text:</label>
                <input type="text" name="find_text" value="{{ rule.find_text }}" required>
                <label>Replace Text:</label>
                <input type="text" name="replace_text" value="{{ rule.replace_text }}" required>
                <button type="submit">Update</button>
                <form method="post" action="/delete_rule/{{ i }}" class="inline-form">
                    <button type="submit" class="btn-danger" onclick="return confirm('Hapus rule ini?')">Hapus</button>
                </form>
            </div>
        </form>
        {% endfor %}
        {% endif %}
    </div>

    <!-- Process Files -->
    {% if uploaded_files and replace_rules %}
    <div class="container">
        <h2>3. Jalankan Find & Replace</h2>
        <form method="post" action="/process">
            <button type="submit" class="btn-success">🔄 Proses Semua File</button>
        </form>
    </div>
    {% endif %}

    <!-- Download Results -->
    {% if processed_files %}
    <div class="container">
        <h2>4. Download Hasil</h2>
        <div class="result-files">
            <h3>File yang sudah diproses:</h3>
            {% for file in processed_files %}
                <a href="/download/{{ file }}" class="download-link">📥 {{ file }}</a>
            {% endfor %}
            <br><br>
            <a href="/download_all" class="download-link btn-success">📦 Download Semua (ZIP)</a>
        </div>
    </div>
    {% endif %}

</body>
</html>
'''

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'docx'

def find_replace_in_docx(file_path, rules):
    """Find and replace text in a Word document"""
    try:
        doc = Document(file_path)
        
        # Replace in paragraphs
        for paragraph in doc.paragraphs:
            for rule in rules:
                if rule['find_text'] in paragraph.text:
                    paragraph.text = paragraph.text.replace(rule['find_text'], rule['replace_text'])
        
        # Replace in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for rule in rules:
                        if rule['find_text'] in cell.text:
                            cell.text = cell.text.replace(rule['find_text'], rule['replace_text'])
        
        return doc
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return None

@app.route('/')
def index():
    # Get session data
    uploaded_files = session.get('uploaded_files', [])
    replace_rules = session.get('replace_rules', [])
    processed_files = session.get('processed_files', [])
    
    # Add index to rules for template
    indexed_rules = [(i, rule) for i, rule in enumerate(replace_rules)]
    
    return render_template_string(HTML_TEMPLATE, 
                                uploaded_files=uploaded_files,
                                replace_rules=indexed_rules,
                                processed_files=processed_files)

@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')
    uploaded_files = session.get('uploaded_files', [])
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            uploaded_files.append(unique_filename)
    
    session['uploaded_files'] = uploaded_files
    flash('File berhasil diupload!')
    return redirect(url_for('index'))

@app.route('/delete_file/<filename>', methods=['POST'])
def delete_file(filename):
    uploaded_files = session.get('uploaded_files', [])
    if filename in uploaded_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        uploaded_files.remove(filename)
        session['uploaded_files'] = uploaded_files
        flash('File berhasil dihapus!')
    return redirect(url_for('index'))

@app.route('/add_rule', methods=['POST'])
def add_rule():
    find_text = request.form.get('find_text')
    replace_text = request.form.get('replace_text')
    
    if find_text and replace_text:
        replace_rules = session.get('replace_rules', [])
        replace_rules.append({
            'find_text': find_text,
            'replace_text': replace_text
        })
        session['replace_rules'] = replace_rules
        flash('Rule berhasil ditambahkan!')
    
    return redirect(url_for('index'))

@app.route('/update_rule/<int:index>', methods=['POST'])
def update_rule(index):
    find_text = request.form.get('find_text')
    replace_text = request.form.get('replace_text')
    
    replace_rules = session.get('replace_rules', [])
    if 0 <= index < len(replace_rules):
        replace_rules[index] = {
            'find_text': find_text,
            'replace_text': replace_text
        }
        session['replace_rules'] = replace_rules
        flash('Rule berhasil diupdate!')
    
    return redirect(url_for('index'))

@app.route('/delete_rule/<int:index>', methods=['POST'])
def delete_rule(index):
    replace_rules = session.get('replace_rules', [])
    if 0 <= index < len(replace_rules):
        replace_rules.pop(index)
        session['replace_rules'] = replace_rules
        flash('Rule berhasil dihapus!')
    
    return redirect(url_for('index'))

@app.route('/process', methods=['POST'])
def process_files():
    uploaded_files = session.get('uploaded_files', [])
    replace_rules = session.get('replace_rules', [])
    
    if not uploaded_files or not replace_rules:
        flash('Harap upload file dan buat rule terlebih dahulu!')
        return redirect(url_for('index'))
    
    processed_files = []
    
    for filename in uploaded_files:
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        output_filename = filename  # Gunakan nama file asli
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Process the document
        processed_doc = find_replace_in_docx(input_path, replace_rules)
        if processed_doc:
            processed_doc.save(output_path)
            processed_files.append(output_filename)
    
    session['processed_files'] = processed_files
    flash(f'Berhasil memproses {len(processed_files)} file!')
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File tidak ditemukan!')
        return redirect(url_for('index'))

@app.route('/download_all')
def download_all():
    processed_files = session.get('processed_files', [])
    
    if not processed_files:
        flash('Tidak ada file untuk didownload!')
        return redirect(url_for('index'))
    
    # Create temporary zip file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    
    with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
        for filename in processed_files:
            file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
            if os.path.exists(file_path):
                zip_file.write(file_path, filename)
    
    return send_file(temp_zip.name, 
                    as_attachment=True, 
                    download_name='processed_files.zip',
                    mimetype='application/zip')

if __name__ == '__main__':
    print("Starting Flask Word Find & Replace App...")
    print("Buka browser dan kunjungi: http://localhost:5000")
    print("\nPastikan Anda sudah install library berikut:")
    print("pip install flask python-docx")
    
    app.run(debug=True, host='0.0.0.0', port=5000)