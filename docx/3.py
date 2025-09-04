from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for, session
import os
import zipfile
import tempfile
import json
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import uuid
import random
from datetime import datetime

# PDF libraries
try:
    from docx2pdf import convert as docx2pdf_convert
    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False

# Alternative PDF conversion methods
try:
    import pythoncom
    PYTHONCOM_AVAILABLE = True
except ImportError:
    PYTHONCOM_AVAILABLE = False

try:
    import subprocess
    SUBPROCESS_AVAILABLE = True
except ImportError:
    SUBPROCESS_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from PyPDF2 import PdfReader, PdfWriter
    import fitz  # PyMuPDF
    PDF_PROCESSING_AVAILABLE = True
except ImportError:
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        import fitz  # PyMuPDF
        PDF_PROCESSING_AVAILABLE = True
    except ImportError:
        try:
            import fitz  # PyMuPDF only
            PDF_PROCESSING_AVAILABLE = True
        except ImportError:
            PDF_PROCESSING_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Folder untuk menyimpan file
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
IMAGE_FOLDER = 'images'
PDF_FOLDER = 'pdf_output'
SETTINGS_FILE = 'app_settings.json'

# Buat folder jika belum ada
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, IMAGE_FOLDER, PDF_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER

def save_settings():
    """Save current session settings to JSON file"""
    try:
        settings = {
            'replace_rules': session.get('replace_rules', []),
            'image_rules': session.get('image_rules', []),
            'uploaded_images': session.get('uploaded_images', []),
            'last_updated': datetime.now().isoformat()
        }
        
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Settings saved to {SETTINGS_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving settings: {str(e)}")
        return False

def load_settings():
    """Load settings from JSON file to session"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            session['replace_rules'] = settings.get('replace_rules', [])
            session['image_rules'] = settings.get('image_rules', [])
            session['uploaded_images'] = settings.get('uploaded_images', [])
            
            print(f"✅ Settings loaded from {SETTINGS_FILE}")
            return True
    except Exception as e:
        print(f"❌ Error loading settings: {str(e)}")
    return False

def auto_save():
    """Auto save settings after any change"""
    save_settings()

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Word to PDF with Positioned Images</title>
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
        .replace-pair, .image-rule {
            border: 1px solid #eee;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
            background-color: #f8f9fa;
        }
        .replace-pair input, .image-rule input, .image-rule select {
            margin-bottom: 8px;
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
        .position-inputs {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .status-info {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            color: #0c5460;
        }
    </style>
</head>
<body>
    <h1>📄➡️📋 Word to PDF with Positioned Images</h1>
    
    <!-- Settings Management -->
    <div class="container">
        <h2>⚙️ Kelola Settingan</h2>
        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px;">
            <form method="post" action="/save_settings" class="inline-form">
                <button type="submit" class="btn-success">💾 Simpan Settingan</button>
            </form>
            
            <form method="post" action="/load_settings" class="inline-form">
                <button type="submit">📥 Muat Settingan</button>
            </form>
            
            <a href="/export_settings" class="download-link">📤 Export Settingan</a>
            
            <form method="post" enctype="multipart/form-data" action="/import_settings" class="inline-form">
                <input type="file" name="settings_file" accept=".json" style="display: inline; width: auto; margin-right: 5px;">
                <button type="submit">📥 Import Settingan</button>
            </form>
        </div>
        <p><small>💡 Settingan otomatis tersimpan di file <code>app_settings.json</code> agar tidak hilang saat buka di komputer lain</small></p>
    </div>
    
    <div class="status-info">
        <strong>Status Libraries & Conversion Methods:</strong><br>
        {% if docx2pdf_available %}
            ✅ docx2pdf: Tersedia (Method 1)<br>
        {% else %}
            ❌ docx2pdf: Tidak tersedia (install: pip install docx2pdf)<br>
        {% endif %}
        
        ✅ LibreOffice: Akan dicoba otomatis (Method 2)<br>
        ✅ ReportLab Fallback: Tersedia (Method 3)<br>
        
        {% if pdf_processing_available %}
            ✅ PDF image processing: Tersedia
        {% else %}
            ❌ PDF image processing: Tidak tersedia (install: pip install reportlab PyMuPDF)
        {% endif %}
        
        <br><strong>💡 Tips:</strong> Jika error COM, install LibreOffice atau gunakan method fallback
    </div>
    
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
        <h2>2. Atur Find & Replace Text</h2>
        
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

    <!-- Image Rules -->
    <div class="container">
        <h2>3. Atur Posisi Gambar di PDF</h2>
        
        <!-- Upload Images -->
        <form method="post" enctype="multipart/form-data" action="/upload_images">
            <div class="form-group">
                <label>Upload Gambar (JPG, PNG, GIF):</label>
                <input type="file" name="images" multiple accept=".jpg,.jpeg,.png,.gif">
            </div>
            <button type="submit">Upload Gambar</button>
        </form>
        
        {% if uploaded_images %}
        <div class="file-list">
            <h3>Gambar yang tersedia:</h3>
            {% for image in uploaded_images %}
                <div>
                    🖼️ {{ image }}
                    <form method="post" action="/delete_image/{{ image }}" class="inline-form">
                        <button type="submit" class="btn-danger" onclick="return confirm('Hapus gambar ini?')">Hapus</button>
                    </form>
                </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <!-- Add new image rule -->
        <form method="post" action="/add_image_rule">
            <div class="image-rule">
                <h4>Tambah Rule Gambar Baru:</h4>
                <label>Text Target untuk Pencarian Posisi:</label>
                <input type="text" name="target_text" placeholder="contoh: endah" required>
                
                <label>Pilih Gambar:</label>
                <select name="image_filename" required>
                    <option value="">-- Pilih Gambar --</option>
                    {% for image in uploaded_images %}
                        <option value="{{ image }}">{{ image }}</option>
                    {% endfor %}
                </select>
                
                <div class="position-inputs">
                    <div>
                        <label>Offset X (mm dari text target - positif=kanan, negatif=kiri):</label>
                        <input type="number" name="offset_x" value="0" step="0.5" min="-100" max="100" required>
                    </div>
                    <div>
                        <label>Offset Y (mm dari text target - positif=bawah, negatif=atas):</label>
                        <input type="number" name="offset_y" value="-10" step="0.5" min="-100" max="100" required>
                    </div>
                </div>
                
                <label>Lebar Gambar (mm):</label>
                <input type="number" name="width" value="20" min="5" max="100" step="0.5" required>
                
                <label>Tinggi Gambar (mm):</label>
                <input type="number" name="height" value="20" min="5" max="100" step="0.5" required>
                
                <button type="submit" class="btn-success">Tambah Image Rule</button>
            </div>
        </form>

        <!-- Existing image rules -->
        {% if image_rules %}
        <h3>Image Rules yang sudah dibuat:</h3>
        {% for i, rule in image_rules %}
        <form method="post" action="/update_image_rule/{{ i }}">
            <div class="image-rule">
                <h4>Image Rule #{{ i + 1 }} - Target: "{{ rule.target_text }}"</h4>
                <label>Text Target:</label>
                <input type="text" name="target_text" value="{{ rule.target_text }}" required>
                
                <label>Pilih Gambar:</label>
                <select name="image_filename" required>
                    {% for image in uploaded_images %}
                        <option value="{{ image }}" {% if image == rule.image_filename %}selected{% endif %}>{{ image }}</option>
                    {% endfor %}
                </select>
                
                <div class="position-inputs">
                    <div>
                        <label>Offset X (mm dari text):</label>
                        <input type="number" name="offset_x" value="{{ rule.offset_x if rule.offset_x is not none else 0 }}" step="0.5" min="-100" max="100" required>
                    </div>
                    <div>
                        <label>Offset Y (mm dari text):</label>
                        <input type="number" name="offset_y" value="{{ rule.offset_y if rule.offset_y is not none else -10 }}" step="0.5" min="-100" max="100" required>
                    </div>
                </div>
                
                <label>Lebar (mm):</label>
                <input type="number" name="width" value="{{ rule.width if rule.width is not none else 20 }}" min="5" max="100" step="0.5" required>
                
                <label>Tinggi (mm):</label>
                <input type="number" name="height" value="{{ rule.height if rule.height is not none else 20 }}" min="5" max="100" step="0.5" required>
                
                <button type="submit">Update</button>
                <form method="post" action="/delete_image_rule/{{ i }}" class="inline-form">
                    <button type="submit" class="btn-danger" onclick="return confirm('Hapus image rule ini?')">Hapus</button>
                </form>
            </div>
        </form>
        {% endfor %}
        {% endif %}
    </div>

    <!-- Process Files -->
    {% if uploaded_files %}
    <div class="container">
        <h2>4. Proses Word ➡️ PDF dengan Gambar</h2>
        <p><strong>Proses yang akan dilakukan:</strong></p>
        <ol>
            <li><strong>Find & Replace text</strong> di dokumen Word</li>
            <li><strong>Convert SEMUA text ke Times New Roman</strong> (seperti Ctrl+A, ukuran font tetap)</li>
            <li>Convert Word ke PDF</li>
            <li><strong>Cari posisi text target di dalam PDF</strong></li>
            <li><strong>Tambahkan gambar dengan offset + randomization ±3mm</strong></li>
            <li>Gambar akan menumpuk di atas teks/element dengan posisi yang sedikit acak</li>
        </ol>
        <p><strong>Contoh:</strong> Jika text "endah" ditemukan di koordinat (100, 200), offset X=10, Y=-15, dan random X=+1.2, Y=-0.8, maka gambar akan ditempatkan di (111.2, 183.2) - memberikan efek posisi natural yang tidak kaku.</p>
        <p><strong>Fitur Baru:</strong></p>
        <ul>
            <li>📝 <strong>Semua text jadi Times New Roman</strong> (seperti Ctrl+A + change font)</li>
            <li>📏 <strong>Ukuran font tetap sama</strong> seperti aslinya</li>
            <li>🎲 <strong>Random positioning ±3mm</strong> untuk efek natural (tidak kaku/robot)</li>
        </ul>
        <form method="post" action="/process">
            <button type="submit" class="btn-success">🔄 Proses ke PDF dengan Gambar</button>
        </form>
    </div>
    {% endif %}

    <!-- Download Results -->
    {% if processed_files %}
    <div class="container">
        <h2>5. Download Hasil PDF</h2>
        <div class="result-files">
            <h3>PDF yang sudah diproses:</h3>
            {% for file in processed_files %}
                <a href="/download/{{ file }}" class="download-link">📥 {{ file }}</a>
            {% endfor %}
            <br><br>
            <a href="/download_all" class="download-link btn-success">📦 Download Semua PDF (ZIP)</a>
        </div>
    </div>
    {% endif %}

</body>
</html>
'''

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'docx'

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg', 'jpeg', 'png', 'gif']

def find_replace_in_docx(file_path, rules):
    """Find and replace text, then convert ALL text in document to Times New Roman (keeping original size)"""
    try:
        doc = Document(file_path)
        
        # Step 1: Find and Replace in paragraphs
        for paragraph in doc.paragraphs:
            for rule in rules:
                if rule['find_text'] in paragraph.text:
                    paragraph.text = paragraph.text.replace(rule['find_text'], rule['replace_text'])
        
        # Step 2: Find and Replace in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for rule in rules:
                            if rule['find_text'] in paragraph.text:
                                paragraph.text = paragraph.text.replace(rule['find_text'], rule['replace_text'])
        
        # Step 3: Convert ALL text to Times New Roman (like Ctrl+A) - keeping original font size
        # Convert paragraphs
        for paragraph in doc.paragraphs:
            for run in paragraph.runs:
                original_size = run.font.size  # Keep original size
                run.font.name = 'Times New Roman'
                if original_size:  # Only set size if it was defined
                    run.font.size = original_size
        
        # Convert tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            original_size = run.font.size  # Keep original size
                            run.font.name = 'Times New Roman'
                            if original_size:  # Only set size if it was defined
                                run.font.size = original_size
        
        print("✅ Semua text di dokumen berhasil diubah ke Times New Roman (ukuran font tetap)")
        return doc
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return None

def convert_docx_to_pdf(docx_path, pdf_path):
    """Convert DOCX to PDF using multiple methods"""
    
    # Method 1: Try docx2pdf with COM initialization
    if DOCX2PDF_AVAILABLE:
        try:
            # Initialize COM for Windows
            if PYTHONCOM_AVAILABLE:
                try:
                    pythoncom.CoInitialize()
                    docx2pdf_convert(docx_path, pdf_path)
                    pythoncom.CoUninitialize()
                except Exception as com_error:
                    print(f"COM error: {com_error}")
                    # Try without COM initialization
                    docx2pdf_convert(docx_path, pdf_path)
            else:
                docx2pdf_convert(docx_path, pdf_path)
                
            if os.path.exists(pdf_path):
                print("✅ Berhasil convert dengan docx2pdf method")
                return True
                
        except Exception as e:
            print(f"❌ docx2pdf method gagal: {str(e)}")
    
    # Method 2: Try using subprocess with LibreOffice
    if SUBPROCESS_AVAILABLE:
        try:
            # Check if LibreOffice is available
            libreoffice_commands = ['soffice', 'libreoffice', 'C:\\Program Files\\LibreOffice\\program\\soffice.exe']
            
            for cmd in libreoffice_commands:
                try:
                    # Try to convert
                    output_dir = os.path.dirname(pdf_path)
                    result = subprocess.run([
                        cmd, '--headless', '--convert-to', 'pdf', 
                        '--outdir', output_dir, docx_path
                    ], check=True, capture_output=True, timeout=30)
                    
                    # LibreOffice creates PDF with same name as input but .pdf extension
                    expected_pdf = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
                    
                    if os.path.exists(expected_pdf) and expected_pdf != pdf_path:
                        # Move to desired location
                        os.rename(expected_pdf, pdf_path)
                    
                    if os.path.exists(pdf_path):
                        print("✅ Berhasil convert dengan LibreOffice method")
                        return True
                    break
                    
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    continue
                    
        except Exception as e:
            print(f"❌ LibreOffice method gagal: {str(e)}")
    
    # Method 3: Create simple PDF from docx content using reportlab
    try:
        return create_pdf_from_docx_content(docx_path, pdf_path)
    except Exception as e:
        print(f"❌ Reportlab method gagal: {str(e)}")
    
    return False

def create_pdf_from_docx_content(docx_path, pdf_path):
    """Create PDF from DOCX content using reportlab (fallback method)"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        
        # Read docx content
        doc = Document(docx_path)
        
        # Create PDF
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        y_position = height - 50  # Start from top with margin
        line_height = 14
        
        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y_position, "Converted Document")
        y_position -= 30
        
        # Add paragraphs
        c.setFont("Helvetica", 12)
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                # Handle long text by wrapping
                text = paragraph.text.strip()
                max_width = width - 100  # Margin
                
                # Simple text wrapping
                words = text.split()
                line = ""
                for word in words:
                    test_line = line + word + " "
                    if c.stringWidth(test_line, "Helvetica", 12) < max_width:
                        line = test_line
                    else:
                        if line:
                            c.drawString(50, y_position, line.strip())
                            y_position -= line_height
                        line = word + " "
                        
                        # Check if we need a new page
                        if y_position < 50:
                            c.showPage()
                            y_position = height - 50
                
                # Draw remaining text
                if line:
                    c.drawString(50, y_position, line.strip())
                    y_position -= line_height
                
                # Add extra space after paragraph
                y_position -= 5
                
                # Check if we need a new page
                if y_position < 50:
                    c.showPage()
                    y_position = height - 50
        
        # Add tables (simplified)
        for table in doc.tables:
            c.drawString(50, y_position, "[TABLE CONTENT]")
            y_position -= line_height
            
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells])
                if row_text.strip():
                    # Simple text wrapping for table rows
                    if c.stringWidth(row_text, "Helvetica", 10) < width - 100:
                        c.setFont("Helvetica", 10)
                        c.drawString(60, y_position, row_text)
                        y_position -= 12
                    else:
                        c.setFont("Helvetica", 8)
                        c.drawString(60, y_position, row_text[:100] + "...")
                        y_position -= 10
                    
                    if y_position < 50:
                        c.showPage()
                        y_position = height - 50
            
            y_position -= 10
        
        c.save()
        print("✅ Berhasil convert dengan reportlab fallback method")
        return True
        
    except Exception as e:
        print(f"Error creating PDF with reportlab: {str(e)}")
        return False

