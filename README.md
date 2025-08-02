# SmartTextGen API: 場景化的 AI 文字生成服務 (v4 - 生產級增強版)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0.1-brightgreen.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![Redis](https://img.shields.io/badge/Redis-6.2-red.svg)](https://redis.io/)
[![Prometheus](https://img.shields.io/badge/Prometheus-v2.30-orange.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-v8.2-orange.svg)](https://grafana.com/)
[![CI](https://github.com/<your-username>/smarttextgen-api/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-username>/smarttextgen-api/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一個基於 **Flask**, **Hugging Face Transformers**, **Redis** 和 **Prometheus/Grafana** 的文字生成 API，專為 **推薦系統**、**客服問答** 和 **電商場景** 設計。此版本新增 **OpenAPI 文件** 和 **負載測試**，進一步提升生產級部署能力。

## 專案架構

採用微服務架構，整合監控、文件和負載測試。

```
+------------------+       +-------------------+       +--------------------+
|   User Request   |  -->  |    Flask API      |  -->  |   AI Logic Core    |
|                  |       |  (app.py)         |       |   (ai_core.py)     |
| (with API Key)   |       |                   |       |   - Model Loading  |
+------------------+       | - Auth Validation |       |   - Text Generation|
        |                  | - Request Routing |       |   - Prompt Templating|
        V                  | - Input Validation|  <--+  - Response Cleaning |
+--------------------+     | - Redis & LRU Cache  |       +--------------------+
| Prometheus Exporter|     | - History Handling|
+--------------------+     | - OpenAPI Docs    |
        ^                  +-------------------+
+--------------------+     +--------------------+
|  Redis Cache       |     |  Prometheus Server |
| (for history)      | <-- | (API Metrics)      |
+--------------------+     +--------------------+
        ^
        |
+--------------------+
| Grafana Dashboard  |
| (Visual Monitoring)|
+--------------------+
```

- **Prometheus Exporter**: 公開 `/metrics` 端點，監控請求數、延遲和錯誤率。
- **Prometheus Server**: 定期抓取指標數據。
- **Grafana Dashboard**: 視覺化呈現 HTTP 請求速率、延遲 (p95) 和 5xx 錯誤。
- **OpenAPI Docs**: 通過 Swagger UI（`/apidocs`）提供互動式 API 文件。
- **Locust**: 模擬高併發負載測試，驗證效能。

## 核心特色

### 商業場景
- **推薦系統**：根據用戶偏好（如「我喜歡戶外運動」）生成產品建議。
- **客服問答**：回答常見問題（如「如何退貨？」）以專業語氣。
- **電商場景**：生成產品描述或回答產品問題（如「這款鞋適合跑步嗎？」）。

### 效能優化
- **高併發**: 使用 **Gunicorn** 多進程和 **Gevent** 非同步工人，支援高吞吐量。
- **批次處理**: `/api/generate_batch` 端點允許多個 prompt 合併處理，減少模型推論開銷。
- **快取機制**:
  - **Redis 快取**: 相同 prompt/mode/max_length 的請求從 Redis 返回，TTL 為 10 分鐘。
  - **本地 LRU 快取**: 使用 `functools.lru_cache` 加速熱門查詢。
- **模型優化**: 支援 **半精度 (FP16)** 和 **GPU 推論**（需設置 `DEVICE=0` 和 CUDA 映像）。

### 安全性強化
- **API Key 認證**: 所有請求需提供 `X-API-Key`。
- **容器安全**: 使用非 root 使用者 (`appuser`) 運行 Docker 容器。
- **秘密管理**: 敏感資訊（如 `API_KEY`）從環境變數讀取。
- **輸入驗證**: 使用 `flask-pydantic` 驗證 JSON 結構，限制 prompt 長度（1-500 字）。
- **Prompt Injection 防護**: 清理危險字符（如 `{`, `}`, ```）。
- **CORS**: 生產環境限制來源，開發環境允許所有來源。

### 可觀察性
- **Prometheus/Grafana**: 監控請求速率、延遲和錯誤率。
- **日誌**: 開發環境使用 DEBUG 級別，生產環境使用 INFO 級別。
- **OpenAPI 文件**: 提供互動式 Swagger UI（`/apidocs`）。

### CI/CD & 負載測試
- **GitHub Actions**: 執行 Black 格式檢查、Bandit 安全掃描、pytest 測試、OpenAPI 驗證和 Trivy 映像掃描。
- **Locust**: 模擬高併發請求，測試 API 效能。

## 快速啟動

1. **確保已安裝 Docker 和 Docker Compose**

2. **創建環境檔案** (`.env`):
   ```env
   FLASK_ENV=production
   API_KEY=your-secure-api-key
   ALLOWED_ORIGINS=http://your-frontend.com
   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=your-secure-password
   ```

3. **一鍵啟動服務**:
   ```bash
   docker-compose up --build -d
   ```
   啟動四個服務：`smarttextgen-api`、`redis`、`prometheus` 和 `grafana`。

4. **API 端點測試**:

   - **服務健康檢查**
     ```bash
     curl http://localhost:5000/health
     ```
     預期回應:
     ```json
     {
         "status": "ok",
         "model": "distilgpt2",
         "model_status": "ok",
         "redis_status": "ok",
         "cache_status": "ok",
         "api_key_status": "configured",
         "environment": "production"
     }
     ```

   - **單個請求** (電商模式)
     ```bash
     curl -X POST http://localhost:5000/api/generate \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-secure-api-key" \
     -d '{"prompt": "為一款防水夾克寫產品文案", "mode": "ecommerce"}'
     ```
     預期回應:
     ```json
     {
         "input": "為一款防水夾克寫產品文案",
         "output": "這款防水夾克採用高科技 Gore-Tex 面料，輕盈透氣，確保您在戶外活動中保持乾爽舒適。",
         "history": []
     }
     ```

   - **批次請求** (電商模式)
     ```bash
     curl -X POST http://localhost:5000/api/generate_batch \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-secure-api-key" \
     -d '{"prompts": ["為一款防水夾克寫產品文案", "為一款智慧手錶寫社群貼文"], "mode": "ecommerce"}'
     ```
     預期回應:
     ```json
     {
         "inputs": ["為一款防水夾克寫產品文案", "為一款智慧手錶寫社群貼文"],
         "outputs": ["這款防水夾克...", "這款智慧手錶..."],
         "history": []
     }
     ```

   - **對話歷史** (推薦模式)
     ```bash
     curl -X POST http://localhost:5000/api/generate \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-secure-api-key" \
     -d '{"prompt": "我喜歡戶外運動", "user_id": "user-002", "mode": "recommendation"}'
     curl -X POST http://localhost:5000/api/generate \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-secure-api-key" \
     -d '{"prompt": "有什麼適合登山的裝備嗎？", "user_id": "user-002", "mode": "recommendation"}'
     ```

5. **訪問 OpenAPI 文件**:
   - 瀏覽器打開 `http://localhost:5000/apidocs`。
   - 使用 Swagger UI 測試端點並查看文件。

6. **監控儀表板**:
   - 瀏覽器打開 `http://localhost:3000`，登入（預設：admin/your-secure-password）。
   - 導覽至 **Dashboards -> Browse**，查看 **SmartTextGen API Metrics**，監控請求速率、延遲和錯誤率。

## 執行測試

1. **單元測試**:
   ```bash
   docker-compose exec smarttextgen-api pytest
   ```

2. **負載測試**:
   - 安裝 Locust（若未在容器中）：
     ```bash
     pip install locust
     ```
   - 運行負載測試（模擬 50 個用戶，10 秒內增加）：
     ```bash
     locust -f tests/locustfile.py --host=http://localhost:5000
     ```
   - 瀏覽器打開 `http://localhost:8089`，配置用戶數（50）、生成速率（10/s）和測試時間（1 分鐘）。
   - 檢查報告（儲存於 `locust_report/`），並在 Grafana 查看負載期間的指標（請求速率、延遲）。

## CI/CD

本專案使用 GitHub Actions 進行自動化測試和安全掃描：
- **Black**: 程式碼格式檢查。
- **Bandit**: Python 安全掃描。
- **Pytest**: 單元測試和覆蓋率報告。
- **OpenAPI 驗證**: 檢查 `/apispec.json` 的正確性。
- **Trivy**: Docker 映像漏洞掃描。
- **Locust**: 模擬負載測試。

查看 `.github/workflows/ci.yml` 了解詳情。

## 部署到生產環境

1. **設置環境變數**:
   - 編輯 `.env` 文件，設置 `FLASK_ENV=production`、`API_KEY` 和 `ALLOWED_ORIGINS`。
   - 確保 `GRAFANA_ADMIN_PASSWORD` 是安全的隨機密碼。

2. **構建與部署**:
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

3. **監控與負載測試**:
   - 使用 Grafana 檢查服務健康狀況。
   - 定期運行 Locust 負載測試以驗證效能。
   - 檢查 Prometheus 指標以發現性能瓶頸。

## 常見問題（FAQ）

以下是開發者可能關心的問題與解答，涵蓋 API 使用、效能、安全性和部署。

### 1. 如何使用 API 生成特定場景的文字？
您可以通過 `/api/generate` 或 `/api/generate_batch` 端點，指定 `mode` 參數（`general`、`recommendation`、`support` 或 `ecommerce`）來生成對應場景的文字。例如，電商模式的請求：
```bash
curl -X POST http://localhost:5000/api/generate \
-H "Content-Type: application/json" \
-H "X-API-Key: your-secure-api-key" \
-d '{"prompt": "為一款防水夾克寫產品文案", "mode": "ecommerce"}'
```
每個模式使用特定的提示模板（定義於 `prompt_templates.py`），確保回應符合場景需求。

### 2. 如何確保 API 的安全性？
API 採用多層安全措施：
- **API Key 認證**：所有請求需包含正確的 `X-API-Key`（設置於 `.env` 中的 `API_KEY`）。
- **輸入驗證**：使用 `flask-pydantic` 限制 `prompt` 長度（1-500 字）並驗證 JSON 結構。
- **Prompt Injection 防護**：在 `prompt_templates.py` 中清理危險字符（如 `{`, `}`, ```）。
- **CORS**：生產環境通過 `ALLOWED_ORIGINS` 限制來源。
- **容器安全**：Docker 映像使用非 root 使用者（`appuser`）運行。

### 3. 如何處理高併發請求？
API 通過以下方式支援高併發：
- **Gunicorn + Gevent**：使用多進程和非同步工人處理並行請求（`docker-compose.yml` 中設置 `WORKERS=3` 和 `WORKER_CLASS=gevent`）。
- **快取機制**：Redis 快取（TTL 10 分鐘）和本地 LRU 快取（`functools.lru_cache`）減少重複計算。
- **批次處理**：`/api/generate_batch` 端點允許多個 prompt 合併處理，降低模型推論開銷。
您可以通過 Locust 負載測試（`tests/locustfile.py`）模擬高併發並檢查 Grafana 指標。

### 4. 如何查看 API 的文件？
API 文件通過 Swagger UI 提供，訪問 `http://localhost:5000/apidocs`。文件由 `flasgger` 自動生成，涵蓋 `/health`、`/api/generate` 和 `/api/generate_batch` 的請求/回應結構、參數和錯誤碼。您可以直接在 Swagger UI 中測試端點。

### 5. 如何監控 API 的效能？
API 整合了 Prometheus 和 Grafana：
- **Prometheus**：公開 `/metrics` 端點，收集請求數、延遲和錯誤率（配置於 `prometheus/prometheus.yml`）。
- **Grafana**：提供儀表板（`grafana-provisioning/dashboards/dashboard.json`），展示 HTTP 請求速率、p95 延遲和 5xx 錯誤率。
訪問 `http://localhost:3000`（預設登入：admin/your-secure-password），導覽至 **Dashboards -> Browse** 查看 **SmartTextGen API Metrics**。

### 6. 如何進行負載測試？
使用 Locust 進行負載測試（`tests/locustfile.py`）：
```bash
locust -f tests/locustfile.py --host=http://localhost:5000
```
在瀏覽器打開 `http://localhost:8089`，設置用戶數（例如 50）、生成速率（10/s）和運行時間（1 分鐘）。報告儲存於 `locust_report/`，並可結合金 Grafana 監控負載期間的指標（如延遲和錯誤率）。

### 7. 如何儲存和使用對話歷史？
對話歷史通過 Redis 儲存，與 `user_id` 綁定：
- 每次 `/api/generate` 或 `/api/generate_batch` 請求，若提供 `user_id`，歷史會儲存至 Redis（最多保留最近 3 輪對話，6 條記錄）。
- 歷史記錄用於上下文生成，確保回應連貫。
檢查 Redis 內容：
```bash
docker-compose exec redis redis-cli -n 0 KEYS '*'
```

### 8. 如何切換不同的 AI 模型？
API 支援通過環境變數 `MODEL_NAME` 切換模型（預設為 `distilgpt2`）。例如，在 `.env` 中設置：
```env
MODEL_NAME=gpt2-medium
```
重新構建映像：
```bash
docker-compose up --build
```
模型在 Dockerfile 構建時下載（`ai_core.py` 中使用 `transformers.pipeline` 載入）。若使用 GPU 推論，需設置 `DEVICE=0` 並使用 CUDA 映像。

### 9. 如何在生產環境中部署？
1. 編輯 `.env` 文件，設置 `FLASK_ENV=production`、`API_KEY`、`ALLOWED_ORIGINS` 和 `GRAFANA_ADMIN_PASSWORD`。
2. 運行：
   ```bash
   docker-compose up -d
   ```
3. 定期檢查 Grafana 儀表板和 Locust 報告，確保服務穩定。使用健康檢查端點（`/health`）監控模型和 Redis 狀態。

### 10. 如何擴展 API 以支援更多場景？
新增場景需修改 `prompt_templates.py` 中的 `templates` 字典。例如，添加一個「教育」模式：
```python
templates['education'] = "你是一個教育助手。參考歷史對話: {history_context}。根據以下問題：'{user_input}'，提供清晰且結構化的解答。"
```
更新 `app.py` 中的 `VALID_MODES` 列表：
```python
VALID_MODES = ['general', 'recommendation', 'support', 'ecommerce', 'education']
```
然後重新構建並部署：
```bash
docker-compose up --build
```

---

*這個專案旨在展示高品質的 AI 應用開發，適合用於商業場景展示或技術討論。歡迎 fork 和貢獻！*
