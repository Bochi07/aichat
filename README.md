# AI角色扮演聊天平台

一个轻量级的 AI 聊天前端，支持**多模型提供商**，使用 FastAPI + SQLite 构建，手机端优先设计。

本文档前半部分为**项目介绍与功能展示**，后半部分为**部署、排错与维护**。

## 目录

**功能部分**
- [支持的 AI 提供商](#支持的-ai-提供商)
- [功能](#功能)
- [效果截图](#效果截图)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [环境变量](#环境变量)

**部署部分**
- [Docker 部署](#docker-部署)
- [常见启动错误](#常见启动错误)
- [运行时错误](#运行时错误)
- [自定义修改指南](#自定义修改指南)
- [更新与维护](#更新与维护)
- [部署检查清单](#部署检查清单)
- [安全声明](#安全声明)

---

# 功能部分

## 支持的 AI 提供商

| 提供商 | 模型示例 |
|--------|----------|
| **DeepSeek** | deepseek-v4-pro, deepseek-v4-flash |
| **通义千问 (Qwen)** | qwen3.7-max, qwen-max, qwen-plus, qwen-flash |
| **文心 (Ernie)** | ernie-5.1, ernie-4.5-turbo, ernie-4.0-turbo, ernie-speed |
| **小米 MiLM** | mimo-v2-flash, mimo-v2-pro, mimo-v2.5-pro |

## 功能

- 🧪 **支持多模型调用** — 一台多用，支持切换不同 AI 提供商进行使用
- 📱 **手机优先** — 响应式设计，特意针对手机的分辨率优化，手机上显示效果更好
- 💬 **多轮对话** — 保存历史对话，支持搜索，AI的回复使用内建轻量Markdown渲染器渲染
- 🔬 **深度思考模式** — 支持 DeepSeek/千问/小米的推理链展开
- 🔑 **API Key 管理** — 可视化管理各提供商的访问密钥
- 🔐 **绑定QQ / 忘记密码** — 注册时绑定 QQ，可通过 QQ 验证重置密码
- 🛡️ **访问限流 / CSRF 防护** — 登录、注册、发送均限流，写请求做同源校验
- 📵 **会话管理** — 任意设备进行问答操作后，同账号其他设备自动下线
- 🐳 **Docker 部署** — 一条命令启动（详见部署部分）

> 📌 **忘记密码**依赖注册时绑定的 QQ 号。老用户升级后需先在「设置 → 绑定QQ」填写一次，才可使用忘记密码功能。

## 效果截图

<img width="2866" height="1610" alt="image" src="https://github.com/user-attachments/assets/4da0f69f-8237-44e3-9eb7-26cf21ecf5f0" />

## 技术栈

- **后端**: Python 3.10+ / FastAPI / aiosqlite
- **前端**: 原生 HTML/CSS/JS（无框架依赖）
- **数据库**: SQLite（WAL 模式）
- **认证**: JWT (HS256) + 验证码
- **部署**: Docker（推荐）/ 本地运行

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
├── gunicorn_conf.py      # Gunicorn 配置（可选，Docker 部署无需使用）
└── uwsgi.ini             # uWSGI 配置（可选，FastAPI 不推荐用）
```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `SECRET_KEY` | ✅ 是 | 无 | JWT 签名密钥，至少 32 位随机字符串，部署前务必修改占位符 |
| `HOST` | 否 | `0.0.0.0` | 监听地址 |
| `PORT` | 否 | `3210` | 监听端口 |
| `DATA_DIR` | 否 | 项目目录 | 数据目录；Docker 下为 `/app/data`（对应宿主机 `./data`） |

---

# 部署部分

## Docker 部署

> 新版 Docker 使用 `docker compose`（无连字符）子命令；只有老版本才用 `docker-compose`。下文统一用新版写法。

#### 前置条件：安装 Docker

**已安装的跳过本节。** Ubuntu / Debian 系统一行安装：

```bash
curl -fsSL https://get.docker.com | bash -s docker
sudo systemctl enable --now docker
```

验证：

```bash
sudo docker run --rm hello-world   # 能输出 Hello from Docker! 即成功
```

#### 生成并配置 SECRET_KEY

生成随机密钥（任选一种）：

```bash
openssl rand -hex 32                                          # 推荐，无需 Python
python3 -c 'import secrets;print(secrets.token_hex(32))'      # 有 Python 时
```

编辑 `docker-compose.yml`，把第 9 行占位符替换为上面生成的字符串：

```yaml
environment:
  - SECRET_KEY=粘贴你生成的随机字符串
```

> ⚠️ 占位符也能启动，但等于把登录凭证公开，**必须改**。改了之后之前的登录状态会全部失效，属正常现象。

#### 构建并启动

```bash
cd /你的项目路径/aichat
docker compose up -d --build
```

#### 验证与日志

```bash
docker compose ps            # 状态应为 Up
docker compose logs aichat   # 首次启动应看到 Uvicorn running on http://0.0.0.0:3210
docker compose logs -f aichat  # 持续跟踪日志（Ctrl+C 退出）
```

浏览器访问 **http://服务器公网IP:3210**   （本机部署访问 `http://localhost:3210`）。

#### 公网访问放行端口（最容易漏的一步）

容器起来但公网打不开，99% 是端口没放行，检查两处：

```bash
# ① 服务器防火墙（使用 firewalld 时）
sudo firewall-cmd --add-port=3210/tcp --permanent && sudo firewall-cmd --reload

# 使用 ufw 时
sudo ufw allow 3210/tcp
```

② 云控制台（阿里云/腾讯云/华为云等）→ **安全组** → 添加入方向规则：**端口 3210/TCP，来源 0.0.0.0/0**。

#### 数据持久化与备份

`docker-compose.yml` 已将宿主机的 `./data` 挂载到容器内 `/app/data`。数据库文件 `data.db` 保存在宿主机项目目录下的 `data/` 中。

- **停止/重建容器数据不丢**：`docker compose down` 不会删除 `data/`。
- **备份**：直接备份 `data/` 文件夹即可（必要时连同 `docker-compose.yml` 一起）。

```bash
cp -r data "data.bak.$(date +%Y%m%d)"
```

- **彻底删除（含数据）**：`docker compose down -v`（⚠️ 会删掉 volume，慎用）。

#### 停止与更新

```bash
# 停止（数据保留）
docker compose down

# 更新代码后重新构建并启动
git pull origin main
docker compose up -d --build
```

## 常见启动错误

### ❌ `未设置 SECRET_KEY，拒绝启动`

**完整报错**：
```
RuntimeError: !!! 未设置 SECRET_KEY，拒绝启动 !!!
```

**原因**：没有创建 `.env` 文件，或 `.env` 中没有 `SECRET_KEY`（本地运行）；或 docker-compose 未设置该环境变量（Docker 部署）。

**解决**：
```bash
# 本地运行：确认 .env 存在且内容正确
ls -la .env
cat .env   # 应显示: SECRET_KEY=一串很长的随机字符
```

Docker 部署则检查 `docker-compose.yml` 中是否设置了 `SECRET_KEY`。

### ❌ `ModuleNotFoundError: No module named 'xxx'`

**原因**：依赖未安装或虚拟环境未激活（仅本地运行会遇到）。

**解决**：确认虚拟环境已激活（命令行前应有 `(.venv)` 标记），重新 `pip install -r requirements.txt`。

Docker 部署不会遇到此问题（镜像构建时已装好依赖）；若遇到多为构建缓存问题，用 `docker compose build --no-cache` 重试。

### ❌ `Address already in use`（端口被占用）

**完整报错**：
```
OSError: [Errno 98] Address already in use
# 或 Windows: [WinError 10048]
```

**原因**：端口 3210 已被其他程序占用。

**解决**：
```bash
# 方案1：换个端口（本地运行时）
PORT=8080 python main.py

# 方案2：查杀占用端口的进程
# Linux
lsof -i :3210
kill -9 <PID>
# Windows
netstat -ano | findstr :3210
taskkill /PID <PID> /F

# Docker：宿主机端口被占时，改 docker-compose.yml
ports:
  - "8080:3210"   # 宿主机 8080 → 容器 3210
```

### ❌ Docker 容器启动后立即退出

**原因**：通常是 `SECRET_KEY` 未正确设置，或镜像未构建成功。

**解决**：
```bash
# 查看容器日志，定位具体原因
docker compose logs aichat

# 确认 docker-compose.yml 中的 SECRET_KEY 不是占位符
# 构建报错时，加上 --no-cache 重新构建
docker compose build --no-cache
```

### ❌ `sqlite3.OperationalError: unable to open database file`

**原因**：SQLite 所在目录没有写入权限。

**解决**：
```bash
# 本地运行：确认当前用户对项目目录有写权限
chmod 755 /你的项目路径/aichat

# Docker：确认 data 目录存在且可写（Linux 下目录权限通常需为容器用户可写）
mkdir -p data && chmod 777 data
```

### ❌ Docker 镜像构建失败（网络/拉取问题）

```bash
# 换用国内镜像加速后重试，例如：
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{ "registry-mirrors": ["https://docker.m.daocloud.io"] }
EOF
sudo systemctl restart docker
docker compose build --no-cache
```

## 运行时错误

### ❌ 聊天时返回 `检查API KEY的格式是否正确或已过期`

**原因**：未在设置页面填写对应提供商的 API Key，或 Key 已过期/被禁用。

**解决**：
1. 打开 `http://localhost:3210/settings`
2. 在下拉框选择你要用的提供商
3. 填入正确的 API Key，点击保存
4. 回到聊天页重试

### ❌ 登录后很快就提示"登录已过期"

**原因**，可能是以下几种：
- 其他设备进行了**问答操作**，本设备被自动踢下线（会话管理策略）
- 修改/重置了密码，旧登录凭证已全部失效
- 服务器重启导致内存中的 Token 黑名单丢失

**解决**：
- 重新登录即可
- 如果换了 `SECRET_KEY`，所有用户需要重新登录
- Token 有效期默认 7 天

### ❌ 注册时验证码一直提示错误

**原因**：验证码的 HMAC 签名依赖 `SECRET_KEY`。如果启动后改了 `SECRET_KEY`，之前的验证码就会失效。

**解决**：
- 刷新页面重新获取验证码
- 确保启动后没有再修改 `.env` / `docker-compose.yml`

### ❌ 搜索结果不对或搜不到

**原因**：搜索只匹配聊天消息的**内容**，不匹配标题。

**解决**：
- 用聊天中出现过的关键词搜索
- 搜索不支持模糊拼音，需要精确中文字符匹配

### ❌ 手机端布局错乱

**原因**：CSS 缓存。

**解决**：
- 强制刷新浏览器（Ctrl+Shift+R 或 Cmd+Shift+R）
- 清除浏览器缓存
- 确认没有自定义 CSS 覆盖

## 自定义修改指南

### 添加新的 AI 提供商

编辑 `main.py`，在 `PROVIDERS` 字典中添加：

```python
"openai": {
    "name": "OpenAI",
    "base_url": "https://api.openai.com/v1",
    "models": ["gpt-4o", "gpt-4o-mini"],
    "default_model": "gpt-4o-mini",
},
```

前端会自动加载新提供商，无需改 HTML。

> ⚠️ 要求提供商的 API 兼容 OpenAI 的 `/chat/completions` 格式。不同提供商的深度思考参数可能不同，需要在 `stream_response()` 函数中适配。

### 修改端口

三种方式，任选其一：

```bash
# 方式1：环境变量（本地运行）
PORT=8080 python main.py

# 方式2：写在 .env 文件中
echo "PORT=8080" >> .env

# 方式3：Docker 中修改 docker-compose.yml
ports:
  - "8080:3210"
```

### 修改 Token 有效期

编辑 `main.py` 第 86 行：
```python
JWT_EXPIRE_SECONDS = 7 * 24 * 3600   # 7天，改成你需要的秒数
```

### 修改最大同时登录设备数

编辑 `main.py` 第 87 行：
```python
MAX_SESSIONS = 5   # 默认5个设备；任一设备问答后，其他设备会被踢下线
```

### 添加密码哈希（推荐）

当前密码是明文存储的。如果要加固，安装 `passlib`：

```bash
pip install passlib[bcrypt]
```

然后在 `main.py` 中修改注册和登录逻辑：
```python
from passlib.hash import bcrypt

# 注册时：存哈希
hashed = bcrypt.hash(password)

# 登录时：验证哈希
bcrypt.verify(password, row["password"])
```

## 更新与维护

### 更新代码

```bash
git pull origin main
# 依赖有变动时用 --no-cache 强制重建，确保装上新的依赖版本
docker compose down
docker compose build --no-cache
docker compose up -d
```

> 版本升级后首次启动会自动给数据库补充新列（`ALTER TABLE`），旧数据保留，无需手动操作。

### 备份数据

```bash
# 数据库（含用户、Key、聊天记录）在宿主机的 ./data 目录
docker compose down
cp -r data "data.bak.$(date +%Y%m%d%H%M%S)"
docker compose up -d
```

> 彻底删除（含数据）才使用 `docker compose down -v`，请慎用。

### 清理旧数据

本项目目前没有内置的数据清理功能。如需手动清理：

```bash
# 进入 SQLite
sqlite3 data.db

# 删除 N 天前的消息（保留最近 90 天）
DELETE FROM messages WHERE created_at < unixepoch('now', '-90 days');

# 清理无消息的空对话
DELETE FROM chats WHERE id NOT IN (SELECT DISTINCT chat_id FROM messages);

# 压缩数据库
PRAGMA optimize;
VACUUM;
.quit
```

## 部署检查清单

- [ ] 服务器已安装 Docker，`docker compose version` 有输出
- [ ] `docker-compose.yml` 中 `SECRET_KEY` 已改为随机字符串（非占位符）
- [ ] `docker compose up -d --build` 构建成功、容器状态为 `Up`
- [ ] `docker compose logs aichat` 显示 `Uvicorn running on ...`
- [ ] 浏览器能打开 `http://服务器公网IP:3210`（本机则用 localhost）
- [ ] 云安全组 + 服务器防火墙已放行 3210/TCP
- [ ] 能正常注册账号（需填写 QQ）
- [ ] 在设置页面填入了至少一个提供商的 API Key
- [ ] 能正常发送消息并收到 AI 回复
- [ ] 能正常绑定/修改 QQ，忘记密码可重置
- [ ] 已完成 `data/` 目录的定期备份

## 安全声明

本项目是一个**个人学习用途**的实验台，已内置以下防护：

- **访问限流** — 登录/注册/发送等接口按 IP/用户限流，超出返回 429
- **CSRF 同源校验** — 写请求校验 Origin/Referer 与 Host 同源
- **出站 TLS 校验** — 调用 AI 供应商 API 时校验服务器证书
- **改密吊销会话** — 修改/重置密码后，全部登录凭证失效，需重新登录
- **会话管理** — 问答操作后，同账号其他设备自动下线

仍存在的**设计取舍**（未加密）：

1. **密码明文存储** — 用户密码未经过 bcrypt/scrypt 哈希，直接以明文存入 SQLite
2. **API Key 明文存储** — 各提供商的 API Key 以明文存入数据库
3. **内存 Token 黑名单** — JWT 注销机制使用内存存储，重启后失效

这些设计是为了保持代码简洁、易于理解和修改。**如果用于生产环境，请自行添加密码哈希和加密存储。** 建议不要将本项目直接暴露到公网。

## License

MIT License — 详见 [LICENSE](LICENSE)