def find_text_position_in_pdf(pdf_path, target_text):
    """Find position of target text in PDF and return coordinates"""
    text_positions = []
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Search for text in the page
            text_instances = page.search_for(target_text.lower())
            
            for inst in text_instances:
                # inst is a Rect object with coordinates
                text_positions.append({
                    'page': page_num,
                    'x': inst.x0,  # Left position
                    'y': inst.y0,  # Top position  
                    'width': inst.width,
                    'height': inst.height,
                    'rect': inst
                })
        
        doc.close()
        return text_positions
        
    except Exception as e:
        print(f"Error finding text position: {str(e)}")
        return []

def add_images_to_pdf(pdf_path, image_rules, target_texts_found):
    """Add images to PDF at positions relative to target text with random offset"""
    if not PDF_PROCESSING_AVAILABLE:
        print("PDF processing libraries tidak tersedia")
        return False
        
    try:
        # Create temporary output file
        temp_pdf_path = pdf_path + ".tmp"
        
        # Open PDF with PyMuPDF for editing
        doc = fitz.open(pdf_path)
        
        for rule in image_rules:
            target_text = rule['target_text']
            
            # Check if target text was found during replacement
            if target_text.lower() in target_texts_found:
                # Find positions of target text in PDF
                text_positions = find_text_position_in_pdf(pdf_path, target_text)
                
                if text_positions:
                    image_path = os.path.join(app.config['IMAGE_FOLDER'], rule['image_filename'])
                    
                    if os.path.exists(image_path):
                        # Convert mm to points (1mm = 2.834645669 points)
                        offset_x_points = float(rule.get('offset_x', 0)) * 2.834645669
                        offset_y_points = float(rule.get('offset_y', -10)) * 2.834645669
                        width_points = float(rule['width']) * 2.834645669
                        height_points = float(rule['height']) * 2.834645669
                        
                        # Add randomization: -3 to +3 mm
                        random_x = random.uniform(-3, 3) * 2.834645669  # Convert mm to points
                        random_y = random.uniform(-3, 3) * 2.834645669  # Convert mm to points
                        
                        # Add image near each instance of target text (or just first instance)
                        text_pos = text_positions[0]  # Use first occurrence
                        page_num = text_pos['page']
                        
                        if page_num < len(doc):
                            page = doc.load_page(page_num)
                            
                            # Calculate image position relative to text position with randomization
                            img_x = text_pos['x'] + offset_x_points + random_x
                            img_y = text_pos['y'] + offset_y_points + random_y
                            
                            # Create rect for image
                            img_rect = fitz.Rect(img_x, img_y, img_x + width_points, img_y + height_points)
                            
                            # Insert image
                            page.insert_image(img_rect, filename=image_path)
                            
                            print(f"Added image for '{target_text}' at relative position ({rule.get('offset_x', 0):+.1f}{random_x/2.834645669:+.1f}mm, {rule.get('offset_y', -10):+.1f}{random_y/2.834645669:+.1f}mm) from text")
                else:
                    print(f"Text '{target_text}' not found in PDF for positioning")
        
        # Save to temporary file first
        doc.save(temp_pdf_path)
        doc.close()
        
        # Replace original file with temporary file
        if os.path.exists(temp_pdf_path):
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            os.rename(temp_pdf_path, pdf_path)
            return True
        else:
            return False
        
    except Exception as e:
        print(f"Error adding images to PDF: {str(e)}")
        
        # Fallback: Try using reportlab to add images
        try:
            return add_images_to_pdf_reportlab(pdf_path, image_rules, target_texts_found)
        except Exception as e2:
            print(f"Fallback method also failed: {str(e2)}")
            return False

