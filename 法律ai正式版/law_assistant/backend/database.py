# 数据库连接和模型定义
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import hashlib
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "law_assistant.db")

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建对话表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '新对话',
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # 创建消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            is_image INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print("数据库初始化完成")

# ============ 用户相关操作 ============

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username: str, password: str, email: str = None, phone: str = None) -> Dict:
    """创建用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), email, phone)
        )
        conn.commit()
        user_id = cursor.lastrowid
        
        # 自动创建第一个对话
        cursor.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, "新对话")
        )
        conn.commit()
        conversation_id = cursor.lastrowid
        
        return {
            "id": user_id,
            "username": username,
            "conversation_id": conversation_id
        }
    except sqlite3.IntegrityError:
        return {"error": "用户名已存在"}
    finally:
        conn.close()

def verify_user(username: str, password: str) -> Optional[Dict]:
    """验证用户登录"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """根据 ID 获取用户"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, email, phone, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    return dict(user) if user else None

# ============ 对话相关操作 ============

def get_user_conversations(user_id: int) -> List[Dict]:
    """获取用户所有对话"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT id, title, is_pinned, created_at, updated_at 
           FROM conversations 
           WHERE user_id = ? 
           ORDER BY is_pinned DESC, updated_at DESC""",
        (user_id,)
    )
    conversations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return conversations

def create_conversation(user_id: int, title: str = "新对话") -> Dict:
    """创建新对话"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user_id, title)
    )
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    
    return {
        "id": conversation_id,
        "title": title,
        "user_id": user_id
    }

def update_conversation(conversation_id: int, title: str = None, is_pinned: int = None) -> bool:
    """更新对话"""
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if is_pinned is not None:
        updates.append("is_pinned = ?")
        params.append(is_pinned)
    
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(conversation_id)
        
        cursor.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
    
    conn.close()
    return True

def delete_conversation(conversation_id: int) -> bool:
    """删除对话"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    
    return True

# ============ 消息相关操作 ============

def get_conversation_messages(conversation_id: int) -> List[Dict]:
    """获取对话的所有消息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT id, role, content, is_image, created_at 
           FROM messages 
           WHERE conversation_id = ? 
           ORDER BY created_at ASC""",
        (conversation_id,)
    )
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return messages

def add_message(conversation_id: int, role: str, content: str, is_image: bool = False) -> Dict:
    """添加消息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, is_image) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, 1 if is_image else 0)
    )
    conn.commit()
    message_id = cursor.lastrowid
    
    # 更新对话时间
    cursor.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conversation_id,)
    )
    conn.commit()
    conn.close()
    
    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content
    }

def delete_message(message_id: int) -> bool:
    """删除消息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    
    return True
