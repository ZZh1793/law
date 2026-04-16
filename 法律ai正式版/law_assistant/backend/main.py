import uvicorn
import httpx
import webbrowser
import os
from threading import Timer
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

import database
import requests
import urllib3

# ==========================================
# 禁用代理（彻底解决代理导致API无法连接的问题）
# ==========================================
# 清除所有可能的代理环境变量
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", 
             "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"]:
    os.environ.pop(var, None)

# 配置 session 禁用代理
session = requests.Session()
session.trust_env = False
# 显式设置 proxies 为 None 确保不使用代理
session.proxies = None

# 禁用 urllib3 的代理警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. API 配置
# ==========================================
# DeepSeek 配置
DEEPSEEK_API_KEY = "sk-1843dc3b9a164ab6adb0945fc637a114"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# 豆包(火山引擎ARK) API 配置 - 图片和文档识别
ARK_API_KEY = "ark-f5c28f9c-4397-4a15-9573-1d968a0c03ad-555a6"
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_MODEL = "doubao-vision-01"

# 小理法律检索 API 配置
XIAOLI_APPID = "QthdBErlyaYvyXul"
XIAOLI_SECRET = "EC5D455E6BD348CE8E18BE05926D2EBE"
XIAOLI_API_BASE = "https://openapi.delilegal.com/api/qa/v3/search"

# ==========================================
# 2. 初始化 FastAPI 应用
# ==========================================
app = FastAPI(title="法知明 - 劳动纠纷助手后端")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时初始化数据库
database.init_db()

def open_browser():
    """打开本地浏览器"""
    url = "http://127.0.0.1:8000/guide.html"
    webbrowser.open(url)

# ==========================================
# 3. 小理法律检索函数
# ==========================================
def search_laws(keyword: str) -> str:
    """检索相关法律条文"""
    try:
        url = f"{XIAOLI_API_BASE}/queryListLaw"
        headers = {
            "Content-Type": "application/json",
            "appid": XIAOLI_APPID,
            "secret": XIAOLI_SECRET
        }
        payload = {
            "pageNo": 1,
            "pageSize": 3,
            "sortField": "correlation",
            "sortOrder": "desc",
            "condition": {
                "timeLinessTypeArr": ["5"],
                "publishYearStart": "2000-01-01",
                "publishYearEnd": "2024-12-31",
                "activeYearStart": "2000-01-01",
                "activeYearEnd": "2024-12-31",
                "keywords": [keyword],
                "fieldName": "semantic"
            }
        }
        resp = session.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get("code") == 0 or data.get("success") == True:
            # 修正：实际返回结构是 body.data
            result_list = data.get("body", {}).get("data", [])
            if result_list:
                laws = []
                for item in result_list[:3]:
                    title = item.get("title", "")
                    content = item.get("content", "")
                    if not content:
                        highlights = item.get("highlights", [])
                        content = highlights[0][:500] if highlights else ""
                    else:
                        content = content[:500]
                    laws.append(f"【{title}】{content}...")
                return "\n".join(laws)
        return ""
    except Exception as e:
        print(f"法律检索失败: {e}")
        return ""

def search_cases(keyword: str) -> str:
    """检索相关司法案例"""
    try:
        url = f"{XIAOLI_API_BASE}/queryListCase"
        headers = {
            "appid": XIAOLI_APPID,
            "secret": XIAOLI_SECRET
        }
        payload = {
            "pageNo": 1,
            "pageSize": 2,
            "sortField": "correlation",
            "sortOrder": "desc",
            "condition": {
                "caseYearStart": "2018-01-01",
                "caseYearEnd": "2024-12-31",
                "courtLevelArr": ["0"],
                "keywordArr": [keyword]
            }
        }
        resp = session.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get("code") == 0 or data.get("success") == True:
            # 修正：实际返回结构是 body.data
            result_list = data.get("body", {}).get("data", [])
            if result_list:
                cases = []
                for item in result_list[:2]:
                    try:
                        title = item.get("title", "") or ""
                        content = item.get("content", "") or ""
                        content = content[:300] if content else ""
                        cases.append(f"【{title}】{content}...")
                    except:
                        continue
                return "\n".join(cases) if cases else ""
        return ""
    except Exception as e:
        print(f"案例检索失败: {e}")
        return ""

# ==========================================
# 4. 数据模型定义
# ==========================================
class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_id: int
    message: str
    chat_history: List[MessageItem] = []
    conversation_id: Optional[int] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class ConversationRequest(BaseModel):
    user_id: int
    title: Optional[str] = None
    is_pinned: Optional[bool] = None

