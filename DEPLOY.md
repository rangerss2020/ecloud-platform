# ECloud API 管理平台 - 部署指南

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.8+ |
| MySQL | 5.7+ |
| pip | 20+ |

## 一键部署

```bash
# 1. 克隆项目
cd seedance

# 2. 安装依赖
pip install -r requirements.txt

# 3. 创建数据库（需提前安装MySQL）
mysql -uroot -p -e "CREATE DATABASE ecloud_platform DEFAULT CHARSET utf8mb4;"

# 4. 修改数据库连接信息
# 编辑 ecloud_platform/settings.py 中的 DATABASES 配置

# 5. 初始化数据库和数据
python manage.py migrate
python manage.py initdata

# 6. 启动服务
python manage.py runserver 0.0.0.0:8000
```

## 配置说明

### 数据库配置 (ecloud_platform/settings.py)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ecloud_platform',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

### 默认测试账号
| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 代理 | agent01 | agent123 |
| 会员 | member01 | member123 |

### 生产环境启动
```bash
# 使用 gunicorn (Linux)
pip install gunicorn
gunicorn ecloud_platform.wsgi:application -w 4 -b 0.0.0.0:8000

# 或使用 waitress (Windows)
pip install waitress
waitress-serve --port=8000 ecloud_platform.wsgi:application
```

## 初始化数据说明

`python manage.py initdata` 自动创建：
- 3个测试用户
- 1个移动云MaaS渠道 (Bearer Token认证)
- 21个AI大模型
- 内置敏感词
- 默认充值快捷金额配置
- 用户API Key
