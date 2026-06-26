# ECloud API 平台 - 部署指南

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.8+ |
| MySQL | 5.7+ |

## 快速部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建数据库
mysql -uroot -p -e "CREATE DATABASE ecloud_platform DEFAULT CHARSET utf8mb4;"

# 3. 配置数据库密码
# 编辑 ecloud_platform/settings.py 中的 DATABASES.PASSWORD
# 或设置环境变量: export DB_PASSWORD=your_password

# 4. 初始化
python manage.py migrate
python manage.py initdata

# 5. 收集静态文件
python manage.py collectstatic --noinput

# 6. 启动（生产模式）
waitress-serve --port=8000 --threads=16 ecloud_platform.wsgi:application
```

## 线程数建议

`线程数 = CPU核心数 × 2`，I/O 密集型可适当调高。

## Docker 部署

```bash
cp .env.example .env
docker-compose up -d
```

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 代理 | agent01 | agent123 |
| 会员 | member01 | member123 |

## 技术栈

- **Web 服务器**: Waitress（多线程）+ WhiteNoise（静态文件）
- **后端**: Django 3.2
- **数据库**: MySQL 5.7
- **前端**: Bootstrap 5 + Chart.js（全本地化）

## 初始化数据

`python manage.py initdata` 自动创建：
- 3 个测试用户（含 API Key）
- 21 个 AI 大模型
- 4 个套餐（体验包/基础版/专业版/企业版）
- 内置敏感词
- 充值快捷金额 + 赠送配置
