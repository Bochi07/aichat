"""
个人学习实验台 - 多模型支持
FastAPI + SQLite，明文密码，手机端优化
"""
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import stat
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from urllib.parse import urlparse

import aiohttp
import jwt
import aiosqlite
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# ============================================================
# 提供商配置（硬编码，无需用户填 URL）
# ============================================================
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
        "default_model": "deepseek-v4-pro",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen3.7-max", "qwen3.7-plus", "qwen3.6-flash",
            "qwen-max", "qwen-plus", "qwen-flash",
            "qwen-long-latest",
        ],
        "default_model": "qwen-plus",
    },
    "ernie": {
        "name": "文心",
        "base_url": "https://api.baiduqianfan.ai/v1",
        "models": [
            "ernie-5.1",
            "ernie-4.5-turbo-128k-preview",
            "ernie-4.0-turbo-8k",
            "ernie-4.0-turbo-128k",
            "ernie-3.5-8k",
            "ernie-speed-8k",
            "ernie-speed-128k",
            "ernie-lite-8k",
        ],
        "default_model": "ernie-4.0-turbo-8k",
    },
    "mimo": {
        "name": "小米 MiLM",
        "base_url": "https://api.xiaomimimo.com/v1",
        "models": ["mimo-v2-flash", "mimo-v2-pro", "mimo-v2.5-pro"],
        "default_model": "mimo-v2-flash",
    },
}

# ============================================================
# 配置
# ============================================================
try:
    from dotenv import load_dotenv
    _env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_file)
except ImportError:
    pass

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3210"))
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "data.db")
JWT_EXPIRE_SECONDS = 30 * 24 * 3600
MAX_SESSIONS = 5
MAX_HISTORY = 30      # 每次发送携带的最大历史消息条数，超出后省略更早的
MAX_MSG_CHARS = 6000  # 单条历史消息超过该长度时截断

if not SECRET_KEY:
    raise RuntimeError(
        "\n!!! 未设置 SECRET_KEY，拒绝启动 !!!\n"
        "请执行: echo \"SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')\" >> .env\n"
    )

app = FastAPI(title="个人学习实验台", docs_url=None, redoc_url=None)

base_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")
TEMPLATES_DIR = os.path.join(base_dir, "templates")

# ============================================================
# Token 黑名单
# ============================================================
TOKEN_BLACKLIST = {}

def _revoke_token(jti: str, exp: int):
    TOKEN_BLACKLIST[jti] = exp

def _is_token_revoked(jti: str) -> bool:
    return jti in TOKEN_BLACKLIST

def _cleanup_blacklist():
    now = int(time.time())
    for k in [k for k, v in TOKEN_BLACKLIST.items() if v <= now]:
        del TOKEN_BLACKLIST[k]

# ============================================================
# 简易内存限流（按 IP / 用户）
# ============================================================
_RATE_LIMITS = defaultdict(deque)   # key -> 最近请求时间戳队列

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _rate_limit(key: str, limit: int, window: int):
    """滑动窗口：window 秒内最多 limit 次，超出抛 429"""
    now = time.time()
    # 周期性清扫：key 过多时移除已超过 1 小时无活动的记录，避免内存无限增长
    if len(_RATE_LIMITS) > 1000:
        for k in [k for k, q in list(_RATE_LIMITS.items()) if not q or q[-1] <= now - 3600]:
            del _RATE_LIMITS[k]
    q = _RATE_LIMITS[key]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "操作过于频繁，请稍后再试")
    q.append(now)

# ============================================================
# 数据库
# ============================================================
async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def fetch_all(db: aiosqlite.Connection, sql: str, params: tuple = ()):
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

