# 个人学习实验台（Personal Learning Lab）

一个轻量级的 AI 聊天前端，支持**多模型提供商**，使用 FastAPI + SQLite 构建，手机端优先设计。

## 支持的 AI 提供商

| 提供商 | 模型示例 |
|--------|----------|
| **DeepSeek** | deepseek-v4-pro, deepseek-v4-flash |
| **通义千问 (Qwen)** | qwen3.7-max, qwen-max, qwen-plus, qwen-flash |
| **文心 (Ernie)** | ernie-5.1, ernie-4.5-turbo, ernie-4.0-turbo, ernie-speed |
| **小米 MiLM** | mimo-v2-flash, mimo-v2-pro, mimo-v2.5-pro |

## 功能

- 🧪 **多模型实验台** — 一台多用，切换不同 AI 提供商进行对比实验
- 📱 **手机优先** — 响应式设计，手机上体验完整功能
- 💬 **多轮对话** — 保存历史对话，支持搜索
- 🔬 **深度思考模式** — 支持 DeepSeek/千问/小米的推理链展开
- 🔑 **API Key 管理** — 可视化管理各提供商的访问密钥
- 🐳 **Docker 部署** — 一条命令即可部署

## 技术栈

- **后端**: Python 3.12+ / FastAPI / aiosqlite
- **前端**: 原生 HTML/CSS/JS（无框架依赖）
- **数据库**: SQLite（WAL 模式）
- **认证**: JWT (HS256) + 验证码
- **部署**: Docker / Gunicorn / uWSGI

## 快速开始

### 本地运行

```bash
# 1. 克隆项目
git clone https://github.com/yourname/aichat.git
cd aichat

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 生成 SECRET_KEY（重要！）
echo "SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')" > .env

# 5. 启动
python main.py
# 访问 http://localhost:3210
```

### Docker 部署

```bash
# 修改 docker-compose.yml 中的 SECRET_KEY 为随机字符串
# 然后：
docker-compose up -d
# 访问 http://localhost:3210
```

## 项目结构

```
aichat/
├── main.py               # FastAPI 主程序（单文件）
├── requirements.txt      # Python 依赖
├── templates/
│   ├── chat.html         # 聊天页面
│   ├── login.html        # 登录注册页面
│   └── settings.html     # API Key 管理页面
├── static/
│   └── style.css         # 手机优先样式表
├── Dockerfile            # Docker 构建
├── docker-compose.yml    # Docker Compose
├── gunicorn_conf.py      # Gunicorn 生产配置
└── uwsgi.ini             # uWSGI 生产配置
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SECRET_KEY` | ✅ 是 | JWT 签名密钥，至少 32 位随机字符串 |
| `HOST` | 否 | 监听地址，默认 `0.0.0.0` |
| `PORT` | 否 | 监听端口，默认 `3210` |
| `DATA_DIR` | 否 | 数据目录，默认当前目录 |

## ⚠️ 安全声明

本项目是一个**个人学习用途**的实验台，存在以下设计上的安全取舍：

1. **密码明文存储** — 用户密码未经过 bcrypt/scrypt 哈希，直接以明文存入 SQLite
2. **API Key 明文存储** — 各提供商的 API Key 以明文存入数据库
3. **内存 Token 黑名单** — JWT 注销机制使用内存存储，重启后失效

这些设计是为了保持代码简洁、易于理解和修改。**如果用于生产环境，请自行添加密码哈希和加密存储。**

## License

MIT License — 详见 [LICENSE](LICENSE)
