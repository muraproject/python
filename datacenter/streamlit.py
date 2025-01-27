from flask import Flask
from flask_autoindex import AutoIndex

# Inisialisasi Flask
app = Flask(__name__)

# Inisialisasi AutoIndex untuk root folder
files_index = AutoIndex(app, browse_root='./files')

# Setup routes sebelum app.run()
@app.route('/<path:path>')
def autoindex(path):
    return files_index.render_autoindex(path)

@app.route('/')
def index():
    return files_index.render_autoindex()

if __name__ == '__main__':
    # Jalankan server
    app.run(debug=True, host='0.0.0.0', port=5000)