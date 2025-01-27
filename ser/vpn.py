from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return 'Server is running'

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({'message': 'Hello World!'})

@app.route('/api/data', methods=['POST'])
def receive_data():
    data = request.json
    return jsonify({
        'status': 'success',
        'received': data
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)