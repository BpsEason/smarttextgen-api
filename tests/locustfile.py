from locust import HttpUser, task, between
import json
import random

class SmartTextGenUser(HttpUser):
    wait_time = between(1, 5)  # 模擬用戶之間的等待時間 (1-5秒)
    
    def on_start(self):
        """每個模擬用戶啟動時設置 API Key"""
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "my-secure-api-key"
        }
        self.modes = ["general", "recommendation", "support", "ecommerce"]
        self.prompts = [
            "為一款防水夾克寫產品文案",
            "我喜歡戶外運動",
            "如何退貨？",
            "這款鞋適合跑步嗎？"
        ]

    @task(3)
    def generate_single(self):
        """模擬單個生成請求"""
        payload = {
            "prompt": random.choice(self.prompts),
            "mode": random.choice(self.modes),
            "max_length": random.randint(50, 200),
            "user_id": f"user-{random.randint(1, 1000)}"
        }
        self.client.post("/api/generate", json=payload, headers=self.headers)

    @task(1)
    def generate_batch(self):
        """模擬批次生成請求"""
        payload = {
            "prompts": random.sample(self.prompts, k=2),
            "mode": random.choice(self.modes),
            "max_length": random.randint(50, 200),
            "user_id": f"user-{random.randint(1, 1000)}"
        }
        self.client.post("/api/generate_batch", json=payload, headers=self.headers)

    @task(1)
    def health_check(self):
        """模擬健康檢查請求"""
        self.client.get("/health")
