from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for, session
import os
import zipfile
import tempfile
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Inches, Mm, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.shared import OxmlElement, qn
from docx.enum.dml import MSO_THEME_COLOR_INDEX
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Folder untuk menyimpan file
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
IMAGE_FOLDER = 'images'

# Buat folder jika belum ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Word Find & Replace with Positioned Images</title>
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
    </style>
</head>
<body>
    <h1>Word Find & Replace with Positioned Images</h1>
    
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
        <h2>3. Atur Gambar Berdasarkan Text</h2>
        
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
                <label>Text Target (cari text ini untuk posisi gambar):</label>
                <input type="text" name="target_text" placeholder="contoh: endah" required>
                
                <label>Pilih Gambar:</label>
                <select name="image_filename" required>
                    <option value="">-- Pilih Gambar --</option>
                    {% for image in uploaded_images %}
                        <option value="{{ image }}">{{ image }}</option>
                    {% endfor %}
                </select>
                
                <div class="form-group">
                    <label>Mode Gambar:</label>
                    <select name="image_mode">
                        <option value="normal">Normal (di paragraph)</option>
                        <option value="floating" selected>Floating (in front of text)</option>
                    </select>
                </div>
                
                <div class="position-inputs">
                    <div>
                        <label>Jarak Horizontal (mm dari kiri halaman):</label>
                        <input type="number" name="offset_x" value="0" step="0.5" min="-50" max="200">
                    </div>
                    <div>
                        <label>Jarak Vertikal (mm dari atas paragraph):</label>
                        <input type="number" name="offset_y" value="-10" step="0.5" min="-50" max="50">
                    </div>
                </div>
                
                <label>Lebar Gambar (mm):</label>
                <input type="number" name="image_width" value="20" min="5" max="100" step="0.1">
                
                <button type="submit" class="btn-success">Tambah Image Rule</button>
            </div>
        </form>

        <!-- Existing image rules -->
        {% if image_rules %}
        <h3>Image Rules yang sudah dibuat:</h3>
        {% for i, rule in image_rules %}
        <form method="post" action="/update_image_rule/{{ i }}">
            <div class="image-rule">
                <h4>Image Rule #{{ i + 1 }}</h4>
                <label>Text Target:</label>
                <input type="text" name="target_text" value="{{ rule.target_text }}" required>
                
                <label>Pilih Gambar:</label>
                <select name="image_filename" required>
                    {% for image in uploaded_images %}
                        <option value="{{ image }}" {% if image == rule.image_filename %}selected{% endif %}>{{ image }}</option>
                    {% endfor %}
                </select>
                
                <div class="form-group">
                    <label>Mode Gambar:</label>
                    <select name="image_mode">
                        <option value="normal" {% if rule.image_mode == 'normal' %}selected{% endif %}>Normal (di paragraph)</option>
                        <option value="floating" {% if rule.image_mode == 'floating' or not rule.image_mode %}selected{% endif %}>Floating (in front of text)</option>
                    </select>
                </div>
                
                <div class="position-inputs">
                    <div>
                        <label>Jarak Horizontal (mm):</label>
                        <input type="number" name="offset_x" value="{{ rule.offset_x }}" step="0.5" min="-50" max="200">
                    </div>
                    <div>
                        <label>Jarak Vertikal (mm):</label>
                        <input type="number" name="offset_y" value="{{ rule.offset_y }}" step="0.5" min="-50" max="50">
                    </div>
                </div>
                
                <label>Lebar Gambar (mm):</label>
                <input type="number" name="image_width" value="{{ rule.image_width }}" min="5" max="100" step="0.1">
                
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
        <h2>4. Jalankan Processing</h2>
        <p><strong>Catatan:</strong></p>
        <ul>
            <li>Find & Replace akan dijalankan terlebih dahulu</li>
            <li>Gambar akan ditambahkan berdasarkan target text dengan mode <strong>Floating (in front of text)</strong></li>
            <li>Mode Floating memungkinkan gambar menumpuk di atas textbox dan elemen lainnya</li>
            <li>Posisi gambar menggunakan koordinat absolut dalam milimeter</li>
        </ul>
        <form method="post" action="/process">
            <button type="submit" class="btn-success">🔄 Proses Semua File</button>
        </form>
    </div>
    {% endif %}

    <!-- Download Results -->
    {% if processed_files %}
    <div class="container">
        <h2>5. Download Hasil</h2>
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

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg', 'jpeg', 'png', 'gif']

