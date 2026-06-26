from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F
from django.db import transaction as db_transaction
from decimal import Decimal
import time
from django.http import JsonResponse
from agent.models import AgentProfile
from .models import User
from .email_utils import send_verify_code, generate_code, is_email_verify_enabled


def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        messages.error(request, '用户名或密码错误')
    return render(request, 'users/login.html')


def user_register(request):
    from billing.models import SystemConfig
    verify_enabled = is_email_verify_enabled()
    if SystemConfig.get('allow_register', '1') == '0':
        messages.error(request, '平台已关闭注册')
        if verify_enabled:
            return render(request, 'users/register.html', {'verify_enabled': True})
        return render(request, 'users/register.html')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = 'member'
        ref_code = request.POST.get('ref', '').strip()

        if len(username) < 3:
            messages.error(request, '用户名至少3个字符')
        elif len(password) < 6:
            messages.error(request, '密码至少6位')
        elif password != password2:
            messages.error(request, '两次密码不一致')
        elif verify_enabled:
            code = request.POST.get('verify_code', '').strip()
            session_code = request.session.get('register_verify_code', '')
            if not code or code != session_code:
                messages.error(request, '验证码错误')
                return render(request, 'users/register.html', {'verify_enabled': True})
            if time.time() > request.session.get('register_verify_expire', 0):
                messages.error(request, '验证码已过期')
                return render(request, 'users/register.html', {'verify_enabled': True})
        elif User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
        else:
            parent = None
            if ref_code:
                try:
                    parent = User.objects.get(referral_code=ref_code, is_active=True)
                except User.DoesNotExist:
                    pass

            user = User.objects.create_user(
                username=username, password=password,
                email=email, phone=phone, role=role,
                parent_agent=parent
            )

            if parent and parent.role != 'agent':
                from billing.models import SystemConfig
                reward = Decimal(SystemConfig.get('invite_reward', '0'))
                if reward > 0:
                    from django.db import transaction as db_transaction
                    with db_transaction.atomic():
                        p = User.objects.select_for_update().get(pk=parent.pk)
                        p.balance = F('balance') + reward
                        p.save(update_fields=['balance'])
                        p.refresh_from_db()
                        from billing.models import Transaction
                        Transaction.objects.create(
                            user=p, type='adjust', amount=reward,
                            balance_after=p.balance,
                            description=f'邀请奖励({user.username})',
                        )

            if role == 'agent':
                AgentProfile.objects.create(user=user, level=1, commission_rate=10)
                messages.success(request, '代理账户注册成功，请联系管理员审核')
            else:
                messages.success(request, '注册成功，请登录')
            request.session.pop('register_verify_code', None)
            request.session.pop('register_verify_expire', None)
            return redirect('user_login')

    return render(request, 'users/register.html', {'verify_enabled': verify_enabled})


def send_register_code(request):
    email = request.POST.get('email', '').strip()
    if not email:
        return JsonResponse({'ok': False, 'error': '邮箱不能为空'})

    code = generate_code()
    request.session['register_verify_code'] = code
    request.session['register_verify_expire'] = time.time() + 300

    try:
        send_verify_code(email, code)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


def user_logout(request):
    logout(request)
    return redirect('user_login')


@login_required
def user_profile(request):
    if request.method == 'POST':
        user = request.user
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        password = request.POST.get('password', '')
        if password:
            if len(password) >= 6:
                user.set_password(password)
                user.save()
                login(request, user)
                messages.success(request, '密码已修改')
                return redirect('user_profile')
            else:
                messages.error(request, '密码至少6位')
                return render(request, 'users/profile.html')
        user.save()
        messages.success(request, '资料更新成功')

    return render(request, 'users/profile.html')


@login_required
def user_apikey(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'generate':
            ak, sk = request.user.generate_api_keys()
            messages.success(request, 'API Key 已生成，Secret 仅显示一次请妥善保管')
            return render(request, 'users/apikey.html', {'new_ak': ak, 'new_sk': sk})
        elif action == 'reset':
            ak, sk = request.user.generate_api_keys()
            messages.success(request, 'API Key 已重置')
            return render(request, 'users/apikey.html', {'new_ak': ak, 'new_sk': sk})

    return render(request, 'users/apikey.html')