# ==========================================
# 4. 用户认证接口
# ==========================================
@app.post("/api/register")
async def register(req: RegisterRequest):
    """用户注册"""
    result = database.create_user(
        username=req.username,
        password=req.password,
        email=req.email,
        phone=req.phone
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {"success": True, "user": result}

@app.post("/api/login")
async def login(req: LoginRequest):
    """用户登录"""
    user = database.verify_user(req.username, req.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 获取用户的第一个对话
    conversations = database.get_user_conversations(user["id"])
    conversation_id = conversations[0]["id"] if conversations else None
    
    return {
        "success": True,
        "user": user,
        "conversation_id": conversation_id
    }

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    """获取用户信息"""
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True, "user": user}

# ==========================================
# 5. 对话管理接口
# ==========================================
@app.get("/api/conversations/{user_id}")
async def get_conversations(user_id: int):
    """获取用户所有对话"""
    conversations = database.get_user_conversations(user_id)
    return {"success": True, "conversations": conversations}

@app.post("/api/conversations")
async def create_conversation(req: ConversationRequest):
    """创建新对话"""
    conversation = database.create_conversation(req.user_id, req.title or "新对话")
    return {"success": True, "conversation": conversation}

@app.put("/api/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, req: ConversationRequest):
    """更新对话"""
    database.update_conversation(
        conversation_id,
        title=req.title,
        is_pinned=1 if req.is_pinned else 0 if req.is_pinned is not None else None
    )
    return {"success": True}

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """删除对话"""
    database.delete_conversation(conversation_id)
    return {"success": True}

# ==========================================
# 6. 消息接口
# ==========================================
@app.get("/api/messages/{conversation_id}")
async def get_messages(conversation_id: int):
    """获取对话消息"""
    messages = database.get_conversation_messages(conversation_id)
    return {"success": True, "messages": messages}

# ==========================================
# 7. 核心对话接口 (带数据库存储 + 小理法律检索)
# ==========================================
SYSTEM_PROMPT_TEMPLATE = """你是一个名为"法知明"的专业劳动者权益法律咨询助手。

【你的核心原则】
1. 态度温暖、专业，像朋友一样安抚用户的情绪。
2. 基于检索到的真实法律条文和案例回答，不要编造法条。
3. 给出实用的维权建议（如收集什么证据、如何去劳动监察大队投诉、如何申请仲裁）。
4. 如果用户提供的信息不足，主动向用户提问（如：是否有签订书面合同？每月工资多少？）。
5. 你的回答将直接显示在网页聊天框中，请使用换行符和简单的符号表情（如✅、📌）进行排版，避免长篇大论。

【当前检索到的法律条文】(如果为空则忽略)
{relevant_laws}

【当前检索到的相关案例】(如果为空则忽略)
{relevant_cases}"""

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # 1. 处理对话 ID
    conversation_id = req.conversation_id
    
    # 如果没有 conversation_id，创建一个新对话
    if not conversation_id:
        conversation = database.create_conversation(req.user_id, "新对话")
        conversation_id = conversation["id"]
    
    # 2. 保存用户消息到数据库
    database.add_message(conversation_id, "user", req.message)
    
    # 3. 更新对话标题（如果是第一条消息）
    messages = database.get_conversation_messages(conversation_id)
    if len(messages) == 1:
        title = req.message[:30] + "..." if len(req.message) > 30 else req.message
        database.update_conversation(conversation_id, title=title)
    
    # 4. 调用小理API检索相关法律条文和案例
    print(f"正在检索法律资料，关键词: {req.message}")
    relevant_laws = search_laws(req.message)
    relevant_cases = search_cases(req.message)
    print(f"检索到法律条文: {len(relevant_laws) if relevant_laws else 0} 字符")
    print(f"检索到案例: {len(relevant_cases) if relevant_cases else 0} 字符")
    
    # 5. 组装系统提示词（包含检索结果）
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        relevant_laws=relevant_laws if relevant_laws else "（未检索到相关法律条文）",
        relevant_cases=relevant_cases if relevant_cases else "（未检索到相关案例）"
    )
    
    # 6. 组装消息历史
    messages = database.get_conversation_messages(conversation_id)
    chat_history = [
        {"role": "system", "content": system_prompt}
    ]
    for msg in messages:
        if not msg.get("is_image"):
            chat_history.append({"role": msg["role"], "content": msg["content"]})
    
    # 7. 调用 DeepSeek API
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": chat_history,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    # 使用禁用代理的 session 调用 DeepSeek API，添加重试机制
    try:
        print(f"发送请求到 DeepSeek，消息数: {len(chat_history)}")
        
        # 创建新的适配器，禁用代理并增加连接池
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # 创建重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
        )
        
        # 创建适配器并配置
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        response = session.post(
            DEEPSEEK_API_URL, 
            json=payload, 
            headers=headers, 
            timeout=(10, 60),  # 连接超时10秒，读取超时60秒
            verify=True  # 启用 SSL 验证
        )
        print(f"DeepSeek 响应状态: {response.status_code}")
        response.raise_for_status()
        resp_data = response.json()
        print(f"DeepSeek 响应成功")
        ai_reply = resp_data["choices"][0]["message"]["content"]
        
        # 8. 保存 AI 回复到数据库
        database.add_message(conversation_id, "assistant", ai_reply)
        
        return {
            "response": ai_reply,
            "conversation_id": conversation_id
        }
        
    except requests.exceptions.HTTPError as e:
        print(f"API 状态码错误: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail=f"大模型接口错误: {e.response.status_code}")
        
    except requests.exceptions.RequestException as e:
        print(f"网络请求报错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"网络错误: {str(e)}")
        
    except Exception as e:
        import traceback
        print(f"未知后端报错: {str(e)}")
        print(f"详细错误: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

# ==========================================
# 8. 豆包API图像识别函数
# ==========================================
def recognize_with_doubao(image_base64: str, file_type: str = "图片") -> str:
    """使用豆包API识别图片内容"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ARK_API_KEY}"
        }
        
        payload = {
            "model": ARK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": f"请仔细识别这张{file_type}中的所有文字内容和关键信息，完整提取并返回。如果这是合同、工资条、通知等文件，请按原格式整理返回。"
                        }
                    ]
                }
            ],
            "max_tokens": 2000
        }
        
        print(f"调用豆包API识别{file_type}...")
        response = session.post(
            ARK_API_URL,
            json=payload,
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"豆包API识别成功，内容长度: {len(content)}")
            return content
        else:
            print(f"豆包API错误: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"豆包API调用失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# ==========================================
# 9. 文件上传接口 - 使用豆包API识别图片和文档
# ==========================================
import io
import base64
from fastapi import UploadFile

@app.post("/api/upload")
async def upload_file(file: UploadFile):
    """解析上传的图片、PDF或Word文档（使用豆包API识别）"""
    try:
        filename = file.filename.lower()
        
        # 读取文件内容
        content = await file.read()
        
        # 图片文件：使用豆包API识别
        if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
            image_base64 = base64.b64encode(content).decode('utf-8')
            result = recognize_with_doubao(image_base64, "图片")
            if result:
                return {"success": True, "content": result, "type": "image"}
            else:
                return {"success": False, "content": "", "error": "图片识别失败，请手动描述内容"}
        
        # PDF文件：使用pdfplumber提取文字
        elif filename.endswith('.pdf'):
            try:
                import pdfplumber
                
                all_text = ""
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    for page_num, page in enumerate(pdf.pages[:10]):  # 最多10页
                        page_text = page.extract_text()
                        if page_text:
                            all_text += f"\n--- 第{page_num+1}页 ---\n{page_text}"
                
                if all_text.strip():
                    # 如果提取到文字，返回文字内容
                    return {"success": True, "content": all_text[:8000], "type": "pdf"}
                else:
                    return {"success": False, "content": "", "error": "PDF内容为空或无法提取文字"}
                    
            except ImportError:
                # 如果没有PyMuPDF，回退到pdfplumber
                import pdfplumber
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                
                if text.strip():
                    return {"success": True, "content": text[:5000], "type": "pdf"}
                else:
                    return {"success": False, "content": "", "error": "PDF内容为空"}
        
        # Word文件：先用docx解析文字，再识别图片
        elif filename.endswith(('.docx', '.doc')):
            from docx import Document
            doc = Document(io.BytesIO(content))
            text = "\n".join([p.text for p in doc.paragraphs])
            
            if text.strip():
                return {"success": True, "content": text[:5000], "type": "word"}
            else:
                return {"success": False, "content": "", "error": "Word文档内容为空"}
        
        # 文本文件：直接读取
        elif filename.endswith('.txt'):
            try:
                text = content.decode('utf-8')
                return {"success": True, "content": text[:5000], "type": "text"}
            except:
                try:
                    text = content.decode('gbk')
                    return {"success": True, "content": text[:5000], "type": "text"}
                except:
                    return {"success": False, "content": "", "error": "无法解码文本文件"}
        
        else:
            return {"success": False, "content": "", "error": f"不支持的文件类型: {filename}"}
    
    except Exception as e:
        print(f"文件解析错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "content": "", "error": f"解析失败: {str(e)}"}

# ==========================================
# 9. 挂载静态文件
# ==========================================
import os
# 获取项目根目录 (backend 的上一级)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    Timer(1.5, open_browser).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
