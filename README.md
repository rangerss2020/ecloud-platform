<p align="center">
  <img src="static/icons/default.svg" width="80" alt="ECloud Logo"/>
</p>

<h1 align="center">ECloud API Platform</h1>

<p align="center">
  <strong>开源大模型 API 中转与管理平台</strong><br>
  Open-source LLM API Relay & Management Platform
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="Python"></a>
  <a href="https://www.djangoproject.com/"><img src="https://img.shields.io/badge/django-3.2-green" alt="Django"></a>
  <a href="https://github.com/rangerss2020/ecloud-platform"><img src="https://img.shields.io/github/stars/rangerss2020/ecloud-platform?style=social" alt="Stars"></a>
</p>

---

## 📖 简介

ECloud 是一个基于 Django 构建的大模型 API 中转平台，提供用户管理、API Key 分发、多模型接入、计费充值、代理分佣、套餐购买等完整功能。

### 核心特性

- 🚀 **统一 API 入口** — 一个 Key 调用 21+ 大模型（DeepSeek / GLM / Qwen / Kimi / Llama 等）
- 💰 **灵活计费** — 按次 / 按量（千tokens / 百万tokens）计费，自定义定价
- 🔑 **API Key 管理** — 用户自主申请，Bearer Token 调用
- 📦 **套餐系统** — 购买套餐享调用次数/Token额度，到期自动过期
- 👥 **代理体系** — 多级代理、佣金分佣、下级会员管理
- 🎁 **推广邀请** — 邀请链接 + 二维码 + 注册奖励
- 🛡️ **敏感词过滤** — 输入输出双向过滤，三级处理策略
- 📊 **统计仪表盘** — Chart.js 图表，实时消费/充值统计
- 🌐 **开放 API** — 用户通过 API Key 直接 HTTP 调用
- 🎨 **暗黑科幻 UI** — 全自定义暗色主题

---

## 🏗 架构

```
用户代码 ──Bearer Token──→  本平台  ──转发──→  上游模型 API
                       自动计费+日志+过滤
```

- 前端：Bootstrap 5 + Chart.js + 原生 JS
- 后端：Django 3.2（Python）
- 数据库：MySQL 5.7+
- 认证：Bearer Token / HMAC 签名

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+
- pip

### 安装

```bash
# 克隆仓库
git clone https://github.com/rangerss2020/ecloud-platform.git
cd ecloud-platform

# 安装依赖
pip install -r requirements.txt

# 创建数据库
mysql -uroot -p -e "CREATE DATABASE ecloud_platform DEFAULT CHARSET utf8mb4;"

# 编辑 ecloud_platform/settings.py 中的数据库密码
# DATABASES = { 'default': { 'PASSWORD': '你的密码', ... } }

# 初始化
python manage.py migrate
python manage.py initdata

# 启动
python manage.py runserver 0.0.0.0:8000
```

访问 `http://127.0.0.1:8000/`

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 代理 | agent01 | agent123 |
| 会员 | member01 | member123 |

---

## 📡 API 调用

### Bearer Token 方式（推荐）

```python
import requests

resp = requests.post('http://127.0.0.1:8000/api/v1/deepseek-v3/',
    headers={'Authorization': f'Bearer {API_KEY}'},
    json={
        'model': 'deepseek-v3',
        'messages': [{'role': 'user', 'content': '你好'}]
    }
)
print(resp.json())
```

### 可用模型

| 系列 | 模型 |
|------|------|
| DeepSeek | V4-Pro, V4-Flash, V3.2, V3.1, V3, R1, 7B |
| GLM | 4.6, 5 |
| Qwen | Qwen3-235B, Qwen3-32B, Qwen-VL |
| 九天 | 乾元, 坤舆 |
| Kimi | K2.6 |
| Llama | 3.3, 3.2, 3.1 |
| 其他 | 混元(腾讯), 文心一言(百度), Embedding |

---

## 📁 项目结构

```
seedance/
├── ecloud_platform/      # Django 配置
├── users/                # 用户系统
├── apimodels/            # API模型管理
├── billing/              # 计费充值套餐
├── agent/                # 代理管理
├── apigateway/           # API网关
├── static/               # 静态资源
├── templates/            # 前端模板
├── requirements.txt      # 依赖
├── LICENSE               # Apache 2.0
└── README.md
```

---

## ⚙️ 配置

### 上游 API 连接

在管理后台配置渠道（Channel）的认证信息：
- Bearer Token 模式：填入上游 `API Key`
- AK/SK 签名模式：填入 `AccessKey` / `SecretKey`

### 生产部署

```bash
# Gunicorn (Linux)
gunicorn ecloud_platform.wsgi:application -w 4 -b 0.0.0.0:8000

# Waitress (Windows)
waitress-serve --port=8000 ecloud_platform.wsgi:application
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 开源协议

本项目基于 [Apache License 2.0](LICENSE) 开源。

Copyright © 2024 [rangerss2020](https://github.com/rangerss2020)

---

## ⚠️ 免责声明

本项目仅供学习和研究使用。使用者应遵守相关法律法规，不得用于非法用途。项目作者不对使用本软件产生的任何后果负责。

---

## 🌟 Star History

如果你觉得这个项目有用，请给一个 ⭐ Star！
