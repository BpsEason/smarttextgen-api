from flask import Flask, request, jsonify
from flask_cors import CORS
from ai_core import generate_response
from flask_pydantic import validate
from pydantic import BaseModel, constr, conint
from flasgger import Swagger, swag_from
import logging
import redis
import json
import os
from functools import lru_cache
from prometheus_flask_exporter import PrometheusMetrics

# Initialize Flask app
app = Flask(__name__)

# Prometheus metrics setup
metrics = PrometheusMetrics(app)

# Configure CORS
environment = os.getenv('FLASK_ENV', 'development')
if environment == 'production':
    CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '').split(','))
else:
    CORS(app, origins='*')

# Configure logging based on environment
log_level = logging.DEBUG if environment == 'development' else logging.INFO
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Configure Swagger for OpenAPI documentation
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
app.config['SWAGGER'] = {'title': 'SmartTextGen API', 'uiversion': 3}
Swagger(app, config=swagger_config)

# --- Redis Configuration ---
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0
    )
    redis_client.ping()
    logging.info("成功連線至 Redis.")
except redis.ConnectionError as e:
    logging.error(f"連線至 Redis 失敗: {e}")
    redis_client = None

# API Key Validation
API_KEY = os.getenv('API_KEY', 'default-api-key')
if API_KEY == 'default-api-key':
    logging.warning("警告: 正在使用預設 API Key。請在生產環境中設定一個強密碼。")

def validate_api_key(api_key):
    return api_key == API_KEY

# Cache configuration
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL', 600))  # 10 minutes

# 定義有效的模式
VALID_MODES = ['general', 'recommendation', 'support', 'ecommerce']

# Pydantic models for input validation
class GenerateRequest(BaseModel):
    prompt: constr(min_length=1, max_length=500)
    user_id: str | None = None
    max_length: conint(ge=10, le=500) = 100
    mode: str = 'general'

class BatchGenerateRequest(BaseModel):
    prompts: list[constr(min_length=1, max_length=500)]
    user_id: str | None = None
    max_length: conint(ge=10, le=500) = 100
    mode: str = 'general'

@app.route('/health', methods=['GET'])
@swag_from({
    'responses': {
        200: {
            'description': '服務健康狀態',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'ok'},
                    'model': {'type': 'string', 'example': 'distilgpt2'},
                    'model_status': {'type': 'string', 'example': 'ok'},
                    'redis_status': {'type': 'string', 'example': 'ok'},
                    'cache_status': {'type': 'string', 'example': 'ok'},
                    'api_key_status': {'type': 'string', 'example': 'configured'},
                    'environment': {'type': 'string', 'example': 'production'}
                }
            }
        }
    }
})
def health_check():
    """服務健康檢查端點"""
    redis_status = "ok" if redis_client and redis_client.ping() else "未連線"
    model_name = os.getenv('MODEL_NAME', 'distilgpt2')
    logging.info("收到健康檢查請求.")
    
    # 檢查模型是否已載入
    from ai_core import generator
    model_status = "ok" if generator else "未載入"
    
    # 檢查快取狀態
    cache_status = "ok" if redis_client else "無快取"
    
    return jsonify({
        "status": "ok",
        "model": model_name,
        "model_status": model_status,
        "redis_status": redis_status,
        "cache_status": cache_status,
        "api_key_status": "configured" if API_KEY != 'default-api-key' else "default",
        "environment": environment
    })

@lru_cache(maxsize=100)
def generate_response_with_cache(prompt, history, max_length, mode):
    """帶有本地 LRU 快取的核心生成函數"""
    return generate_response(prompt, history, max_length, mode)

def get_redis_key(prompt, mode, max_length):
    """生成 Redis 快取的 Key"""
    return f"cache:{prompt}:{mode}:{max_length}"

def get_response_from_cache(prompt, mode, max_length):
    """嘗試從 Redis 快取中獲取回應"""
    if redis_client:
        cached_response = redis_client.get(get_redis_key(prompt, mode, max_length))
        if cached_response:
            logging.info("從 Redis 快取中獲取到回應.")
            return json.loads(cached_response.decode('utf-8'))
    return None

def set_response_to_cache(prompt, mode, max_length, response):
    """將回應存入 Redis 快取"""
    if redis_client:
        redis_client.setex(get_redis_key(prompt, mode, max_length), CACHE_TTL_SECONDS, json.dumps(response))

