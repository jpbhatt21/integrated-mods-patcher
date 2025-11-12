from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime
from dotenv import load_dotenv
from db import get, post
import service
# Load environment variables
load_dotenv()

# Flask App Configuration
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this')

# Authentication Configuration
USERS = os.getenv('USERS', "").split(',')



# =============================================================================
# DB FUNCTIONS 
# =============================================================================

# =============================================================================
# FLASK API FUNCTIONS
# =============================================================================

# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        print(f"Login attempt for user: {username} ", USERS)
        if username in USERS:
            print("User authenticated")
            response = get('COUNT', bearer=password, table='CHECK', record='')
            if response.status_code == 200:
                post('GENERIC', bearer=password, table='CHECK', data={"Title": f'{username} logged in at {datetime.utcnow().isoformat(sep=" ",timespec="seconds")}'})
                return jsonify({
                'success': True,
                'token': password,
                'expires_in': 86400  # 24 hours in secondss
            })
            
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/status', methods=['GET'])
def status():
    """Get current service status"""
    status = service.get_status()
    return jsonify({'success': True, 'status': status})

@app.route('/api/auth', methods=['GET'])
def auth():
    """Authenticate user"""
    bearer = request.headers.get('Authorization')
    response = get('COUNT', bearer=bearer, table='CHECK', record='')
    if response.status_code == 200:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@app.route('/api/stop', methods=['GET'])
def stop():
    """Stop the current running task"""
    bearer = request.headers.get('Authorization')
    response = get('COUNT', bearer=bearer, table='CHECK', record='')
    if not response.status_code == 200:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    if service.cancel_task():
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'No running task to cancel'}), 400

@app.route('/api/start/<task>/<game>/<threads>/<sleep>', methods=['GET'])
def table(task, game, threads, sleep):
    bearer = request.headers.get('Authorization')
    status = service.get_status()
    if not status["current_task"] in ["Idle","Finished","Cancelled"]:
        return jsonify({'success': False, 'error': 'A task is already running'}), 400
    service.start_service(task=task, game=game, bearer=bearer, threads=int(threads), sleep=int(sleep))
    status = service.get_status()
    if status:
        return jsonify({'success': True, 'status': status})
    return jsonify({'success': False}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
       })

# =============================================================================
# STATIC FILE SERVING
# =============================================================================

@app.route('/')
def serve_index():
    """Serve the main index.html file"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    """Serve static files or fallback to index.html for client-side routing"""
    try:
        # If the file exists, serve it
        return send_from_directory(app.static_folder, path)
    except:
        # If file doesn't exist, serve index.html (for client-side routing)
        return send_from_directory(app.static_folder, 'index.html')

# =============================================================================
# ERROR HANDLERS
# =============================================================================

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# =============================================================================
# SIGNAL HANDLERS AND STARTUP
# =============================================================================


if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)