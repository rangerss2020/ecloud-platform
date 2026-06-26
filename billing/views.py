from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.core.paginator import Paginator
from .models import RechargeOrder, Transaction, SystemConfig, RedeemCode, Package, UserPackage
from .payment import get_gateway
import uuid
import json
from users.models import User


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin', login_url='user_login')(view)


@login_required
def billing_index(request):
    page1 = Paginator(Transaction.objects.filter(user=request.user).order_by('-created_at'), 10)
    transactions = page1.get_page(request.GET.get('page'))
    page2 = Paginator(RechargeOrder.objects.filter(user=request.user).order_by('-created_at'), 10)
    recharge_orders = page2.get_page(request.GET.get('page2'))
    packages = Package.objects.filter(status='enabled').order_by('sort_order')
    my_packages = UserPackage.objects.filter(user=request.user).select_related('package').order_by('-created_at')[:5]
    return render(request, 'billing/index.html', {
        'transactions': transactions, 'page_obj': transactions,
        'recharge_orders': recharge_orders, 'page_obj2': recharge_orders,
        'packages': packages, 'my_packages': my_packages,
    })


@login_required
def recharge(request):
    pay_methods_enabled = {
        'alipay': SystemConfig.get('alipay_enabled', '1') == '1',
        'wechat': SystemConfig.get('wechat_enabled', '1') == '1',
    }

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except (ValueError, Exception):
            messages.error(request, '请输入有效金额')
            return render(request, 'billing/recharge.html', {
        'pay_methods_enabled': pay_methods_enabled,
        'quick_amounts': parse_quick_amounts(),
    })

        pay_method = request.POST.get('pay_method', 'alipay')
        if pay_method not in ('alipay', 'wechat'):
            pay_method = 'alipay'

        if amount <= 0:
            messages.error(request, '充值金额必须大于0')
        elif amount < 10:
            messages.error(request, '最低充值10元')
        else:
            discount_rate = calc_discount(amount)
            pay_amount = amount * (100 - discount_rate) / 100 if discount_rate > 0 else amount
            order_no = 'RECH' + timezone.now().strftime('%Y%m%d%H%M%S') + uuid.uuid4().hex[:6].upper()
            pay_method_name = dict(RechargeOrder.PAY_METHODS).get(pay_method)
            remark = f'{pay_method_name}在线充值'
            if discount_rate > 0:
                remark = f'{pay_method_name}充值{amount}元(折后{pay_amount}元)'
            order = RechargeOrder.objects.create(
                order_no=order_no,
                user=request.user,
                amount=amount,
                pay_method=pay_method,
                status='pending',
                remark=remark,
            )
            order._pay_amount = pay_amount

            gateway = get_gateway(pay_method)
            gate_order = order
            if pay_amount != amount:
                gate_order = RechargeOrder(order_no=order.order_no, user=order.user, amount=pay_amount, pay_method=order.pay_method)
            pay_result, error = gateway.create_order(gate_order)

            if pay_result:
                return render(request, 'billing/pay.html', {
                    'order': order,
                    'qr_code': pay_result.get('qr_code', ''),
                    'pay_method': pay_method,
                    'pay_method_name': dict(RechargeOrder.PAY_METHODS).get(pay_method),
                    'amount': amount,
                    'pay_amount': pay_amount,
                    'discount_rate': discount_rate,
                })
            else:
                messages.error(request, f'支付下单失败: {error}')
                return render(request, 'billing/recharge.html', {
        'pay_methods_enabled': pay_methods_enabled,
        'quick_amounts': parse_quick_amounts(),
    })

    return render(request, 'billing/recharge.html', {
        'pay_methods_enabled': pay_methods_enabled,
        'quick_amounts': parse_quick_amounts(),
    })


@login_required
def check_order_status(request, order_no):
    try:
        order = RechargeOrder.objects.get(order_no=order_no, user=request.user)
        return JsonResponse({'status': order.status, 'order_no': order_no})
    except RechargeOrder.DoesNotExist:
        return JsonResponse({'status': 'not_found'}, status=404)