def add_images_to_pdf_reportlab(pdf_path, image_rules, target_texts_found):
    """Fallback method: Add images using reportlab overlay with text positioning and randomization"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from PyPDF2 import PdfReader, PdfWriter
        import io
        
        # Read existing PDF
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            
            # Create overlay with images for this page
            overlay_buffer = io.BytesIO()
            overlay_canvas = canvas.Canvas(overlay_buffer, pagesize=A4)
            
            # Add images for this page
            for rule in image_rules:
                target_text = rule['target_text']
                
                if target_text.lower() in target_texts_found:
                    image_path = os.path.join(app.config['IMAGE_FOLDER'], rule['image_filename'])
                    
                    if os.path.exists(image_path):
                        # For reportlab fallback, we'll use estimated position
                        # This is less accurate but provides basic functionality
                        
                        # Estimate text position (simplified approach)
                        # In a real implementation, you'd need OCR or PDF text extraction
                        estimated_x = 50 * mm  # Default estimate
                        estimated_y = 200 * mm  # Default estimate
                        
                        # Apply offsets
                        offset_x = float(rule.get('offset_x', 0)) * mm
                        offset_y = float(rule.get('offset_y', -10)) * mm
                        
                        # Add randomization: -3 to +3 mm
                        random_x = random.uniform(-3, 3) * mm
                        random_y = random.uniform(-3, 3) * mm
                        
                        x = estimated_x + offset_x + random_x
                        # Flip Y coordinate and apply offset (PDF coordinate system)
                        y = estimated_y - offset_y + random_y
                        
                        width = float(rule['width']) * mm
                        height = float(rule['height']) * mm
                        
                        overlay_canvas.drawImage(image_path, x, y, width=width, height=height)
                        
                        print(f"Added image (fallback) for '{target_text}' with randomization ({random_x/mm:+.1f}mm, {random_y/mm:+.1f}mm)")
            
            overlay_canvas.save()
            overlay_buffer.seek(0)
            
            # Create overlay PDF page
            overlay_reader = PdfReader(overlay_buffer)
            if len(overlay_reader.pages) > 0:
                overlay_page = overlay_reader.pages[0]
                page.merge_page(overlay_page)
            
            writer.add_page(page)
        
        # Write final PDF
        with open(pdf_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
        
    except Exception as e:
        print(f"Error in reportlab fallback: {str(e)}")
        return False

def find_target_texts_in_doc(doc, image_rules):
    """Find which target texts exist in the document"""
    found_texts = set()
    
    # Search in paragraphs
    for paragraph in doc.paragraphs:
        for rule in image_rules:
            if rule['target_text'].lower() in paragraph.text.lower():
                found_texts.add(rule['target_text'].lower())
    
    # Search in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for rule in image_rules:
                    if rule['target_text'].lower() in cell.text.lower():
                        found_texts.add(rule['target_text'].lower())
    
    return found_texts

@app.route('/')
def index():
    # Auto-load settings at startup if not already loaded
    if not session.get('settings_loaded'):
        load_settings()
        session['settings_loaded'] = True
    
    # Get session data
    uploaded_files = session.get('uploaded_files', [])
    replace_rules = session.get('replace_rules', [])
    image_rules = session.get('image_rules', [])
    uploaded_images = session.get('uploaded_images', [])
    processed_files = session.get('processed_files', [])
    
    # Add index to rules for template
    indexed_replace_rules = [(i, rule) for i, rule in enumerate(replace_rules)]
    indexed_image_rules = [(i, rule) for i, rule in enumerate(image_rules)]
    
    return render_template_string(HTML_TEMPLATE, 
                                uploaded_files=uploaded_files,
                                replace_rules=indexed_replace_rules,
                                image_rules=indexed_image_rules,
                                uploaded_images=uploaded_images,
                                processed_files=processed_files,
                                docx2pdf_available=DOCX2PDF_AVAILABLE,
                                pdf_processing_available=PDF_PROCESSING_AVAILABLE)

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

@app.route('/upload_images', methods=['POST'])
def upload_images():
    files = request.files.getlist('images')
    uploaded_images = session.get('uploaded_images', [])
    
    for file in files:
        if file and file.filename and allowed_image(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            file_path = os.path.join(app.config['IMAGE_FOLDER'], unique_filename)
            file.save(file_path)
            uploaded_images.append(unique_filename)
    
    session['uploaded_images'] = uploaded_images
    auto_save()  # Auto save after change
    flash('Gambar berhasil diupload!')
    return redirect(url_for('index'))

# Settings Management Routes
@app.route('/save_settings', methods=['POST'])
def save_settings_route():
    if save_settings():
        flash('✅ Settingan berhasil disimpan!')
    else:
        flash('❌ Gagal menyimpan settingan!')
    return redirect(url_for('index'))

@app.route('/load_settings', methods=['POST']) 
def load_settings_route():
    if load_settings():
        flash('✅ Settingan berhasil dimuat!')
    else:
        flash('❌ Gagal memuat settingan!')
    return redirect(url_for('index'))

@app.route('/export_settings')
def export_settings():
    try:
        settings = {
            'replace_rules': session.get('replace_rules', []),
            'image_rules': session.get('image_rules', []),
            'uploaded_images': session.get('uploaded_images', []),
            'export_date': datetime.now().isoformat()
        }
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8')
        json.dump(settings, temp_file, indent=2, ensure_ascii=False)
        temp_file.close()
        
        return send_file(temp_file.name, 
                        as_attachment=True,
                        download_name=f'app_settings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                        mimetype='application/json')
                        
    except Exception as e:
        flash(f'❌ Error exporting settings: {str(e)}')
        return redirect(url_for('index'))

@app.route('/import_settings', methods=['POST'])
def import_settings():
    try:
        file = request.files.get('settings_file')
        if file and file.filename.endswith('.json'):
            # Read uploaded file
            settings_data = json.load(file.stream)
            
            # Validate and load settings
            session['replace_rules'] = settings_data.get('replace_rules', [])
            session['image_rules'] = settings_data.get('image_rules', [])
            session['uploaded_images'] = settings_data.get('uploaded_images', [])
            
            # Save to local settings file
            save_settings()
            
            flash('✅ Settingan berhasil diimport!')
        else:
            flash('❌ Harap pilih file JSON yang valid!')
            
    except Exception as e:
        flash(f'❌ Error importing settings: {str(e)}')
        
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

@app.route('/delete_image/<filename>', methods=['POST'])
def delete_image(filename):
    uploaded_images = session.get('uploaded_images', [])
    if filename in uploaded_images:
        file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        uploaded_images.remove(filename)
        session['uploaded_images'] = uploaded_images
        auto_save()  # Auto save after change
        flash('Gambar berhasil dihapus!')
    return redirect(url_for('index'))

# Text Replace Rules
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
        auto_save()  # Auto save after change
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
        auto_save()  # Auto save after change
        flash('Rule berhasil diupdate!')
    
    return redirect(url_for('index'))

@app.route('/delete_rule/<int:index>', methods=['POST'])
def delete_rule(index):
    replace_rules = session.get('replace_rules', [])
    if 0 <= index < len(replace_rules):
        replace_rules.pop(index)
        session['replace_rules'] = replace_rules
        auto_save()  # Auto save after change
        flash('Rule berhasil dihapus!')
    
    return redirect(url_for('index'))

# Image Rules
@app.route('/add_image_rule', methods=['POST'])
def add_image_rule():
    target_text = request.form.get('target_text')
    image_filename = request.form.get('image_filename')
    offset_x = request.form.get('offset_x', '0')
    offset_y = request.form.get('offset_y', '-10')
    width = request.form.get('width', '20')
    height = request.form.get('height', '20')
    
    # Validate and convert values with error handling
    try:
        offset_x_val = float(offset_x) if offset_x and offset_x.strip() else 0.0
        offset_y_val = float(offset_y) if offset_y and offset_y.strip() else -10.0
        width_val = float(width) if width and width.strip() else 20.0
        height_val = float(height) if height and height.strip() else 20.0
    except (ValueError, TypeError):
        flash('Error: Nilai offset, width, atau height tidak valid!')
        return redirect(url_for('index'))
    
    if not target_text or not image_filename:
        flash('Error: Target text dan image filename harus diisi!')
        return redirect(url_for('index'))
    
    if target_text and image_filename:
        image_rules = session.get('image_rules', [])
        image_rules.append({
            'target_text': target_text,
            'image_filename': image_filename,
            'offset_x': offset_x_val,
            'offset_y': offset_y_val,
            'width': width_val,
            'height': height_val
        })
        session['image_rules'] = image_rules
        auto_save()  # Auto save after change
        flash('Image Rule berhasil ditambahkan!')
    
    return redirect(url_for('index'))

@app.route('/update_image_rule/<int:index>', methods=['POST'])
def update_image_rule(index):
    target_text = request.form.get('target_text')
    image_filename = request.form.get('image_filename')
    offset_x = request.form.get('offset_x', '0')
    offset_y = request.form.get('offset_y', '-10')
    width = request.form.get('width', '20')
    height = request.form.get('height', '20')
    
    # Validate and convert values with error handling
    try:
        offset_x_val = float(offset_x) if offset_x and offset_x.strip() else 0.0
        offset_y_val = float(offset_y) if offset_y and offset_y.strip() else -10.0
        width_val = float(width) if width and width.strip() else 20.0
        height_val = float(height) if height and height.strip() else 20.0
    except (ValueError, TypeError):
        flash('Error: Nilai offset, width, atau height tidak valid!')
        return redirect(url_for('index'))
    
    if not target_text or not image_filename:
        flash('Error: Target text dan image filename harus diisi!')
        return redirect(url_for('index'))
    
    image_rules = session.get('image_rules', [])
    if 0 <= index < len(image_rules):
        image_rules[index] = {
            'target_text': target_text,
            'image_filename': image_filename,
            'offset_x': offset_x_val,
            'offset_y': offset_y_val,
            'width': width_val,
            'height': height_val
        }
        session['image_rules'] = image_rules
        auto_save()  # Auto save after change
        flash('Image Rule berhasil diupdate!')
    else:
        flash('Error: Image rule tidak ditemukan!')
    
    return redirect(url_for('index'))

@app.route('/delete_image_rule/<int:index>', methods=['POST'])
def delete_image_rule(index):
    image_rules = session.get('image_rules', [])
    if 0 <= index < len(image_rules):
        image_rules.pop(index)
        session['image_rules'] = image_rules
        auto_save()  # Auto save after change
        flash('Image Rule berhasil dihapus!')
    
    return redirect(url_for('index'))

@app.route('/process', methods=['POST'])
def process_files():
    uploaded_files = session.get('uploaded_files', [])
    replace_rules = session.get('replace_rules', [])
    image_rules = session.get('image_rules', [])
    
    if not uploaded_files:
        flash('Harap upload file terlebih dahulu!')
        return redirect(url_for('index'))
    
    if not PDF_PROCESSING_AVAILABLE:
        flash('Library untuk processing PDF tidak tersedia! Install: pip install PyMuPDF reportlab')
        return redirect(url_for('index'))
    
    processed_files = []
    
    for filename in uploaded_files:
        try:
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Step 1: Find and Replace in Word document
            if replace_rules:
                doc = find_replace_in_docx(input_path, replace_rules)
                if doc:
                    # Save the modified Word document
                    temp_docx_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
                    doc.save(temp_docx_path)
                    docx_path = temp_docx_path
                else:
                    docx_path = input_path
            else:
                docx_path = input_path
            
            # Step 2: Convert to PDF (dengan multiple fallback methods)
            pdf_filename = filename.replace('.docx', '.pdf')
            pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)
            
            conversion_success = convert_docx_to_pdf(docx_path, pdf_path)
            
            if conversion_success and os.path.exists(pdf_path):
                # Step 3: Add images to PDF if rules exist
                if image_rules:
                    # Check which target texts were found
                    if replace_rules:
                        doc_for_search = Document(docx_path)
                    else:
                        doc_for_search = Document(input_path)
                    
                    target_texts_found = find_target_texts_in_doc(doc_for_search, image_rules)
                    
                    if add_images_to_pdf(pdf_path, image_rules, target_texts_found):
                        processed_files.append(pdf_filename)
                        flash(f'✅ {filename} berhasil diproses ke PDF dengan gambar!')
                    else:
                        processed_files.append(pdf_filename)
                        flash(f'⚠️ {filename} berhasil diproses ke PDF, tapi gagal menambahkan gambar!')
                else:
                    processed_files.append(pdf_filename)
                    flash(f'✅ {filename} berhasil diproses ke PDF!')
            else:
                flash(f'❌ Gagal convert {filename} ke PDF! Coba install LibreOffice atau Microsoft Office')
                
        except Exception as e:
            flash(f'❌ Error processing {filename}: {str(e)}')
    
    session['processed_files'] = processed_files
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['PDF_FOLDER'], filename)
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
            file_path = os.path.join(app.config['PDF_FOLDER'], filename)
            if os.path.exists(file_path):
                zip_file.write(file_path, filename)
    
    return send_file(temp_zip.name, 
                    as_attachment=True, 
                    download_name='processed_pdfs.zip',
                    mimetype='application/zip')

if __name__ == '__main__':
    print("🚀 Starting Flask Word to PDF App with Positioned Images...")
    print("Buka browser dan kunjungi: http://localhost:5000")
    print("\n📦 Install libraries yang diperlukan:")
    print("pip install flask python-docx docx2pdf reportlab PyMuPDF")
    print("\n✨ Fitur Unggulan:")
    print("- Find & Replace text dalam dokumen Word")
    print("- Convert Word ke PDF")
    print("- Tambahkan gambar di PDF dengan koordinat absolut")
    print("- Gambar menumpuk di atas semua elemen (textbox, tabel, dll)")
    print("- Positioning presisi dengan milimeter")
    print("- Multiple image rules untuk berbagai target text")
    print("\n🎯 Solusi untuk Textbox:")
    print("- Text 'endah' di textbox akan dicari")
    print("- Gambar ditambahkan di PDF dengan koordinat X,Y absolut")
    print("- Tidak ada batasan layout - gambar bisa di mana saja")
    
    app.run(debug=True, host='0.0.0.0', port=5000)