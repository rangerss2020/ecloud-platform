from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Q, Q
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from users.models import User
from billing.models import SystemConfig
from .models import AgentProfile, CommissionRecord, Withdrawal
import uuid
from decimal import Decimal

def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin', login_url='user_login')(view)
import uuid


@login_required
def agent_dashboard(request):
    if request.user.role not in ('agent', 'admin'):
        messages.error(request, '无权访问')
        return redirect('dashboard')

    ctx = {}
    if request.user.role == 'agent':
        profile = get_object_or_404(AgentProfile, user=request.user)
        ctx['profile'] = profile
        ctx['sub_count'] = request.user.sub_members.count()
        search = request.GET.get('q', '').strip()
        sub_qs = request.user.sub_members.all()
        if search:
            sub_qs = sub_qs.filter(username__icontains=search)
        ctx['sub_members'] = sub_qs.order_by('-created_at')[:10]
        ctx['sub_search'] = search
        commissions = CommissionRecord.objects.filter(agent=profile)
        ctx['commissions'] = commissions.order_by('-created_at')[:20]
        ctx['total_commission'] = commissions.filter(status='settled').aggregate(total=Sum('commission_amount'))['total'] or 0
        ctx['pending_commission'] = commissions.filter(status='pending').aggregate(total=Sum('commission_amount'))['total'] or 0
    else:
        ctx['total_agents'] = AgentProfile.objects.count()
        ctx['total_members'] = User.objects.filter(role='member').count()
        ctx['total_commission'] = CommissionRecord.objects.filter(status='settled').aggregate(total=Sum('commission_amount'))['total'] or 0
        ctx['admin_members'] = User.objects.filter(role='member').select_related('parent_agent').order_by('-created_at')[:10]
        ctx['all_agents'] = AgentProfile.objects.select_related('user').order_by('-created_at')[:10]

    return render(request, 'agent/dashboard.html', ctx)


@login_required
def member_list(request):
    if request.user.role not in ('agent', 'admin'):
        messages.error(request, '无权访问')
        return redirect('dashboard')

    if request.user.role == 'admin':
        qs = User.objects.filter(role='member').select_related('parent_agent')
    else:
        qs = request.user.sub_members.select_related('parent_agent').all()

    search = request.GET.get('q', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))

    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    from apigateway.models import ApiRequestRecord
    for m in page_obj:
        m.call_count = ApiRequestRecord.objects.filter(user=m).count()
        m.total_consume = ApiRequestRecord.objects.filter(user=m).aggregate(
            total=Sum('cost')
        )['total'] or 0
        m.total_tokens = 0
        try:
            recs = ApiRequestRecord.objects.filter(user=m, prompt_tokens__gt=0).values_list('prompt_tokens', 'completion_tokens')
            m.total_tokens = sum(r[0]+r[1] for r in recs if r[0] or r[1])
        except Exception:
            pass

    return render(request, 'agent/members.html', {
        'members': page_obj, 'page_obj': page_obj, 'search': search,
    })


@login_required
def promotion(request):
    if request.user.role not in ('agent', 'member'):
        messages.error(request, '仅代理和会员可访问推广页')
        return redirect('dashboard')

    if request.user.role == 'agent':
        profile = get_object_or_404(AgentProfile, user=request.user)
    else:
        profile = None

    if not request.user.referral_code:
        request.user.referral_code = 'REF' + uuid.uuid4().hex[:8].upper()
        request.user.save(update_fields=['referral_code'])

    base = request.build_absolute_uri('/')[:-1]
    ref_link = f'{base}/users/register/?ref={request.user.referral_code}'
    ref_count = request.user.sub_members.count()
    qr_url = f'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={ref_link}'
    invite_reward = SystemConfig.get('invite_reward', '0')
    search = request.GET.get('q', '').strip()
    invited_qs = request.user.sub_members.all()
    if search:
        invited_qs = invited_qs.filter(username__icontains=search)
    invited_members = invited_qs.order_by('-created_at')[:20]

    from apigateway.models import ApiRequestRecord
    for m in invited_members:
        m.call_count = ApiRequestRecord.objects.filter(user=m).count()
        m.total_consume = ApiRequestRecord.objects.filter(user=m).aggregate(
            total=Sum('cost')
        )['total'] or 0
        m.total_tokens = 0
        try:
            recs = ApiRequestRecord.objects.filter(user=m, prompt_tokens__gt=0).values_list('prompt_tokens', 'completion_tokens')
            m.total_tokens = sum(r[0]+r[1] for r in recs if r[0] or r[1])
        except Exception:
            pass

    return render(request, 'agent/promotion.html', {
        'profile': profile,
        'ref_link': ref_link,
        'ref_code': request.user.referral_code,
        'ref_count': ref_count,
        'qr_url': qr_url,
        'invite_reward': invite_reward,
        'invited_members': invited_members,
        'search': search,
    })