@csrf_exempt
def pay_callback(request, provider):
    if provider not in ('alipay', 'wechat'):
        return HttpResponse('FAIL')

    gateway = get_gateway(provider)
    if request.method == 'POST':
        if provider == 'wechat':
            data = _parse_xml(request.body.decode('utf-8'))
        else:
            data = dict(request.POST.items())

        if not gateway.verify_callback(data):
            return HttpResponse('FAIL' if provider == 'alipay' else '<xml><return_code>FAIL</return_code></xml>')

        out_trade_no = data.get('out_trade_no', '')
        trade_status = data.get('trade_status', data.get('result_code', 'SUCCESS'))

        try:
            order = RechargeOrder.objects.select_for_update().get(order_no=out_trade_no)
        except RechargeOrder.DoesNotExist:
            return HttpResponse('FAIL' if provider == 'alipay' else '<xml><return_code>FAIL</return_code></xml>')

        if trade_status in ('TRADE_SUCCESS', 'SUCCESS') and order.status == 'pending':
            with transaction.atomic():
                order = RechargeOrder.objects.select_for_update().get(order_no=out_trade_no)
                if order.status != 'pending':
                    return HttpResponse('SUCCESS' if provider == 'alipay' else '<xml><return_code>SUCCESS</return_code></xml>')

                user = order.user
                user = User.objects.select_for_update().get(pk=user.pk)
                user.balance = F('balance') + order.amount
                user.save(update_fields=['balance'])
                user.refresh_from_db()

                Transaction.objects.create(
                    user=user, type='recharge', amount=order.amount,
                    balance_after=user.balance,
                    description=f'{dict(RechargeOrder.PAY_METHODS).get(order.pay_method)}充值 {order.amount} 元',
                    related_order=order.order_no,
                )

                bonus = calc_bonus(order.amount)
                if bonus > 0:
                    user.balance = F('balance') + bonus
                    user.save(update_fields=['balance'])
                    user.refresh_from_db()
                    Transaction.objects.create(
                        user=user, type='recharge', amount=bonus,
                        balance_after=user.balance,
                        description=f'充值赠送 {bonus} 元',
                        related_order=order.order_no,
                    )

                order.status = 'completed'
                order.save(update_fields=['status', 'updated_at'])

        return HttpResponse('SUCCESS' if provider == 'alipay' else '<xml><return_code>SUCCESS</return_code></xml>')

    return HttpResponse('FAIL')


def _parse_xml(xml_str):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_str)
    return {child.tag: child.text for child in root}


def calc_bonus(amount):
    config = SystemConfig.get('quick_amounts', '')
    for line in config.strip().split('\n'):
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 2 and Decimal(parts[0]) == amount:
            return Decimal(parts[1])
    return Decimal('0')


def calc_discount(amount):
    config = SystemConfig.get('quick_amounts', '')
    for line in config.strip().split('\n'):
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3 and Decimal(parts[0]) == amount:
            try:
                return int(parts[2])
            except ValueError:
                return 0
    return 0


def parse_quick_amounts():
    config = SystemConfig.get('quick_amounts', '')
    items = []
    for line in config.strip().split('\n'):
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 2:
            items.append({
                'amount': parts[0],
                'bonus': parts[1],
                'discount': parts[2] if len(parts) > 2 else '0',
                'label': parts[3] if len(parts) > 3 else f'{parts[0]}元',
            })
    return items


