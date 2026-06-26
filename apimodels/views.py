from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.http import HttpResponse, Http404
import os
import mimetypes
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from django.core.paginator import Paginator
from .models import ApiModel, Channel
from billing.models import Transaction
from agent.models import AgentProfile, CommissionRecord
from users.models import User
from decimal import Decimal
from apigateway.models import ApiRequestRecord
import os
import markdown
import markdown


@login_required
def dashboard(request):
    user = request.user
    all_models = ApiModel.objects.filter(status='enabled').select_related('channel').order_by('channel__sort_order', 'sort_order')
    p1 = Paginator(all_models, 4)
    api_models = p1.get_page(request.GET.get('page'))
    p2 = Paginator(ApiRequestRecord.objects.filter(user=user).order_by('-created_at'), 10)
    recent_records = p2.get_page(request.GET.get('page2'))
    recent_trans = Transaction.objects.filter(user=user).order_by('-created_at')[:10]

    total_calls = ApiRequestRecord.objects.filter(user=user).count()
    total_cost = ApiRequestRecord.objects.filter(user=user).aggregate(
        total=Sum('cost')
    )['total'] or 0

    # 每日调用趋势 (最近7天)
    days = []
    calls_per_day = []
    today = timezone.now().date()
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        days.append(d.strftime('%m-%d'))
        count = ApiRequestRecord.objects.filter(
            user=user, created_at__date=d
        ).count()
        calls_per_day.append(count)

    # 模型费用分布
    model_costs = ApiRequestRecord.objects.filter(
        user=user, cost__gt=0
    ).values('api_model__name').annotate(
        total=Sum('cost')
    ).order_by('-total')[:8]
    cost_labels = [m['api_model__name'] or '未知' for m in model_costs]
    cost_data = [float(m['total']) for m in model_costs]

    # 交易流水 (最近10条金额)
    trans = Transaction.objects.filter(user=user).order_by('-created_at')[:12]
    trans_labels = [t.created_at.strftime('%m-%d %H:%M') for t in reversed(trans)]
    trans_data = [float(t.amount) for t in reversed(trans)]
    trans_colors = ['#00e676' if t.type == 'recharge' else '#ff1744' if t.type == 'consume' else '#7c4dff' for t in reversed(trans)]

    today = timezone.now().date()
    today_recharge = Decimal('0')
    today_consume = Decimal('0')
    total_consume = Decimal('0')
    total_recharge = Decimal('0')
    today_commission = Decimal('0')
    sub_total_consume = Decimal('0')
    sub_today_consume = Decimal('0')
    sub_tokens = 0
    sub_calls = 0
    sub_member_count = 0
    admin_tokens = 0
    admin_total_calls = 0
    agent_count = 0
    member_count = 0
    total_commission = Decimal('0')
    today_rechargers = []
    total_tokens = 0

    if user.role == 'admin':
        today_recharge = Transaction.objects.filter(type='recharge', created_at__date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        today_rechargers = User.objects.filter(
            transaction__type='recharge', transaction__created_at__date=today
        ).annotate(today_amount=Sum('transaction__amount')).distinct()[:10]
        total_recharge = Transaction.objects.filter(type='recharge').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        agent_count = AgentProfile.objects.count()
        member_count = User.objects.filter(role='member').count()
        admin_tokens = 0
        try:
            recs = ApiRequestRecord.objects.filter(status='success').values_list('response_data', flat=True)[:1000]
            for resp in recs:
                if isinstance(resp, dict):
                    b = resp.get('body', {})
                    if isinstance(b, dict):
                        u = b.get('usage', {})
                        if isinstance(u, dict):
                            admin_tokens += int(u.get('total_tokens', 0))
        except Exception:
            pass
        admin_total_calls = ApiRequestRecord.objects.count()
    elif user.role == 'agent':
        profile = AgentProfile.objects.filter(user=user).first()
        if profile:
            today_commission = CommissionRecord.objects.filter(agent=profile, created_at__date=today).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')
            total_commission = CommissionRecord.objects.filter(agent=profile, status='settled').aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')
            sub_total_consume = Transaction.objects.filter(user__parent_agent=user, type='consume').aggregate(total=Sum('amount'))['total'] or Decimal('0')
            sub_today_consume = Transaction.objects.filter(user__parent_agent=user, type='consume', created_at__date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            sub_tokens = 0
            try:
                records = ApiRequestRecord.objects.filter(user__parent_agent=user, status='success').values_list('response_data', flat=True)[:500]
                for resp in records:
                    if isinstance(resp, dict):
                        b = resp.get('body', {})
                        if isinstance(b, dict):
                            u = b.get('usage', {})
                            if isinstance(u, dict):
                                sub_tokens += int(u.get('total_tokens', 0))
            except Exception:
                pass
            sub_calls = ApiRequestRecord.objects.filter(user__parent_agent=user).count()
            sub_member_count = User.objects.filter(parent_agent=user).count()
    else:
        today_consume = Transaction.objects.filter(user=user, type='consume', created_at__date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_consume = Transaction.objects.filter(user=user, type='consume').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_recharge = Transaction.objects.filter(user=user, type='recharge').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        try:
            from django.db.models.functions import Cast
            from django.db.models import IntegerField
            token_records = ApiRequestRecord.objects.filter(
                user=user, status='success',
                response_data__isnull=False
            ).values_list('response_data', flat=True)[:500]
            for resp in token_records:
                if isinstance(resp, dict):
                    body = resp.get('body', {})
                    if isinstance(body, dict):
                        usage = body.get('usage', {})
                        if isinstance(usage, dict):
                            total_tokens += int(usage.get('total_tokens', 0))
        except Exception:
            pass

    # 按日累计交易(最近14天)
    from django.db import connection
    try:
        trans_daily = Transaction.objects.filter(user=user).extra(
            select={'day': "DATE(created_at)"}
        ).values('day', 'type').annotate(total=Sum('amount')).order_by('-day')[:14]
    except Exception:
        trans_daily = []
    daily_data = {}
    for t in reversed(list(trans_daily)):
        day_str = str(t['day']) if t['day'] else '?'
        d = day_str[5:] if len(day_str) >= 10 and day_str[4] == '-' else day_str
        if d not in daily_data:
            daily_data[d] = {'r': 0, 'c': 0}
        if t['type'] == 'recharge':
            daily_data[d]['r'] += float(t['total'])
        else:
            daily_data[d]['c'] += float(abs(t['total']))

    ctx = {
        'api_models': api_models,
        'page_obj': api_models,
        'recent_records': recent_records,
        'page_obj2': recent_records,
        'recent_trans': recent_trans,
        'total_calls': total_calls,
        'total_cost': total_cost,
        'today_recharge': today_recharge,
        'today_consume': abs(today_consume),
        'total_consume': abs(total_consume),
        'total_recharge': abs(total_recharge),
        'agent_count': agent_count if user.role == 'admin' else 0,
        'member_count': member_count if user.role == 'admin' else 0,
        'admin_tokens': admin_tokens if user.role == 'admin' else 0,
        'admin_total_calls': admin_total_calls if user.role == 'admin' else 0,
        'total_tokens': total_tokens,
        'today_commission': today_commission,
        'today_rechargers': today_rechargers,
        'sub_total_consume': abs(sub_total_consume) if user.role == 'agent' else Decimal('0'),
        'sub_today_consume': abs(sub_today_consume) if user.role == 'agent' else Decimal('0'),
        'sub_tokens': sub_tokens if user.role == 'agent' else 0,
        'sub_calls': sub_calls if user.role == 'agent' else 0,
        'sub_member_count': sub_member_count if user.role == 'agent' else 0,
        'total_commission': total_commission if user.role == 'agent' else Decimal('0'),
        'user': user,
        'chart_days': days,
        'chart_calls': calls_per_day,
        'cost_labels': cost_labels,
        'cost_data': cost_data,
        'trans_labels': trans_labels,
        'trans_data': trans_data,
        'trans_colors': trans_colors,
        'daily_labels': list(daily_data.keys()),
        'daily_recharge': [daily_data[k]['r'] for k in daily_data],
        'daily_consume': [daily_data[k]['c'] for k in daily_data],
    }
    return render(request, 'dashboard.html', ctx)


@login_required
def api_model_list(request):
    from django.db.models import Q
    qs = ApiModel.objects.select_related('channel').filter(status='enabled')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))

    bill_type = request.GET.get('bill', '')
    if bill_type in ('per_call', 'per_unit', 'free'):
        qs = qs.filter(bill_type=bill_type)

    vendor = request.GET.get('vendor', '')
    if vendor:
        qs = qs.filter(channel__code=vendor)

    qs = qs.order_by('channel__sort_order', 'sort_order')
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    channels = Channel.objects.filter(status='enabled').order_by('sort_order')
    view_mode = request.GET.get('view', 'card')

    return render(request, 'apimodels/list.html', {
        'api_models': page_obj, 'page_obj': page_obj,
        'channels': channels, 'view_mode': view_mode,
        'search': search, 'bill_type': bill_type, 'vendor': vendor,
    })


@login_required
def api_model_detail(request, model_id):
    api_model = get_object_or_404(ApiModel, id=model_id)
    params = api_model.parameters.all().order_by('sort_order')
    return render(request, 'apimodels/detail.html', {
        'api_model': api_model,
        'params': params,
    })


@login_required
def api_docs(request):
    from markdown.extensions.toc import TocExtension
    docs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'PLATFORM_DOCS.md')
    if os.path.exists(docs_path):
        with open(docs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        toc_md = markdown.Markdown(extensions=[TocExtension(baselevel=1, toc_depth='2-3')])
        toc_md.convert(content)
        toc_html = toc_md.toc or ''
        html_content = markdown.markdown(content, extensions=['extra', 'codehilite', 'toc'])
    else:
        toc_html = ''
        html_content = '<h3>文档未找到</h3><p>API调用说明文档不存在，请联系管理员。</p>'
    
    return render(request, 'apimodels/docs.html', {
        'docs_content': html_content,
        'toc_html': toc_html,
    })


def serve_static(request, path):
    import os
    from django.conf import settings
    full = os.path.normpath(os.path.join(settings.BASE_DIR, 'static', path))
    if '..' in path or not full.startswith(os.path.normpath(os.path.join(settings.BASE_DIR, 'static'))):
        raise Http404
    if not os.path.exists(full) or os.path.isdir(full):
        return HttpResponse(f'File not found: {full}', status=404)
    content_type, _ = mimetypes.guess_type(full)
    with open(full, 'rb') as f:
        return HttpResponse(f.read(), content_type=content_type or 'application/octet-stream')