@app.route('/api/generate', methods=['POST'])
@validate()
@swag_from({
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 500, 'example': '為一款防水夾克寫產品文案'},
                    'user_id': {'type': 'string', 'example': 'user-001'},
                    'max_length': {'type': 'integer', 'minimum': 10, 'maximum': 500, 'example': 100},
                    'mode': {'type': 'string', 'enum': VALID_MODES, 'example': 'ecommerce'}
                },
                'required': ['prompt']
            }
        },
        {
            'name': 'X-API-Key',
            'in': 'header',
            'type': 'string',
            'required': True,
            'description': 'API Key for authentication'
        }
    ],
    'responses': {
        200: {
            'description': '生成成功的回應',
            'schema': {
                'type': 'object',
                'properties': {
                    'input': {'type': 'string', 'example': '為一款防水夾克寫產品文案'},
                    'output': {'type': 'string', 'example': '這款防水夾克採用高科技 Gore-Tex 面料...'},
                    'history': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        },
        400: {'description': '無效的請求參數'},
        401: {'description': '無效的 API Key'},
        422: {'description': '輸入驗證失敗'},
        500: {'description': '內部伺服器錯誤'}
    }
})
def generate_text(body: GenerateRequest):
    """主文字生成端點，支援單個請求"""
    try:
        prompt = body.prompt
        user_id = body.user_id
        max_length = body.max_length
        mode = body.mode
        api_key = request.headers.get('X-API-Key')
        
        if not validate_api_key(api_key):
            return jsonify({"error": "無效的 API Key。"}), 401

        # 驗證 mode
        if mode not in VALID_MODES:
            return jsonify({"error": f"mode 必須是 {VALID_MODES} 之一。"}), 400

        # 檢查 Redis 快取
        cached_response = get_response_from_cache(prompt, mode, max_length)
        if cached_response:
            return jsonify({
                "input": prompt,
                "output": cached_response['output'],
                "history": cached_response.get('history', [])
            })

        # 處理對話歷史 (最多保留最近 3 輪)
        history = []
        if user_id and redis_client:
            try:
                history_str = redis_client.get(user_id)
                if history_str:
                    history = json.loads(history_str.decode('utf-8'))[-6:]
            except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
                logging.error(f"從 Redis 讀取或解析歷史紀錄時發生錯誤: {e}", exc_info=True)
                history = []

        logging.info(f"生成請求 - user_id: {user_id}, 模式: {mode}, prompt: '{prompt}'")
        output = generate_response_with_cache(prompt, tuple(history), max_length, mode)

        # 更新歷史並存入 Redis
        new_history = history + [f"User: {prompt}", f"AI: {output}"]
        if user_id and redis_client:
            redis_client.set(user_id, json.dumps(new_history[:6]))
        else:
            new_history = []
        
        response_data = {
            "input": prompt,
            "output": output,
            "history": new_history
        }

        # 存入 Redis 快取
        set_response_to_cache(prompt, mode, max_length, response_data)

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"發生內部錯誤: {e}", exc_info=True)
        return jsonify({"error": "發生內部伺服器錯誤。"}), 500

@app.route('/api/generate_batch', methods=['POST'])
@validate()
@swag_from({
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'prompts': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'maxLength': 500}, 'example': ['為一款防水夾克寫產品文案', '為一款智慧手錶寫社群貼文']},
                    'user_id': {'type': 'string', 'example': 'user-001'},
                    'max_length': {'type': 'integer', 'minimum': 10, 'maximum': 500, 'example': 100},
                    'mode': {'type': 'string', 'enum': VALID_MODES, 'example': 'ecommerce'}
                },
                'required': ['prompts']
            }
        },
        {
            'name': 'X-API-Key',
            'in': 'header',
            'type': 'string',
            'required': True,
            'description': 'API Key for authentication'
        }
    ],
    'responses': {
        200: {
            'description': '批次生成成功的回應',
            'schema': {
                'type': 'object',
                'properties': {
                    'inputs': {'type': 'array', 'items': {'type': 'string'}},
                    'outputs': {'type': 'array', 'items': {'type': 'string'}},
                    'history': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        },
        400: {'description': '無效的請求參數'},
        401: {'description': '無效的 API Key'},
        422: {'description': '輸入驗證失敗'},
        500: {'description': '內部伺服器錯誤'}
    }
})
def generate_batch_text(body: BatchGenerateRequest):
    """批次文字生成端點"""
    try:
        batch_prompts = body.prompts
        user_id = body.user_id
        max_length = body.max_length
        mode = body.mode
        api_key = request.headers.get('X-API-Key')
        
        if not validate_api_key(api_key):
            return jsonify({"error": "無效的 API Key。"}), 401

        if mode not in VALID_MODES:
            return jsonify({"error": f"mode 必須是 {VALID_MODES} 之一。"}), 400

        # 處理對話歷史 (最多保留最近 3 輪)
        history = []
        if user_id and redis_client:
            try:
                history_str = redis_client.get(user_id)
                if history_str:
                    history = json.loads(history_str.decode('utf-8'))[-6:]
            except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
                logging.error(f"從 Redis 讀取或解析歷史紀錄時發生錯誤: {e}", exc_info=True)
                history = []

        # 檢查 Redis 快取
        outputs = []
        for prompt in batch_prompts:
            cached_response = get_response_from_cache(prompt, mode, max_length)
            if cached_response:
                outputs.append(cached_response['output'])
                continue
            output = generate_response_with_cache(prompt, tuple(history), max_length, mode)
            outputs.append(output)
            response_data = {"input": prompt, "output": output, "history": history}
            set_response_to_cache(prompt, mode, max_length, response_data)

        # 更新歷史並存入 Redis
        new_history = history + [f"User: {p}" for p in batch_prompts] + [f"AI: {o}" for o in outputs]
        if user_id and redis_client:
            redis_client.set(user_id, json.dumps(new_history[:6]))

        return jsonify({
            "inputs": batch_prompts,
            "outputs": outputs,
            "history": new_history[:6]
        })

    except Exception as e:
        logging.error(f"批次生成時發生內部錯誤: {e}", exc_info=True)
        return jsonify({"error": "批次生成時發生內部伺服器錯誤。"}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
