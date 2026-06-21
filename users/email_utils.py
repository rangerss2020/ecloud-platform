import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from billing.models import SystemConfig


def send_verify_code(email, code):
    host = SystemConfig.get('smtp_host', '')
    port = int(SystemConfig.get('smtp_port', '587') or '587')
    user = SystemConfig.get('smtp_user', '')
    password = SystemConfig.get('smtp_password', '')
    sender_name = SystemConfig.get('smtp_from', SystemConfig.get('site_name', 'ECloud'))
    site_name = SystemConfig.get('site_name', 'ECloud API平台')

    if not host or not user or not password:
        raise RuntimeError('邮件服务未配置')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'【{site_name}】注册验证码'
    msg['From'] = f'{sender_name} <{user}>'
    msg['To'] = email

    html = f'''<div style="max-width:500px;margin:20px auto;padding:30px;background:#111827;border:1px solid rgba(0,229,255,0.2);border-radius:12px;text-align:center">
        <h2 style="color:#00e5ff;font-family:monospace">{site_name}</h2>
        <p style="color:#8892a4">您的注册验证码：</p>
        <div style="font-size:32px;font-weight:bold;letter-spacing:8px;color:#fff;padding:15px;background:rgba(0,229,255,0.08);border-radius:8px;margin:20px 0">{code}</div>
        <p style="color:#546078;font-size:12px">验证码5分钟内有效</p>
    </div>'''
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def generate_code():
    return ''.join(str(random.randint(0, 9)) for _ in range(6))


def is_email_verify_enabled():
    return SystemConfig.get('email_verify', '0') == '1'