@login_required
def admin_edit_user(request, user_id):
    if request.user.role != 'admin':
        messages.error(request, '无权访问')
        return redirect('dashboard')

    target = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        ap = AgentProfile.objects.filter(user=target).first()
        target.balance = request.POST.get('balance', target.balance)
        target.phone = request.POST.get('phone', target.phone)
        target.email = request.POST.get('email', target.email)
        target.is_active = request.POST.get('is_active', '1') == '1'
        new_role = request.POST.get('role', target.role)
        if new_role in ('admin', 'agent', 'member'):
            target.role = new_role
        target.save()
        if new_role == 'agent' and not AgentProfile.objects.filter(user=target).exists():
            AgentProfile.objects.create(user=target, level=1, commission_rate=10)

        if ap:
            ap.level = request.POST.get('agent_level', ap.level)
            ap.commission_rate = request.POST.get('commission_rate', ap.commission_rate)
            ap.save()

        messages.success(request, '用户信息已更新')
        return redirect('admin_edit_user', user_id=target.id)

    ap = AgentProfile.objects.filter(user=target).first()
    return render(request, 'agent/edit_user.html', {'target': target, 'agent_profile': ap})


@login_required
def withdrawal_apply(request):
    if request.user.role != 'agent':
        messages.error(request, '仅代理可发起提现')
        return redirect('dashboard')

    profile = get_object_or_404(AgentProfile, user=request.user)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except Exception:
            messages.error(request, '金额无效')
            return redirect('withdrawal_apply')

        if amount <= 0:
            messages.error(request, '金额必须大于0')
        elif amount < 10:
            messages.error(request, '最低提现10元')
        elif amount > profile.total_commission:
            messages.error(request, f'可提现佣金余额不足，当前: ¥{profile.total_commission}')
        else:
            Withdrawal.objects.create(
                agent=profile,
                amount=amount,
                remark=request.POST.get('remark', ''),
            )
            messages.success(request, '提现申请已提交，等待审核')
            return redirect('withdrawal_apply')

    pending_withdrawals = Withdrawal.objects.filter(agent__user=request.user).order_by('-created_at')
    paginator = Paginator(pending_withdrawals, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'agent/withdrawal.html', {
        'profile': profile,
        'withdrawals': page_obj,
        'page_obj': page_obj,
        'balance': profile.total_commission,
    })


@login_required
def withdrawal_review(request):
    if request.user.role != 'admin':
        messages.error(request, '无权访问')
        return redirect('dashboard')

    if request.method == 'POST':
        wid = request.POST.get('id')
        action = request.POST.get('action')
        w = get_object_or_404(Withdrawal, id=wid, status='pending')

        with transaction.atomic():
            w = Withdrawal.objects.select_for_update().get(id=wid, status='pending')
            if action == 'approve':
                agent_user = w.agent.user
                profile = w.agent
                profile = AgentProfile.objects.select_for_update().get(pk=profile.pk)
                if profile.total_commission < w.amount:
                    messages.error(request, '佣金余额不足，无法通过')
                    return redirect('withdrawal_review')

                profile.total_commission = F('total_commission') - w.amount
                profile.save(update_fields=['total_commission'])
                profile.refresh_from_db()

                w.status = 'approved'
                w.reviewer = request.user
                w.review_remark = request.POST.get('remark', '')
                w.reviewed_at = timezone.now()
                w.save()

                from billing.models import Transaction
                agent_user.refresh_from_db()
                Transaction.objects.create(
                    user=agent_user, type='consume', amount=-w.amount,
                    balance_after=agent_user.balance,
                    description=f'提现 {w.amount} 元',
                )
                messages.success(request, '提现已通过')
            elif action == 'reject':
                w.status = 'rejected'
                w.reviewer = request.user
                w.review_remark = request.POST.get('remark', '')
                w.reviewed_at = timezone.now()
                w.save()
                messages.success(request, '提现已拒绝')

        return redirect('withdrawal_review')

    search = request.GET.get('q', '').strip()
    qs = Withdrawal.objects.select_related('agent__user')
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(agent__user__username__icontains=search) | Q(remark__icontains=search))
    paginator = Paginator(qs.order_by('-created_at'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'agent/withdrawal_review.html', {
        'withdrawals': page_obj,
        'page_obj': page_obj,
        'search': search,
    })


@login_required
def create_user(request):
    import uuid as _uuid
    if request.user.role != 'admin':
        messages.error(request, '无权访问')
        return redirect('dashboard')

    role = request.GET.get('role', 'member')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        role_ = request.POST.get('role', 'member')
        parent_code = request.POST.get('parent_code', '').strip()

        if not username or not password:
            messages.error(request, '用户名和密码必填')
            return redirect(f'{request.path}?role={role_}')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'用户名 {username} 已存在')
            return redirect(f'{request.path}?role={role_}')

        user = User.objects.create_user(username=username, password=password)
        user.role = role_
        user.api_key = 'AK' + _uuid.uuid4().hex[:30].upper()
        if parent_code:
            parent = User.objects.filter(referral_code=parent_code, is_active=True).first()
            if parent:
                user.parent_agent = parent

        user.save()
        if role_ == 'agent':
            AgentProfile.objects.get_or_create(user=user, defaults={'level': 1, 'commission_rate': 10})

        messages.success(request, f'用户 {username} 创建成功')
        return redirect(f'{request.path}?role={role_}')

    return render(request, 'agent/create_user.html', {'role': role})
