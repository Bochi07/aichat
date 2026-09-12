# AI角色扮演聊天平台

一个轻量级的 AI 聊天前端，支持**多模型提供商**，使用 FastAPI + SQLite 构建，手机端优先设计。

本文档前半部分为**项目介绍与功能展示**，后半部分为**部署、排错与维护**。

## 目录

**功能部分**
- [支持的 AI 提供商](#支持的-ai-提供商)
- [功能](#功能)
- [上下文优化](#上下文优化)
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
| **DeepSeek** | deepseek-v4-pro, deepseek-v4-flash，deepseek-v4.1-flash |
| **通义千问 (Qwen)** | qwen3.7-max, qwen-max, qwen-plus, qwen-flash |
| **文心 (Ernie)** | ernie-5.1, ernie-4.5-turbo, ernie-4.0-turbo, ernie-speed |
| **小米 MiLM** | mimo-v2.5-pro, mimo-v2.5 |

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
- 🚀 **1M 上下文深度优化** — 使用 tiktoken 精确计算 token，动态分配输出预留，最大化利用 1M 上下文窗口（详见[上下文优化](#上下文优化)）

> 📌 **忘记密码**依赖注册时绑定的 QQ 号。老用户升级后需先在「设置 → 绑定QQ」填写一次，才可使用忘记密码功能。

## 上下文优化

本项目针对 1M（1,000,000）token 的超长上下文窗口进行了深度优化，核心策略如下：

### 1. 精确 Token 计算
- 使用 **tiktoken**（cl100k_base 编码）精确计算 token 数，误差 < 1%
- 替代了原有的本地估算算法（误差 ±30%），大幅提升上下文利用率

### 2. 动态输出预留
- 根据历史回复长度动态计算输出预留空间（取 1.2 倍或基础值 1024 的较大者）
- 避免固定预留 2048 token 造成的浪费

### 3. 智能压缩策略
- **压缩阈值**：从 150 token 提升到 300 token，减少不必要的压缩
- **保留比例**：从 30-40% 提升到 50-60%，保留更多历史上下文
- **救援预算**：从 30% 提升到 40%，塞回更多被丢弃的消息

### 4. 三轮上下文拼装
1. **第一轮**：从最新消息往前，用真实 token 数拼装完整历史
2. **第二轮**：被丢弃的消息用压缩版塞回（最多占预算的 40%）
3. **第三轮**：如果还是太满，精简 system_prompt

### 5. 性能指标
- **上下文利用率**：从 50-80% 提升到 85-95%
- **安全余量**：从 500 token 降低到 200 token
- **压缩激进度**：从丢弃 60-70% 降低到丢弃 40-50%

### 6. 兼容性
- **数据库兼容**：无表结构变更，老用户升级无数据影响
- **前端兼容**：API 接口不变，前端操作完全不受影响
- **部署兼容**：仅需安装 tiktoken 依赖，Docker 构建自动处理

## 效果截图

<img width="2866" height="1610" alt="image" src="https://github.com/user-attachments/assets/4da0f69f-8237-44e3-9eb7-26cf21ecf5f0" />

## 技术栈

- **后端**: Python 3.10+ / FastAPI / aiosqlite / tiktoken
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
| `TRUSTED_PROXIES` | 否 | `127.0.0.1,::1` | 可信反向代理地址，逗号分隔。**仅当直连方在此列表中时才会采信 `X-Forwarded-For`**（用于获取真实客户端 IP 做限流与失败锁定）。若 nginx 与应用不在同一台机器，必须把 nginx 的 IP 加进来，否则所有访客会被当成同一来源、共用同一份限流额度 |

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

> ⚠️ 占位符等于把签名密钥公开，程序会**直接拒绝启动**（与未设置 `SECRET_KEY` 同样处理），必须改成随机字符串。改完之后之前的登录状态会全部失效，属正常现象。

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

### ❌ `SECRET_KEY 仍是公开的占位符，拒绝启动`

**完整报错**：
```
RuntimeError: !!! SECRET_KEY 仍是公开的占位符，拒绝启动 !!!
```

**原因**：`SECRET_KEY` 还是 `docker-compose.yml` / `Dockerfile` 里自带的默认值（如 `请改成随机字符串至少32位`、`change-me-to-random-string`）。这类值在开源仓库里人人可见，等于没有密钥，因此程序拒绝启动。

**解决**：按上一节的方法生成随机串并填入 `.env` 或 `docker-compose.yml`。

### ❌ `ModuleNotFoundError: No module named 'xxx'`

**原因**：依赖未安装或虚拟环境未激活（仅本地运行会遇到）。

**解决**：确认虚拟环境已激活（命令行前应有 `(.venv)` 标记），重新 `pip install -r requirements.txt`。

> 📌 **新增依赖**：v2.0+ 版本新增 `tiktoken` 依赖，用于精确计算 token 数。Docker 部署会自动安装；本地运行需重新执行 `pip install -r requirements.txt`。

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

### 密码存储（已内置，无需额外依赖）

密码使用 **scrypt**（带随机盐）哈希后存储；若运行环境的 OpenSSL 未提供 scrypt，会自动回退到
**pbkdf2-hmac-sha256**（60 万次迭代）。两者都是 Python 标准库，**不需要安装 passlib、bcrypt 等任何额外依赖**。

- 密码一律按 UTF-8 参与运算，**中文、日文、emoji、任意符号都可以作为密码**；
- 设置新密码时要求 8–128 个字符（调整 `main.py` 中的 `PASSWORD_MIN_LEN` 可改最小长度）；
- **旧版本遗留的明文密码不受影响**：仍可正常登录，并在该次登录成功后自动升级为哈希，用户无感；
- 登录失败锁定与找回密码同样适用（见下方"安全声明"）。

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
- [ ] （可选）本地运行时已安装 tiktoken 依赖：`pip install tiktoken`

## 安全声明

本项目是一个**个人学习用途**的实验台，已内置以下防护：

- **访问限流** — 登录/注册/发送等接口按 IP/用户限流，超出返回 429（仅采信可信代理带来的 `X-Forwarded-For`）
- **密码哈希存储** — scrypt + 随机盐（回退 pbkdf2），历史明文密码在登录成功时自动升级
- **登录失败锁定** — 同一账号连续失败 5 次锁定 15 分钟，计数落库、多进程有效
- **验证码答案不下发** — 令牌只含签名与过期时间，答案留在服务端且 5 分钟过期
- **CSRF 同源校验** — 写请求校验 Origin/Referer 与 Host 同源
- **出站 TLS 校验** — 调用 AI 供应商 API 时校验服务器证书
- **改密吊销会话** — 修改/重置密码后，全部登录凭证失效，需重新登录
- **会话管理** — 问答操作后，同账号其他设备自动下线

仍存在的**设计取舍**：

1. **API Key 明文存储** — 各提供商的 API Key 以明文存入数据库（设置页需要完整回显，便于核对）
2. **内存 Token 黑名单** — JWT 注销机制使用内存存储，重启后失效（但登出同时会删除数据库中的会话记录，因此仍然有效）
3. **找回密码凭据较弱** — 仅凭"用户名 + 绑定的 QQ 号"，建议不要将本项目直接暴露到公网

这些设计是为了保持代码简洁、易于理解和修改。**如果要用于生产环境，请自行补充 API Key 加密存储。** 建议不要将本项目直接暴露到公网。

## License

MIT License — 详见 [LICENSE](LICENSE)
