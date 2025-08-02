from transformers import pipeline, set_seed
from prompt_templates import get_prompt_template
import logging
import os
import torch
from functools import lru_cache

# Set a seed for reproducibility
set_seed(42)

# --- Model Loading ---
MODEL_NAME = os.getenv('MODEL_NAME', 'distilgpt2')
DEVICE = int(os.getenv('DEVICE', -1))  # -1 for CPU, 0 for first GPU

try:
    # 啟動半精度 (FP16) 和 GPU 推論
    generator = pipeline(
        "text-generation", 
        model=MODEL_NAME,
        device=DEVICE,
        torch_dtype=torch.float16 if DEVICE != -1 and torch.cuda.is_available() else torch.float32
    )
    logging.info(f"AI 模型 ({MODEL_NAME}) 已成功載入。推論設備: {'GPU' if DEVICE != -1 and torch.cuda.is_available() else 'CPU'}")
except Exception as e:
    logging.error(f"載入 AI 模型失敗: {e}")
    generator = None

# 本地 LRU 快取以加速常見查詢
@lru_cache(maxsize=128)
def generate_response(prompt: list | str, history: tuple, max_length: int, mode: str = 'general') -> str | list:
    """
    使用載入的模型，並根據場景特定的提示模板生成文字。
    支援單個 prompt (str) 和批次 prompt (list[str]) 輸入。
    """
    if not generator:
        return "錯誤: AI 模型不可用。" if isinstance(prompt, str) else ["錯誤: AI 模型不可用。"] * len(prompt)
    
    try:
        # 處理單個 prompt 和批次 prompt
        if isinstance(prompt, str):
            prompts = [prompt]
        else:
            prompts = prompt
        
        # 將歷史和當前提示結合成完整輸入
        history_context = " ".join(history)
        full_prompts = [get_prompt_template(mode)(p).format(history_context=history_context) for p in prompts]

        result = generator(full_prompts, max_length=max_length, num_return_sequences=1, batch_size=len(full_prompts))
        
        # 清理並提取生成的文字
        outputs = []
        for i, res in enumerate(result):
            generated_text = res[0]['generated_text']
            response = generated_text if not generated_text.startswith(full_prompts[i]) else generated_text[len(full_prompts[i]):].strip()
            outputs.append(response)

        return outputs[0] if isinstance(prompt, str) else outputs

    except Exception as e:
        logging.error(f"文字生成過程中發生錯誤: {e}")
        return "抱歉，生成回應時發生錯誤。" if isinstance(prompt, str) else ["抱歉，生成回應時發生錯誤。"] * len(prompt)