@login_required
def transaction_list(request):
    paginator = Paginator(Transaction.objects.filter(user=request.user).order_by('-created_at'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'billing/transactions.html', {'transactions': page_obj, 'page_obj': page_obj})


@admin_required
def system_settings(request):
    if request.method == 'POST':
        fields = ['site_name', 'allow_register', 'email_verify', 'invite_reward', 'quick_amounts',
                  'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_from']
        for f in fields:
            SystemConfig.set(f, request.POST.get(f, ''))
        SystemConfig.set('allow_register', request.POST.get('_allow_register', '0'))
        messages.success(request, '系统设置已保存')

    ctx = {}
    defaults = {'site_name': 'ECloud API平台',         'allow_register': '1', 'email_verify': '0', 'invite_reward': '0',
                'quick_amounts': '10,0,0,10元\n50,5,0,50元\n100,15,90,推荐\n200,40,85,热门\n500,120,80,超值',
                'smtp_host': '', 'smtp_port': '587', 'smtp_user': '',
                'smtp_password': '', 'smtp_from': ''}
    for key, default in defaults.items():
        ctx[key] = SystemConfig.get(key, default)
    return render(request, 'billing/system.html', ctx)


@admin_required
def payment_settings(request):
    if request.method == 'POST':
        fields = ['alipay_enabled', 'alipay_app_id', 'alipay_private_key',
                  'alipay_public_key', 'alipay_notify_url',
                  'wechat_enabled', 'wechat_app_id', 'wechat_mch_id',
                  'wechat_api_key', 'wechat_notify_url', 'pay_mock_mode']
        for f in fields:
            SystemConfig.set(f, request.POST.get(f, '0' if 'enabled' in f or 'mock' in f else ''))
        messages.success(request, '支付设置已保存')
        return redirect('payment_settings')

    ctx = {}
    defaults = [
        ('alipay_enabled', '1'), ('alipay_app_id', ''), ('alipay_private_key', ''),
        ('alipay_public_key', ''), ('alipay_notify_url', ''),
        ('wechat_enabled', '1'), ('wechat_app_id', ''), ('wechat_mch_id', ''),
        ('wechat_api_key', ''), ('wechat_notify_url', ''), ('pay_mock_mode', '1'),
    ]
    for key, default in defaults:
        ctx[key] = SystemConfig.get(key, default)
    callback_base = request.build_absolute_uri('/')[:-1]
    ctx['alipay_callback_url'] = f'{callback_base}/billing/callback/alipay/'
    ctx['wechat_callback_url'] = f'{callback_base}/billing/callback/wechat/'
    return render(request, 'billing/settings.html', ctx)


@login_required
def redeem_code(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        if not code:
            messages.error(request, '请输入兑换码')
            return redirect('billing_index')

        with transaction.atomic():
            rc = RedeemCode.objects.select_for_update().filter(code=code, is_used=False).first()
            if not rc:
                messages.error(request, '兑换码无效或已被使用')
                return redirect('billing_index')

            user = User.objects.select_for_update().get(pk=request.user.pk)
            user.balance = F('balance') + rc.amount
            user.save(update_fields=['balance'])
            user.refresh_from_db()

            rc.is_used = True
            rc.used_by = request.user
            rc.used_at = timezone.now()
            rc.save()

            Transaction.objects.create(
                user=request.user, type='adjust', amount=rc.amount,
                balance_after=user.balance,
                description=f'兑换码兑换 {rc.amount} 元',
                related_order=rc.code,
            )

        messages.success(request, f'兑换成功！到账 {rc.amount} 元')
        return redirect('billing_index')

    return redirect('billing_index')


@admin_required
def manage_redeem_codes(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'generate':
            amount = request.POST.get('amount', '0')
            count = int(request.POST.get('count', '1'))
            batch = 'BTH' + timezone.now().strftime('%Y%m%d%H%M%S')
            codes = []
            for _ in range(count):
                c = uuid.uuid4().hex[:10].upper()
                RedeemCode.objects.create(code=c, amount=amount, batch_no=batch)
                codes.append(c)
            messages.success(request, f'已生成 {count} 个兑换码，批次 {batch}')
            return render(request, 'billing/redeem_admin.html', {
                'codes': RedeemCode.objects.all().order_by('-created_at')[:50],
                'new_codes': codes, 'new_batch': batch,
            })
        elif action == 'delete':
            RedeemCode.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, '已删除')
        elif action == 'delete_batch':
            RedeemCode.objects.filter(batch_no=request.POST.get('batch'), is_used=False).delete()
            messages.success(request, '已删除未使用的批次码')

    paginator = Paginator(RedeemCode.objects.all().order_by('is_used', '-created_at'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'billing/redeem_admin.html', {'codes': page_obj, 'page_obj': page_obj})


@admin_required
def manage_packages(request):
    from apimodels.models import ApiModel
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add':
            p = Package.objects.create(
                name=request.POST.get('name', ''),
                price=request.POST.get('price', 0),
                description=request.POST.get('description', ''),
                call_limit=int(request.POST.get('call_limit', 0) or 0),
                token_limit=int(request.POST.get('token_limit', 0) or 0),
                duration_type=request.POST.get('duration_type', 'month'),
                duration_value=int(request.POST.get('duration_value', 1) or 1),
                model_restrict=request.POST.get('model_restrict') == '1',
                model_ids=[int(x) for x in request.POST.getlist('model_ids') if x],
                status=request.POST.get('status', 'enabled'),
            )
            messages.success(request, '套餐已添加')
        elif action == 'edit':
            p = get_object_or_404(Package, id=request.POST.get('id'))
            p.name = request.POST.get('name', p.name)
            p.price = request.POST.get('price', p.price)
            p.description = request.POST.get('description', p.description)
            p.call_limit = int(request.POST.get('call_limit', p.call_limit) or 0)
            p.token_limit = int(request.POST.get('token_limit', p.token_limit) or 0)
            p.duration_type = request.POST.get('duration_type', p.duration_type)
            p.duration_value = int(request.POST.get('duration_value', p.duration_value) or 1)
            p.model_restrict = request.POST.get('model_restrict') == '1'
            p.model_ids = [int(x) for x in request.POST.getlist('model_ids') if x]
            p.status = request.POST.get('status', p.status)
            p.save()
            messages.success(request, '套餐已更新')
        elif action == 'delete':
            Package.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, '套餐已删除')
        return redirect('manage_packages')

    packages = Package.objects.all().order_by('sort_order')
    all_models = ApiModel.objects.filter(status='enabled').order_by('channel__sort_order', 'sort_order')
    return render(request, 'billing/package_admin.html', {
        'packages': packages, 'all_models': all_models,
    })


@login_required
def buy_package(request, package_id):
    p = get_object_or_404(Package, id=package_id, status='enabled')
    if request.user.balance < p.price:
        messages.error(request, '余额不足')
        return redirect('billing_index')

    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if user.balance < p.price:
            messages.error(request, '余额不足')
            return redirect('billing_index')

        user.balance = F('balance') - p.price
        user.save(update_fields=['balance'])
        user.refresh_from_db()

        end_date = None
        if p.duration_type == 'forever':
            end_date = None
        elif p.duration_type in ('month', 'year'):
            end_date = timezone.now() + relativedelta(**{p.duration_type + 's': p.duration_value})
        else:
            end_date = timezone.now() + timedelta(days=p.duration_value)

        UserPackage.objects.filter(user=user, status='active').update(status='expired')

        up = UserPackage.objects.create(
            user=user, package=p, end_date=end_date,
        )

        Transaction.objects.create(
            user=user, type='consume', amount=-p.price,
            balance_after=user.balance,
            description=f'购买套餐: {p.name}',
        )

    messages.success(request, f'成功购买套餐【{p.name}】')
    return redirect('billing_index')


@admin_required
def admin_transactions(request):
    search = request.GET.get('q', '').strip()
    qs = Transaction.objects.select_related('user').exclude(description__startswith='套餐')
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(user__username__icontains=search) | Q(description__icontains=search) | Q(related_order__icontains=search))
    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'billing/admin_transactions.html', {'transactions': page_obj, 'page_obj': page_obj, 'search': search})
