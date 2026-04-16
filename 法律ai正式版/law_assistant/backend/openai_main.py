import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from openai import OpenAI

# ==========================================
# 1. 大模型 API 配置 (这里以 DeepSeek 为例)
# 如果用智谱，修改 BASE_URL 为 "https://open.bigmodel.cn/api/paas/v4/" 即可
# ==========================================
API_KEY = "sk-5e3049ac148e405bb0b6c9fd11111add"
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ==========================================
# 2. 初始化 FastAPI 应用与跨域配置
# ==========================================
app = FastAPI(title="法知明 - 劳动纠纷助手后端")

# 因为你的前端代码中写死了请求 http://localhost:8000，这里必须允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 3. 定义与前端对应的数据模型
# ==========================================
class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_id: str
    message: str
    chat_history: List[MessageItem] = []

# ==========================================
# 4. 定义核心对话接口
# ==========================================
SYSTEM_PROMPT = """你是一个名为“法知明”的专业劳动者权益法律咨询助手。
你的目标是：
1. 态度温暖、专业，像朋友一样安抚用户的情绪。
2. 准确引用《中华人民共和国劳动法》、《劳动合同法》等相关法律条款。
3. 给出实用的维权建议（如收集什么证据、如何去劳动监察大队投诉、如何申请仲裁）。
4. 如果用户提供的信息不足，主动向用户提问（如：是否有签订书面合同？每月工资多少？）。
5. 你的回答将直接显示在网页聊天框中，请使用换行符和简单的符号表情（如✅、📌）进行排版，避免长篇大论。"""

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        # 组装发送给大模型的消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 加上历史记录，让 AI 拥有记忆
        for msg in req.chat_history:
            messages.append({"role": msg.role, "content": msg.content})
            
        # 加上用户最新发送的消息
        messages.append({"role": "user", "content": req.message})

        # 调用大模型
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7, # 稍微带点感情和同理心
            max_tokens=800
        )
        
        ai_reply = response.choices[0].message.content
        
        # 返回格式必须和前端期望的对应 (data.response)
        return {"response": ai_reply}
        
    except Exception as e:
        print(f"后端报错: {str(e)}")
        raise HTTPException(status_code=500, detail="AI 服务暂时不可用，请稍后再试。")

# ==========================================
# 5. 挂载静态文件 (这一步让你可以直接在浏览器访问 HTML)
# ==========================================
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    # 必须运行在 8000 端口，因为你的前端代码写死了 http://localhost:8000/api/chat
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)