def find_replace_in_docx(file_path, replace_rules, image_rules):
    """Find and replace text, then add positioned images based on text targets"""
    try:
        doc = Document(file_path)
        
        # Step 1: Find and Replace text in paragraphs
        for paragraph in doc.paragraphs:
            for rule in replace_rules:
                if rule['find_text'] in paragraph.text:
                    paragraph.text = paragraph.text.replace(rule['find_text'], rule['replace_text'])
        
        # Step 2: Find and Replace text in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for rule in replace_rules:
                        if rule['find_text'] in cell.text:
                            cell.text = cell.text.replace(rule['find_text'], rule['replace_text'])
        
        # Step 3: Add positioned images based on target text
        for image_rule in image_rules:
            add_positioned_image(doc, image_rule)
        
        return doc
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return None

def add_floating_image(paragraph, image_path, width_mm, offset_x_mm, offset_y_mm):
    """Add floating image with absolute positioning (in front of text)"""
    if not ADVANCED_POSITIONING:
        # Fallback to normal image if advanced positioning not available
        run = paragraph.add_run()
        run.add_picture(image_path, width=Mm(width_mm))
        return
    
    try:
        # Get the paragraph's XML element
        p = paragraph._element
        
        # Create drawing element
        drawing = OxmlElement('w:drawing')
        
        # Create inline drawing
        inline = OxmlElement('wp:anchor')
        inline.set('distT', "0")
        inline.set('distB', "0") 
        inline.set('distL', "0")
        inline.set('distR', "0")
        inline.set('simplePos', "0")
        inline.set('relativeHeight', "1")
        inline.set('behindDoc', "0")  # in front of text
        inline.set('locked', "0")
        inline.set('layoutInCell', "1")
        inline.set('allowOverlap', "1")
        
        # Simple position
        simple_pos = OxmlElement('wp:simplePos')
        simple_pos.set('x', "0")
        simple_pos.set('y', "0")
        inline.append(simple_pos)
        
        # Position H (horizontal)
        pos_h = OxmlElement('wp:positionH')
        pos_h.set('relativeFrom', 'column')
        pos_offset_h = OxmlElement('wp:posOffset')
        pos_offset_h.text = str(int(offset_x_mm * 36000))  # Convert mm to EMU
        pos_h.append(pos_offset_h)
        inline.append(pos_h)
        
        # Position V (vertical) 
        pos_v = OxmlElement('wp:positionV')
        pos_v.set('relativeFrom', 'paragraph')
        pos_offset_v = OxmlElement('wp:posOffset')
        pos_offset_v.text = str(int(offset_y_mm * 36000))  # Convert mm to EMU
        pos_v.append(pos_offset_v)
        inline.append(pos_v)
        
        # Extent (size)
        extent = OxmlElement('wp:extent')
        extent.set('cx', str(int(width_mm * 36000)))  # Convert mm to EMU
        extent.set('cy', str(int(width_mm * 36000)))  # Square image for simplicity
        inline.append(extent)
        
        # Wrap - in front of text
        wrap = OxmlElement('wp:wrapNone')
        inline.append(wrap)
        
        # Doc properties
        doc_pr = OxmlElement('wp:docPr')
        doc_pr.set('id', str(len(p.getparent().getparent()) + 1))
        doc_pr.set('name', f'Picture {len(p.getparent().getparent()) + 1}')
        inline.append(doc_pr)
        
        # Graphic
        graphic = OxmlElement('a:graphic')
        graphic.set(qn('xmlns:a'), 'http://schemas.openxmlformats.org/drawingml/2006/main')
        
        graphic_data = OxmlElement('a:graphicData')
        graphic_data.set('uri', 'http://schemas.openxmlformats.org/drawingml/2006/picture')
        
        # Picture
        pic = OxmlElement('pic:pic')
        pic.set(qn('xmlns:pic'), 'http://schemas.openxmlformats.org/drawingml/2006/picture')
        
        # Picture properties
        nv_pic_pr = OxmlElement('pic:nvPicPr')
        c_nv_pr = OxmlElement('pic:cNvPr')
        c_nv_pr.set('id', '1')
        c_nv_pr.set('name', f'Picture {len(p.getparent().getparent()) + 1}')
        nv_pic_pr.append(c_nv_pr)
        
        c_nv_pic_pr = OxmlElement('pic:cNvPicPr')
        nv_pic_pr.append(c_nv_pic_pr)
        
        pic.append(nv_pic_pr)
        
        # Blip fill
        blip_fill = OxmlElement('pic:blipFill')
        blip = OxmlElement('a:blip')
        
        # Add the image to document and get relationship id
        doc = paragraph.part
        image_part, rId = doc.get_or_add_image_part(image_path)
        blip.set(qn('r:embed'), rId)
        
        blip_fill.append(blip)
        stretch = OxmlElement('a:stretch')
        fill_rect = OxmlElement('a:fillRect')
        stretch.append(fill_rect)
        blip_fill.append(stretch)
        
        pic.append(blip_fill)
        
        # Shape properties
        sp_pr = OxmlElement('pic:spPr')
        xfrm = OxmlElement('a:xfrm')
        off = OxmlElement('a:off')
        off.set('x', '0')
        off.set('y', '0')
        xfrm.append(off)
        
        ext = OxmlElement('a:ext')
        ext.set('cx', str(int(width_mm * 36000)))
        ext.set('cy', str(int(width_mm * 36000)))
        xfrm.append(ext)
        sp_pr.append(xfrm)
        
        prst_geom = OxmlElement('a:prstGeom')
        prst_geom.set('prst', 'rect')
        av_lst = OxmlElement('a:avLst')
        prst_geom.append(av_lst)
        sp_pr.append(prst_geom)
        
        pic.append(sp_pr)
        
        graphic_data.append(pic)
        graphic.append(graphic_data)
        inline.append(graphic)
        
        drawing.append(inline)
        
        # Add to run
        run = paragraph.add_run()
        run._element.append(drawing)
        
    except Exception as e:
        print(f"Error creating floating image: {str(e)}")
        # Fallback to normal image
        run = paragraph.add_run()
        run.add_picture(image_path, width=Mm(width_mm))

