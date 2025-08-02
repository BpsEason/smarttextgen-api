import pytest
import json
import redis
import os
from unittest.mock import patch, MagicMock

# Dynamically import the Flask app
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, VALID_MODES

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Fixture to ensure a clean Redis state for tests."""
    redis_client = redis.Redis(host='redis', port=6379, db=0)
    try:
        redis_client.ping()  # Check connection first
        redis_client.flushdb()
        yield
    except redis.exceptions.ConnectionError:
        print("Warning: Redis is not running. Skipping Redis-dependent tests.")
        yield
        
@pytest.fixture
def client():
    """配置 Flask 應用程式用於測試。"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def get_headers(api_key="my-secure-api-key"):
    """為請求設定 API Key"""
    return {'X-API-Key': api_key, 'Content-Type': 'application/json'}

@patch('app.redis_client', MagicMock())
def test_health_check_no_redis(client):
    """測試 /health 端點，模擬無 Redis 連線。"""
    app.redis_client.ping.return_value = False
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
    assert response.json['redis_status'] == '未連線'
    assert response.json['cache_status'] == '無快取'

def test_apidocs_endpoint(client):
    """測試 Swagger UI 端點。"""
    response = client.get('/apidocs/')
    assert response.status_code == 200
    assert b"Swagger UI" in response.data

@patch('app.generate_response_with_cache', MagicMock(return_value='Test response.'))
def test_generate_missing_api_key(client):
    """測試 /api/generate 缺少 API Key 的情況。"""
    response = client.post('/api/generate', json={'prompt': 'Test'})
    assert response.status_code == 401
    assert "無效的 API Key。" in response.json['error']

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='Test response.'))
def test_generate_missing_prompt(client):
    """測試 /api/generate 缺少 prompt 的情況。"""
    response = client.post('/api/generate', json={}, headers=get_headers())
    assert response.status_code == 422  # flask-pydantic returns 422
    assert "prompt" in response.json['detail'][0]['loc']

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='Test response.'))
def test_generate_invalid_max_length(client):
    """測試 /api/generate max_length 輸入無效的情況。"""
    response = client.post('/api/generate', json={'prompt': 'Test', 'max_length': 5}, headers=get_headers())
    assert response.status_code == 422
    assert "max_length" in response.json['detail'][0]['loc']

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='This is a generated response.'))
def test_generate_invalid_mode(client):
    """測試 /api/generate mode 輸入無效的情況。"""
    response = client.post('/api/generate', json={'prompt': 'Test', 'mode': 'invalid_mode'}, headers=get_headers())
    assert response.status_code == 400
    assert "mode 必須是" in response.json['error']
    assert all(m in response.json['error'] for m in VALID_MODES)

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='This is a generated response.'))
def test_generate_valid_request(client):
    """測試 /api/generate 有效請求的情況。"""
    response = client.post('/api/generate', json={'prompt': 'Hello, world!'}, headers=get_headers())
    assert response.status_code == 200
    assert 'output' in response.json
    assert response.json['input'] == 'Hello, world!'
    assert isinstance(response.json['output'], str)
    assert response.json['output'] == 'This is a generated response.'

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='An e-commerce description.'))
def test_generate_ecommerce_mode(client):
    """測試 /api/generate 的 'ecommerce' 模式。"""
    response = client.post('/api/generate', json={'prompt': 'a waterproof jacket', 'mode': 'ecommerce'}, headers=get_headers())
    assert response.status_code == 200
    assert 'output' in response.json
    assert response.json['input'] == 'a waterproof jacket'
    assert response.json['output'] == 'An e-commerce description.'

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='AI: Response 1.'))
def test_generate_with_history(client):
    """測試帶有 user_id 的對話歷史功能。"""
    user_id = 'test-user'
    app.redis_client.get.return_value = json.dumps(["User: Hello."]).encode('utf-8')
    
    response = client.post('/api/generate', json={'prompt': 'How are you?', 'user_id': user_id}, headers=get_headers())
    
    app.redis_client.set.assert_called()
    assert response.status_code == 200
    assert 'history' in response.json
    assert response.json['history'] == ['User: Hello.', 'AI: Response 1.']

@patch('app.redis_client', MagicMock())
@patch('app.generate_response_with_cache', MagicMock(return_value='Cached response.'))
def test_generate_with_cache(client):
    """測試 Redis 快取功能。"""
    app.redis_client.get.return_value = json.dumps({"input": "Test", "output": "Cached response.", "history": []}).encode('utf-8')
    response1 = client.post('/api/generate', json={'prompt': 'Test', 'mode': 'general'}, headers=get_headers())
    response2 = client.post('/api/generate', json={'prompt': 'Test', 'mode': 'general'}, headers=get_headers())
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json['output'] == response2.json['output']
    app.redis_client.get.assert_called_with('cache:Test:general:100')

@patch('app.generate_response', MagicMock(return_value=['Response 1', 'Response 2']))
def test_generate_batch_valid_request(client):
    """測試 /api/generate_batch 的有效請求。"""
    response = client.post('/api/generate_batch', json={'prompts': ['Prompt 1', 'Prompt 2']}, headers=get_headers())
    assert response.status_code == 200
    assert 'outputs' in response.json
    assert isinstance(response.json['outputs'], list)
    assert response.json['outputs'] == ['Response 1', 'Response 2']
    assert response.json['inputs'] == ['Prompt 1', 'Prompt 2']

@patch('app.generate_response', MagicMock(return_value=['Response 1', 'Response 2']))
def test_generate_batch_invalid_input(client):
    """測試 /api/generate_batch 輸入無效的情況。"""
    response = client.post('/api/generate_batch', json={'prompts': 'not a list'}, headers=get_headers())
    assert response.status_code == 422
    assert "prompts" in response.json['detail'][0]['loc']