async def fetch_one(db: aiosqlite.Connection, sql: str, params: tuple = ()):
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    return dict(row) if row else None

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            qq TEXT NOT NULL DEFAULT '',
            pwd_changed_at INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            jti TEXT UNIQUE NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL DEFAULT 'deepseek',
            name TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL,
            base_url TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, provider)
        );
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '新实验',
            system_prompt TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            reasoning TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
        CREATE INDEX IF NOT EXISTS idx_msgs_chat ON messages(chat_id);
        CREATE INDEX IF NOT EXISTS idx_apikeys_user ON api_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    # 兼容旧数据库
    try:
        await db.execute("ALTER TABLE api_keys ADD COLUMN provider TEXT NOT NULL DEFAULT 'deepseek'")
        await db.commit()
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE messages ADD COLUMN reasoning TEXT NOT NULL DEFAULT ''")
        await db.commit()
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN qq TEXT NOT NULL DEFAULT ''")
        await db.commit()
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE users ADD COLUMN pwd_changed_at INTEGER NOT NULL DEFAULT 0")
        await db.commit()
    except Exception:
        pass
    await db.close()

    try:
        os.chmod(DB_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

# ============================================================
# JWT
# ============================================================
def create_token(user_id: int, pwd_changed_at: int) -> str:
    now = datetime.utcnow()
    exp = now + timedelta(seconds=JWT_EXPIRE_SECONDS)
    return jwt.encode({
        "user_id": user_id,
        "pwd_ver": pwd_changed_at,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": exp,
    }, SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(401, "未登录")
    data = decode_token(token)
    if not data:
        raise HTTPException(401, "登录已过期")
    if _is_token_revoked(data.get("jti", "")):
        raise HTTPException(401, "令牌已注销，请重新登录")
    _cleanup_blacklist()
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT * FROM users WHERE id=?", (data["user_id"],))
        if not row:
            raise HTTPException(401, "用户不存在")
        if data.get("pwd_ver", 0) != row["pwd_changed_at"]:
            raise HTTPException(401, "登录已过期，请重新登录")
        return row
    finally:
        await db.close()

async def _enforce_session_limit(user_id: int, current_jti: str):
    db = await get_db()
    try:
        sessions = await fetch_all(db,
            "SELECT jti, created_at FROM sessions WHERE user_id=? ORDER BY created_at ASC", (user_id,))
        if len(sessions) >= MAX_SESSIONS:
            to_remove = sessions[:len(sessions) - MAX_SESSIONS + 1]
            for s in to_remove:
                old = await fetch_one(db, "SELECT jti FROM sessions WHERE jti=?", (s["jti"],))
                if old:
                    TOKEN_BLACKLIST[old["jti"]] = int(time.time()) + JWT_EXPIRE_SECONDS
                    await db.execute("DELETE FROM sessions WHERE jti=?", (old["jti"],))
        await db.execute("INSERT INTO sessions (user_id, jti, created_at) VALUES (?,?,?)",
                         (user_id, current_jti, int(time.time())))
        await db.commit()
    finally:
        await db.close()

async def _remove_session(jti: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM sessions WHERE jti=?", (jti,))
        await db.commit()
    finally:
        await db.close()

# ============================================================
# 验证码
# ============================================================
def _gen_captcha() -> tuple[str, str]:
    a, b = random.randint(1, 9), random.randint(1, 9)
    question = f"{a} + {b} = ?"
    answer = str(a + b)
    sig = hmac.new(SECRET_KEY.encode(), answer.encode(), hashlib.sha256).hexdigest()[:16]
    return question, f"{sig}:{answer}"

def _verify_captcha(signed: str) -> bool:
    try:
        sig, answer = signed.split(":", 1)
        expected = hmac.new(SECRET_KEY.encode(), answer.encode(), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False

_USED_CAPTCHAS = set()

def _verify_captcha_flow(captcha_signed: str, captcha_answer: str):
    """校验并消耗验证码（供注册/找回密码共用）"""
    if not captcha_signed or not captcha_answer:
        raise HTTPException(400, "请输入验证码")
    if not _verify_captcha(captcha_signed):
        raise HTTPException(400, "验证码错误或已过期")
    if captcha_answer.strip() != captcha_signed.split(":", 1)[1]:
        raise HTTPException(400, "验证码答案错误")
    if captcha_signed in _USED_CAPTCHAS:
        raise HTTPException(400, "验证码已使用")
    _USED_CAPTCHAS.add(captcha_signed)

# ============================================================
# 安全中间件
# ============================================================
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path.endswith((".db", ".sqlite", ".sqlite3", ".env", ".py", ".pyc")):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
        "img-src 'self' data:; font-src 'self'; form-action 'self'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    """同源校验：写请求若携带 Origin/Referer 则必须与 Host 同主机，否则拒绝（CSRF 防护）。
    仅比较主机名、忽略端口，兼容反向代理改写 Host 及 IPv6。"""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        host_header = request.headers.get("host", "")
        host_name = (urlparse(f"//{host_header}").hostname or "").lower()
        for h in (request.headers.get("origin"), request.headers.get("referer")):
            if not h:
                continue
            try:
                origin_name = (urlparse(h).hostname or "").lower()
            except Exception:
                origin_name = ""
            if origin_name != host_name:
                return JSONResponse({"detail": "跨站请求被拒绝"}, status_code=403)
    return await call_next(request)

@app.middleware("http")
async def inject_user(request: Request, call_next):
    request.state.user = None
    token = request.cookies.get("token")
    if token:
        data = decode_token(token)
        if data and not _is_token_revoked(data.get("jti", "")):
            db = await get_db()
            try:
                row = await fetch_one(db, "SELECT * FROM users WHERE id=?", (data["user_id"],))
                if row and data.get("pwd_ver", 0) == row["pwd_changed_at"]:
                    request.state.user = row
            finally:
                await db.close()
    return await call_next(request)

# ============================================================
# 输入校验
# ============================================================
_USERNAME_RE = re.compile(r'^[\w\u4e00-\u9fff\-]{1,30}$')
_MODEL_RE = re.compile(r'^[a-zA-Z0-9\-_\.]{1,64}$')
_QQ_RE = re.compile(r'^\d{5,11}$')

def _check_username(username: str):
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "用户名仅支持中英文、数字、下划线、连字符，最长30字符")

def _check_password(password: str):
    if not password or len(password) > 128:
        raise HTTPException(400, "密码需要1-128个字符")

def _check_qq(qq: str):
    if not _QQ_RE.match(qq):
        raise HTTPException(400, "QQ号格式不正确（5-11位数字）")

def _check_message(message: str):
    if len(message) > 50000:
        raise HTTPException(400, "消息过长")

def _check_title(title: str):
    if len(title) > 100:
        raise HTTPException(400, "标题最长100字符")

def _check_system_prompt(sp: str):
    if len(sp) > 10000:
        raise HTTPException(400, "实验参数最长10000字符")

def _check_model(model: str):
    if model and not _MODEL_RE.match(model):
        raise HTTPException(400, "模型名称格式不正确")

def _check_api_key_format(key: str):
    if not key or len(key) < 3:
        raise HTTPException(400, "访问密钥 不能为空")

_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
             "Pragma": "no-cache", "Expires": "0"}

def _html(file_name: str):
    """读取 HTML 文件并以 UTF-8 编码返回"""
    path = os.path.join(TEMPLATES_DIR, file_name)
    with open(path, "r", encoding="utf-8") as f:
        resp = HTMLResponse(content=f.read())
    resp.headers.update(_NO_CACHE)
    return resp

# ============================================================
# 页面路由
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not request.state.user:
        return RedirectResponse("login")
    return _html("chat.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.state.user:
        return RedirectResponse("./")
    return _html("login.html")

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not request.state.user:
        return RedirectResponse("login")
    return _html("settings.html")

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

# ============================================================
# 认证 API
# ============================================================
@app.get("/api/auth/captcha")
async def get_captcha(request: Request):
    _rate_limit(f"captcha:{_client_ip(request)}", 30, 60)
    question, signed = _gen_captcha()
    return JSONResponse({"question": question, "signed": signed})

@app.post("/api/auth/signup")
async def signup(request: Request, username: str = Form(...), password: str = Form(...),
                 qq: str = Form(...), captcha_signed: str = Form(""), captcha_answer: str = Form(""),
                 honey: str = Form("")):
    username = username.strip()
    qq = qq.strip()
    _check_username(username)
    _check_password(password)
    _check_qq(qq)
    _rate_limit(f"signup:{_client_ip(request)}", 5, 300)
    if honey:
        raise HTTPException(400, "注册失败，请重试")
    _verify_captcha_flow(captcha_signed, captcha_answer)
    db = await get_db()
    try:
        now = int(time.time())
        try:
            cursor = await db.execute(
                "INSERT INTO users (username, password, qq, created_at, pwd_changed_at) VALUES (?,?,?,?,?)",
                (username, password, qq, now, now))
            await db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(400, "注册失败，请重试")
        user_id = cursor.lastrowid
        token = create_token(user_id, now)
        jti = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])["jti"]
        await _enforce_session_limit(user_id, jti)
        resp = JSONResponse({"ok": True, "message": "注册成功"})
        resp.set_cookie("token", token, max_age=JWT_EXPIRE_SECONDS,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https")
        return resp
    finally:
        await db.close()

@app.post("/api/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    _check_username(username)
    _check_password(password)
    ip = _client_ip(request)
    _rate_limit(f"login:{ip}", 10, 300)
    _rate_limit(f"login:{ip}:{username}", 5, 300)
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT * FROM users WHERE username=?", (username,))
        if not row or row["password"] != password:
            if not row:
                _ = password + "unused_salt_for_timing"
            raise HTTPException(400, "用户名或密码错误")
        token = create_token(row["id"], row["pwd_changed_at"])
        jti = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])["jti"]
        await _enforce_session_limit(row["id"], jti)
        resp = JSONResponse({"ok": True, "message": "登录成功"})
        resp.set_cookie("token", token, max_age=JWT_EXPIRE_SECONDS,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https")
        return resp
    finally:
        await db.close()

@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get("token")
    if token:
        data = decode_token(token)
        if data:
            _revoke_token(data.get("jti", ""), data.get("exp", 0))
            await _remove_session(data.get("jti", ""))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token")
    return resp

@app.get("/api/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return JSONResponse({"username": user["username"]})

@app.put("/api/auth/password")
async def change_password(request: Request):
    user = await get_current_user(request)
    data = await request.json()
    new_password = (data.get("password") or "").strip()
    _check_password(new_password)
    db = await get_db()
    try:
        await db.execute("UPDATE users SET password=? WHERE id=?", (new_password, user["id"]))
        await db.commit()
        return JSONResponse({"ok": True, "message": "密码已修改"})
    finally:
        await db.close()

@app.delete("/api/auth/account")
async def delete_account(request: Request):
    """注销账号：需输入确认文字"""
    user = await get_current_user(request)
    data = await request.json()
    confirm = (data.get("confirm") or "").strip()
    if confirm != "确认注销此账号":
        raise HTTPException(400, "请输入正确的确认文字")
    db = await get_db()
    try:
        # 删除关联数据
        await db.execute("DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE user_id=?)", (user["id"],))
        await db.execute("DELETE FROM chats WHERE user_id=?", (user["id"],))
        await db.execute("DELETE FROM api_keys WHERE user_id=?", (user["id"],))
        await db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        await db.execute("DELETE FROM users WHERE id=?", (user["id"],))
        await db.commit()
        resp = JSONResponse({"ok": True, "message": "账号已注销"})
        resp.delete_cookie("token")
        return resp
    finally:
        await db.close()

@app.get("/api/auth/qq")
async def get_qq(request: Request):
    user = await get_current_user(request)
    return JSONResponse({"qq": user["qq"]})

@app.put("/api/auth/qq")
async def update_qq(request: Request):
    user = await get_current_user(request)
    data = await request.json()
    qq = (data.get("qq") or "").strip()
    _check_qq(qq)
    db = await get_db()
    try:
        await db.execute("UPDATE users SET qq=? WHERE id=?", (qq, user["id"]))
        await db.commit()
        return JSONResponse({"ok": True, "message": "QQ已更新"})
    finally:
        await db.close()

@app.post("/api/auth/forgot-password")
async def forgot_password(request: Request, username: str = Form(...), qq: str = Form(...),
                          new_password: str = Form(...),
                          captcha_signed: str = Form(""), captcha_answer: str = Form("")):
    """忘记密码：校验 用户名+绑定的QQ+验证码 后重置密码"""
    username = username.strip()
    qq = qq.strip()
    _check_username(username)
    _check_password(new_password)
    _check_qq(qq)
    _rate_limit(f"forgot:{_client_ip(request)}", 5, 300)
    _verify_captcha_flow(captcha_signed, captcha_answer)
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT * FROM users WHERE username=?", (username,))
        if not row or row["qq"] != qq:
            raise HTTPException(400, "重置失败，请检查用户名与绑定的QQ")
        now = int(time.time())
        await db.execute("UPDATE users SET password=?, pwd_changed_at=? WHERE id=?",
                         (new_password, now, row["id"]))
        await db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
        await db.commit()
        return JSONResponse({"ok": True, "message": "密码已重置，请使用新密码登录"})
    finally:
        await db.close()

# ============================================================
# 访问密钥（多提供商）
# ============================================================
@app.get("/api/keys")
async def list_keys(request: Request):
    """返回所有提供商的 Key 状态"""
    user = await get_current_user(request)
    db = await get_db()
    try:
        keys = await fetch_all(db,
            "SELECT provider, api_key, created_at FROM api_keys WHERE user_id=?", (user["id"],))
        key_map = {k["provider"]: k for k in keys}
        result = {}
        for pid, pinfo in PROVIDERS.items():
            result[pid] = {
                "name": pinfo["name"],
                "has_key": pid in key_map,
                "api_key": key_map[pid]["api_key"] if pid in key_map else "",
            }
        return JSONResponse(result)
    finally:
        await db.close()

@app.post("/api/keys")
async def create_key(request: Request):
    """保存某个提供商的 Key"""
    user = await get_current_user(request)
    data = await request.json()
    provider = (data.get("provider") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    if provider not in PROVIDERS:
        raise HTTPException(400, "未知提供商")
    if not api_key:
        raise HTTPException(400, "访问密钥 不能为空")
    _check_api_key_format(api_key)
    db = await get_db()
    try:
        # 只允许 1 个 Key，新 Key 顶掉旧的
        await db.execute("DELETE FROM api_keys WHERE user_id=?", (user["id"],))
        now = int(time.time())
        await db.execute(
            "INSERT INTO api_keys (user_id, provider, name, api_key, base_url, created_at) VALUES (?,?,?,?,?,?)",
            (user["id"], provider, PROVIDERS[provider]["name"], api_key, PROVIDERS[provider]["base_url"], now))
        await db.commit()
        return JSONResponse({"ok": True, "message": f"{PROVIDERS[provider]['name']} Key 已保存"})
    finally:
        await db.close()

@app.delete("/api/keys/{provider}")
async def delete_key(provider: str, request: Request):
    """删除某个提供商的 Key"""
    user = await get_current_user(request)
    if provider not in PROVIDERS:
        raise HTTPException(404)
    db = await get_db()
    try:
        await db.execute("DELETE FROM api_keys WHERE user_id=? AND provider=?", (user["id"], provider))
        await db.commit()
        return JSONResponse({"ok": True})
    finally:
        await db.close()

# ============================================================
# 提供商信息
# ============================================================
@app.get("/api/providers")
async def list_providers():
    """返回所有提供商及其模型"""
    return JSONResponse({
        pid: {"name": pinfo["name"], "models": pinfo["models"], "default_model": pinfo["default_model"]}
        for pid, pinfo in PROVIDERS.items()
    })

# ============================================================
# 聊天管理
# ============================================================
@app.get("/api/chats")
async def list_chats(request: Request, search: str = ""):
    user = await get_current_user(request)
    db = await get_db()
    try:
        keyword = search.strip()
        if keyword:
            chats = await fetch_all(db, """
                SELECT c.id, c.title, c.updated_at, m.id as hit_msg_id, m.content as hit_snippet
                FROM chats c
                JOIN messages m ON c.id = m.chat_id
                WHERE c.user_id = ? AND m.content LIKE ?
                ORDER BY c.updated_at DESC, m.created_at ASC
            """, (user["id"], f'%{keyword}%'))
        else:
            chats = await fetch_all(db,
                "SELECT * FROM chats WHERE user_id=? ORDER BY updated_at DESC", (user["id"],))
        return JSONResponse(chats)
    finally:
        await db.close()

@app.post("/api/chats")
async def create_chat(request: Request):
    user = await get_current_user(request)
    data = await request.json()
    title = (data.get("title") or "新实验").strip() or "新实验"
    system_prompt = (data.get("system_prompt") or "").strip()
    _check_title(title)
    _check_system_prompt(system_prompt)
    db = await get_db()
    try:
        now = int(time.time())
        cursor = await db.execute(
            "INSERT INTO chats (user_id, title, system_prompt, created_at, updated_at) VALUES (?,?,?,?,?)",
            (user["id"], title, system_prompt, now, now))
        await db.commit()
        return JSONResponse({"ok": True, "id": cursor.lastrowid})
    finally:
        await db.close()

@app.put("/api/chats/{chat_id}")
async def update_chat(chat_id: int, request: Request):
    user = await get_current_user(request)
    data = await request.json()
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user["id"]))
        if not row:
            raise HTTPException(404, "对话不存在")
        title = (data.get("title") or row["title"]).strip() or "新实验"
        system_prompt = (data.get("system_prompt") or row["system_prompt"]).strip()
        _check_title(title)
        _check_system_prompt(system_prompt)
        now = int(time.time())
        await db.execute(
            "UPDATE chats SET title=?, system_prompt=?, updated_at=? WHERE id=? AND user_id=?",
            (title, system_prompt, now, chat_id, user["id"]))
        await db.commit()
        return JSONResponse({"ok": True})
    finally:
        await db.close()

@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, request: Request):
    user = await get_current_user(request)
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE id=? AND user_id=?)",
            (chat_id, user["id"]))
        await db.execute("DELETE FROM chats WHERE id=? AND user_id=?", (chat_id, user["id"]))
        await db.commit()
        return JSONResponse({"ok": True})
    finally:
        await db.close()

# ============================================================
# 消息 API
# ============================================================
@app.get("/api/chats/{chat_id}/messages")
async def get_messages(chat_id: int, request: Request):
    user = await get_current_user(request)
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user["id"]))
        if not row:
            raise HTTPException(404, "对话不存在")
        msgs = await fetch_all(db,
            "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
        return JSONResponse(msgs)
    finally:
        await db.close()

@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int, request: Request):
    user = await get_current_user(request)
    db = await get_db()
    try:
        row = await fetch_one(db, """
            SELECT m.id FROM messages m JOIN chats c ON m.chat_id = c.id
            WHERE m.id = ? AND c.user_id = ?
        """, (msg_id, user["id"]))
        if not row:
            raise HTTPException(404, "消息不存在")
        await db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
        await db.commit()
        return JSONResponse({"ok": True})
    finally:
        await db.close()

# ============================================================
# AI 聊天
# ============================================================
@app.post("/api/chats/{chat_id}/send")
async def send_message(chat_id: int, request: Request):
    user = await get_current_user(request)
    _rate_limit(f"send:u{user['id']}", 30, 60)

    data = await request.json()
    message = (data.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")
    _check_message(message)

    model = (data.get("model") or "deepseek-v4-pro").strip()
    _check_model(model)
    provider = (data.get("provider") or "deepseek").strip()
    if provider not in PROVIDERS:
        raise HTTPException(400, "未知提供商")
    deep_thinking = data.get("deep_thinking", False)

    # 获取对应提供商的 Key
    db = await get_db()
    try:
        chat_row = await fetch_one(db, "SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user["id"]))
        if not chat_row:
            raise HTTPException(404, "对话不存在")

        key_row = await fetch_one(db,
            "SELECT * FROM api_keys WHERE user_id=? AND provider=? LIMIT 1", (user["id"], provider))
        if not key_row:
            raise HTTPException(400, f"请先在设置中添加 {PROVIDERS[provider]['name']} 的 访问密钥")
        api_key = key_row["api_key"]
        base_url = key_row["base_url"] or PROVIDERS[provider]["base_url"]
    finally:
        await db.close()

    now = int(time.time())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO messages (chat_id, role, content, reasoning, created_at) VALUES (?,?,?,?,?)",
            (chat_id, "user", message, "", now))
        await db.execute("UPDATE chats SET updated_at=? WHERE id=?", (now, chat_id))
        await db.commit()
        history = await fetch_all(db,
            "SELECT role, content FROM messages WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
    finally:
        await db.close()

    omitted = 0
    if len(history) > MAX_HISTORY:
        omitted = len(history) - MAX_HISTORY
        history = history[-MAX_HISTORY:]
    history = list(history)
    for m in history:
        if len(m["content"]) > MAX_MSG_CHARS:
            m["content"] = m["content"][:MAX_MSG_CHARS] + "\n…（该条内容已截断）"

    openai_messages = []
    system_prompt = chat_row.get("system_prompt", "")
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})
    for m in history:
        openai_messages.append({"role": m["role"], "content": m["content"]})

    async def stream_response():
        collected = ""
        reasoning_text = ""
        error_msg = ""
        try:
            if omitted:
                yield f"data: {json.dumps({'notice': f'已省略更早的 {omitted} 条消息（如需完整上下文可新开对话）'})}\n\n"
            async with aiohttp.ClientSession() as session:
                api_url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {"model": model, "messages": openai_messages, "stream": True}
                # 深度分析开关：开 = 深度思考，关 = 快速回答（显式关闭思考）
                if provider == "deepseek":
                    payload["thinking"] = {"type": "enabled" if deep_thinking else "disabled"}
                    if deep_thinking:
                        payload["reasoning_effort"] = "high"
                if provider == "mimo":
                    payload["enable_thinking"] = deep_thinking
                if provider == "qwen":
                    payload["enable_thinking"] = deep_thinking
                async with session.post(api_url, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        try:
                            err_body = await resp.text()
                            err_text = err_body[:500]
                        except Exception:
                            err_text = f"HTTP {resp.status}"
                        error_msg = f"[{resp.status}] {err_text}"
                        yield f"data: {json.dumps({'error': error_msg})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    async for raw_line in resp.content:
                        line = raw_line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            chunk = line[6:]
                            if chunk == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(chunk)
                                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                reasoning = delta.get("reasoning_content", "")
                                if reasoning:
                                    reasoning_text += reasoning
                                    yield f"data: {json.dumps({'reasoning': reasoning})}\n\n"
                                if content:
                                    collected += content
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            error_msg = f"请求异常: {str(e)[:500]}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
        finally:
            save_content = collected if collected else f"❌ {error_msg}" if error_msg else ""
            msg_id = None
            if save_content:
                db2 = await get_db()
                try:
                    cur = await db2.execute(
                        "INSERT INTO messages (chat_id, role, content, reasoning, created_at) VALUES (?,?,?,?,?)",
                        (chat_id, "assistant", save_content,
                         reasoning_text if deep_thinking else "", int(time.time())))
                    msg_id = cur.lastrowid
                    await db2.execute("UPDATE chats SET updated_at=? WHERE id=?", (int(time.time()), chat_id))
                    await db2.commit()
                finally:
                    await db2.close()
            if msg_id:
                yield f"data: {json.dumps({'saved_id': msg_id})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")

# ============================================================
# 启动
# ============================================================
@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    try:
        db = await aiosqlite.connect(DB_PATH)
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db.close()
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