def add_positioned_image(doc, image_rule):
    """Add image at relative position to target text"""
    try:
        target_text = image_rule['target_text']
        image_path = os.path.join(app.config['IMAGE_FOLDER'], image_rule['image_filename'])
        
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return
        
        image_mode = image_rule.get('image_mode', 'floating')
        
        # Search for target text in paragraphs
        for i, paragraph in enumerate(doc.paragraphs):
            if target_text.lower() in paragraph.text.lower():
                if image_mode == 'floating':
                    # Add floating image to the same paragraph
                    offset_x = float(image_rule.get('offset_x', 0))
                    offset_y = float(image_rule.get('offset_y', -10))
                    width_mm = float(image_rule.get('image_width', 20))
                    
                    add_floating_image(paragraph, image_path, width_mm, offset_x, offset_y)
                else:
                    # Add normal image
                    insert_image_near_paragraph(doc, i, image_path, image_rule)
                break  # Only add image for the first occurrence
        
        # Search for target text in table cells
        if image_mode == 'floating':
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if target_text.lower() in cell.text.lower():
                            # Add floating image to the first paragraph in cell
                            if cell.paragraphs:
                                offset_x = float(image_rule.get('offset_x', 0))
                                offset_y = float(image_rule.get('offset_y', -10))
                                width_mm = float(image_rule.get('image_width', 20))
                                
                                add_floating_image(cell.paragraphs[0], image_path, width_mm, offset_x, offset_y)
                            return  # Exit after first match
        
    except Exception as e:
        print(f"Error adding positioned image: {str(e)}")

def insert_image_near_paragraph(doc, target_index, image_path, image_rule):
    """Insert image near target paragraph (simplified version)"""
    try:
        # Determine where to insert the image based on offset_y
        offset_y = float(image_rule.get('offset_y', -10))
        
        # Create new paragraph for image
        if offset_y < 0:  # Above the text
            # Insert before the target paragraph
            if target_index > 0:
                new_para = doc.paragraphs[target_index-1]._element.addnext(doc.add_paragraph()._element)
            else:
                new_para = doc.paragraphs[0]._element.addprevious(doc.add_paragraph()._element)
        else:  # Below the text
            # Insert after the target paragraph
            if target_index < len(doc.paragraphs) - 1:
                new_para = doc.paragraphs[target_index]._element.addnext(doc.add_paragraph()._element)
            else:
                new_para = doc.add_paragraph()._element
        
        # Find the new paragraph object and add image
        for para in doc.paragraphs:
            if para._element == new_para:
                add_image_to_paragraph(para, image_path, image_rule)
                break
        
    except Exception as e:
        print(f"Error inserting image near paragraph: {str(e)}")
        # Fallback: add at the end of document
        fallback_paragraph = doc.add_paragraph()
        add_image_to_paragraph(fallback_paragraph, image_path, image_rule)

