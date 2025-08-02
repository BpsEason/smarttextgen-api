# 場景特定的提示模板，用於不同模式。
# 這些模板是防止 Prompt Injection 的第一道防線，確保使用者輸入在受控的上下文中。
# `{{history_context}}` 會被歷史對話替換，`{{user_input}}` 會被當前使用者輸入替換。

def get_prompt_template(mode: str):
    """
    根據模式回傳特定的提示模板。
    """
    def sanitize_input(user_input: str) -> str:
        """防止 Prompt Injection，清理危險字符"""
        return user_input.replace('{', '').replace('}', '').replace('```', '')

    templates = {
        'recommendation': "你是一個專業的推薦系統。參考歷史對話: {history_context}。根據以下用戶偏好：'{user_input}'，請提供一個詳細且具吸引力的產品推薦。",
        'support': "你是一個專業的客服機器人。參考歷史對話: {history_context}。使用者提問：'{user_input}'，請提供一個清晰、專業且友善的回應。",
        'ecommerce': "你是一位有創意的電商文案寫手。參考歷史對話: {history_context}。根據以下輸入：'{user_input}'，生成一段引人注目的產品描述或促銷文案。",
        'general': "{history_context} {user_input}" # 預設通用模式
    }
    template = templates.get(mode, templates['general'])
    return lambda user_input: template.format(history_context="{history_context}", user_input=sanitize_input(user_input))
