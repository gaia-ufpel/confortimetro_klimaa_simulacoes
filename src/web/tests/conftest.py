"""
Test configuration for web interface
"""
import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app, socketio

@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.test_client() as client:
        with app.app_context():
            yield client

@pytest.fixture
def socketio_client():
    """SocketIO test client"""
    return socketio.test_client(app)

@pytest.fixture
def temp_dir():
    """Temporary directory for test files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def sample_idf_file(temp_dir):
    """Create a sample IDF file for testing"""
    idf_content = """
!- Sample IDF file for testing
Version,
    22.1;

Building,
    Test Building,
    0.0,
    Suburbs,
    0.04,
    0.4,
    FullExterior,
    25,
    6;
"""
    idf_file = temp_dir / "test.idf"
    idf_file.write_text(idf_content)
    return idf_file

@pytest.fixture
def sample_epw_file(temp_dir):
    """Create a sample EPW file for testing"""
    epw_content = """LOCATION,São Paulo,SP,BRA,SWERA,-23.62,-46.66,-3.0,760.0
DESIGN CONDITIONS,1,Climate Design Data 2009 ASHRAE Handbook,,Heating,12,-1.5,"""
    epw_file = temp_dir / "test.epw"
    epw_file.write_text(epw_content)
    return epw_file
