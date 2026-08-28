"""
Confortímetro Klimaa Web Interface
Flask web application for EnergyPlus simulation management
"""

import logging
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
try:
    from .simulation_integration import WebSimulationManager, FileUploadManager
except ImportError:  # Running ``python app.py`` from src/web.
    from simulation_integration import WebSimulationManager, FileUploadManager
import threading
import os
from flask import send_file
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('CONFORTIMETRO_SECRET_KEY', os.urandom(32))
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Initialize SocketIO
socketio = SocketIO(app)

# Initialize managers
sim_manager = WebSimulationManager(socketio)
file_manager = FileUploadManager()

def current_session_id():
    if 'session_id' not in session:
        session['session_id'] = sim_manager.create_session()
    return session['session_id']

@app.route('/')
def index():
    """Main application page"""
    current_session_id()
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    session_id = current_session_id()
    
    config = sim_manager.get_config(session_id)
    if config is None:
        # Return default configuration
        config = {
            'idf_path': '',
            'epw_path': '',
            'output_path': '',
            'energy_path': '',
            'pmv_lowerbound': -0.5,
            'pmv_upperbound': 0.5,
            'temp_ac_min': 18.0,
            'temp_ac_max': 26.0,
            'met': 1.0,
            'wme': 0.0,
            'module_type': 'COMPLETE',
            'rooms': ['ATELIE1']
        }
    
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update simulation configuration"""
    session_id = current_session_id()
    
    config_data = request.get_json()
    if not config_data:
        return jsonify({'error': 'No configuration data provided'}), 400
    
    success = sim_manager.update_config(session_id, config_data)
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Configuration update failed'}), 400

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    """Start simulation"""
    session_id = current_session_id()
    
    success = sim_manager.start_simulation(session_id)
    if success:
        return jsonify({'status': 'started'})
    else:
        return jsonify({'error': 'Failed to start simulation'}), 400

@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    """Stop simulation"""
    session_id = current_session_id()
    
    success = sim_manager.stop_simulation(session_id)
    if success:
        return jsonify({'status': 'stopping'})
    else:
        return jsonify({'error': 'Failed to stop simulation'}), 400

@app.route('/api/simulation/status', methods=['GET'])
def get_simulation_status():
    """Get simulation status"""
    session_id = current_session_id()
    
    status = sim_manager.get_simulation_status(session_id)
    return jsonify({'status': status})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_type = request.form.get('type')
    
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not file_type:
        return jsonify({'error': 'File type not specified'}), 400
    
    result = file_manager.save_uploaded_file(file, file_type)
    
    if result['status'] == 'success':
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/simulation/download', methods=['GET'])
def download_simulation_outputs():
    """Create and return a zip of the simulation outputs for this session."""
    session_id = current_session_id()

    # Create zip using simulation manager
    zip_result = sim_manager.zip_outputs(session_id)
    if zip_result.get('status') != 'success':
        return jsonify({'error': zip_result.get('error', 'Failed to create zip')}), 400

    zip_path = zip_result['zip_path']

    # Schedule deletion of the temporary zip after 60 seconds
    def _cleanup(path, delay=60):
        try:
            time.sleep(delay)
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Cleaned up temporary zip: {path}")
        except Exception as e:
            logger.error(f"Error cleaning up temp zip {path}: {e}")

    threading.Thread(target=_cleanup, args=(zip_path, 60), daemon=True).start()

    # Send file as attachment
    return send_file(zip_path, as_attachment=True, download_name=f'simulation_{session_id}.zip')

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    session_id = current_session_id()
    
    join_room(session_id)
    emit('connected', {'session_id': session_id})
    logger.info(f"Client connected: {session_id}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = session.get('session_id')
    logger.info(f"Client disconnected: {session_id}")

@socketio.on('ping')
def handle_ping():
    """Handle client ping for keepalive"""
    emit('pong')

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create upload directory
    os.makedirs('uploads', exist_ok=True)
    
    # Run the application
    socketio.run(
        app,
        debug=True,
        host='0.0.0.0',
        port=5000,
        allow_unsafe_werkzeug=True
    )