def insert_image_after_table(doc, image_path, image_rule):
    """Insert image after target table"""
    try:
        # Add paragraph after document
        new_paragraph = doc.add_paragraph()
        add_image_to_paragraph(new_paragraph, image_path, image_rule)
            
    except Exception as e:
        print(f"Error inserting image after table: {str(e)}")

def add_image_to_paragraph(paragraph, image_path, image_rule):
    """Add image to a paragraph with alignment"""
    try:
        # Add image to the paragraph
        run = paragraph.add_run()
        width_mm = float(image_rule.get('image_width', 20))
        run.add_picture(image_path, width=Mm(width_mm))
        
        # Apply horizontal alignment based on offset_x
        offset_x = float(image_rule.get('offset_x', 0))
        if offset_x > 10:  # Significant right offset
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif offset_x < -10:  # Significant left offset  
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        else:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
    except Exception as e:
        print(f"Error adding image to paragraph: {str(e)}")

@app.route('/')
def index():
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
    flash('Gambar berhasil diupload!')
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

# Image Rules
@app.route('/add_image_rule', methods=['POST'])
def add_image_rule():
    target_text = request.form.get('target_text')
    image_filename = request.form.get('image_filename')
    offset_x = request.form.get('offset_x', '0')
    offset_y = request.form.get('offset_y', '-10')
    image_width = request.form.get('image_width', '20')
    image_mode = request.form.get('image_mode', 'floating')
    
    if target_text and image_filename:
        image_rules = session.get('image_rules', [])
        image_rules.append({
            'target_text': target_text,
            'image_filename': image_filename,
            'offset_x': float(offset_x),
            'offset_y': float(offset_y),
            'image_width': float(image_width),
            'image_mode': image_mode
        })
        session['image_rules'] = image_rules
        flash('Image Rule berhasil ditambahkan!')
    
    return redirect(url_for('index'))

@app.route('/update_image_rule/<int:index>', methods=['POST'])
def update_image_rule(index):
    target_text = request.form.get('target_text')
    image_filename = request.form.get('image_filename')
    offset_x = request.form.get('offset_x', '0')
    offset_y = request.form.get('offset_y', '-10')
    image_width = request.form.get('image_width', '20')
    image_mode = request.form.get('image_mode', 'floating')
    
    image_rules = session.get('image_rules', [])
    if 0 <= index < len(image_rules):
        image_rules[index] = {
            'target_text': target_text,
            'image_filename': image_filename,
            'offset_x': float(offset_x),
            'offset_y': float(offset_y),
            'image_width': float(image_width),
            'image_mode': image_mode
        }
        session['image_rules'] = image_rules
        flash('Image Rule berhasil diupdate!')
    
    return redirect(url_for('index'))

@app.route('/delete_image_rule/<int:index>', methods=['POST'])
def delete_image_rule(index):
    image_rules = session.get('image_rules', [])
    if 0 <= index < len(image_rules):
        image_rules.pop(index)
        session['image_rules'] = image_rules
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
    
    processed_files = []
    
    for filename in uploaded_files:
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        output_filename = filename  # Gunakan nama file asli
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Process the document
        processed_doc = find_replace_in_docx(input_path, replace_rules, image_rules)
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
    print("Starting Flask Word Find & Replace App with Floating Images...")
    print("Buka browser dan kunjungi: http://localhost:5000")
    print("\nPastikan Anda sudah install library berikut:")
    print("pip install flask python-docx")
    print("\nFitur Unggulan:")
    print("- Find & Replace text dalam dokumen Word")
    print("- Floating Images dengan mode 'In Front of Text'")
    print("- Gambar bisa menumpuk di atas textbox dan elemen lainnya")
    print("- Positioning absolut dengan koordinat milimeter")
    print("- Multiple image rules untuk text yang berbeda")
    print("- Contoh: Cari text 'endah' di textbox, tambahkan gambar floating di atasnya")
    
    # Check advanced positioning status
    try:
        from docx.oxml.shared import OxmlElement, qn
        print("\n✅ Advanced positioning: Aktif (floating images tersedia)")
    except ImportError:
        print("\n❌ Advanced positioning: Tidak tersedia (fallback ke mode basic)")
    
    app.run(debug=True, host='0.0.0.0', port=5000)