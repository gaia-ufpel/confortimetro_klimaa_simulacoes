"""
Test cases for the web application
"""
import json
import io
from pathlib import Path

def test_index_page(client):
    """Test main index page loads"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Confort\xc3\xadmetro Klimaa' in response.data

def test_get_config_initial(client):
    """Test getting initial configuration"""
    response = client.get('/api/config')
    assert response.status_code == 200
    
    config = json.loads(response.data)
    assert 'idf_path' in config
    assert 'epw_path' in config
    assert 'pmv_lowerbound' in config
    assert config['pmv_lowerbound'] == -0.5

def test_update_config(client):
    """Test updating configuration"""
    config_data = {
        'idf_path': '/path/to/test.idf',
        'epw_path': '/path/to/test.epw',
        'output_path': '/path/to/output',
        'energy_path': '/path/to/energyplus',
        'pmv_lowerbound': -0.7,
        'pmv_upperbound': 0.7,
        'temp_ac_min': 20.0,
        'temp_ac_max': 25.0,
        'met': 1.2,
        'wme': 0.1,
        'module_type': 'AC_ONLY',
        'rooms': ['ROOM1', 'ROOM2']
    }
    
    response = client.post('/api/config', 
                          json=config_data,
                          content_type='application/json')
    assert response.status_code == 200
    
    result = json.loads(response.data)
    assert result['status'] == 'success'
    
    # Verify config was saved
    response = client.get('/api/config')
    assert response.status_code == 200
    
    saved_config = json.loads(response.data)
    assert saved_config['pmv_lowerbound'] == -0.7
    assert saved_config['rooms'] == ['ROOM1', 'ROOM2']

def test_upload_idf_file(client, sample_idf_file):
    """Test uploading IDF file"""
    with open(sample_idf_file, 'rb') as f:
        data = {
            'file': (f, 'test.idf'),
            'type': 'idf'
        }
        response = client.post('/api/upload', 
                              data=data,
                              content_type='multipart/form-data')
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['status'] == 'success'
    assert 'path' in result
    assert result['filename'] == 'test.idf'

def test_upload_epw_file(client, sample_epw_file):
    """Test uploading EPW file"""
    with open(sample_epw_file, 'rb') as f:
        data = {
            'file': (f, 'test.epw'),
            'type': 'epw'
        }
        response = client.post('/api/upload', 
                              data=data,
                              content_type='multipart/form-data')
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['status'] == 'success'
    assert 'path' in result
    assert result['filename'] == 'test.epw'

def test_upload_invalid_file_type(client, temp_dir):
    """Test uploading invalid file type"""
    txt_file = temp_dir / "test.txt"
    txt_file.write_text("This is not an IDF file")
    
    with open(txt_file, 'rb') as f:
        data = {
            'file': (f, 'test.txt'),
            'type': 'idf'
        }
        response = client.post('/api/upload', 
                              data=data,
                              content_type='multipart/form-data')
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['status'] == 'error'
    assert 'inválida' in result['error'].lower()

def test_start_simulation_no_config(client):
    """Test starting simulation without configuration"""
    response = client.post('/api/simulation/start')
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'error' in result

def test_simulation_status(client):
    """Test getting simulation status"""
    response = client.get('/api/simulation/status')
    assert response.status_code == 200
    result = json.loads(response.data)
    assert 'status' in result

def test_socketio_connection(socketio_client):
    """Test SocketIO connection"""
    received = socketio_client.get_received()
    assert len(received) > 0
    
    # Check for connection event
    events = [event['name'] for event in received]
    assert 'connected' in events

def test_socketio_ping(socketio_client):
    """Test SocketIO ping/pong"""
    socketio_client.emit('ping')
    received = socketio_client.get_received()
    
    # Should receive pong response
    pong_events = [event for event in received if event['name'] == 'pong']
    assert len(pong_events) > 0

def test_file_upload_no_file(client):
    """Test upload endpoint with no file"""
    response = client.post('/api/upload', data={})
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'No file provided' in result['error']

def test_file_upload_no_type(client, sample_idf_file):
    """Test upload endpoint with no type specified"""
    with open(sample_idf_file, 'rb') as f:
        data = {'file': (f, 'test.idf')}
        response = client.post('/api/upload', 
                              data=data,
                              content_type='multipart/form-data')
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'File type not specified' in result['error']
