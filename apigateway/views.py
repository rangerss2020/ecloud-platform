import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, StreamingHttpResponse
from django.db.models import Q
import json
import os
import time
import requests
import json
from apimodels.models import Channel, ApiModel, ApiParameter
from billing.models import Transaction
from .models import ApiRequestRecord, SensitiveWord
from .filter import filter_instance
from .openapi import forward_api
from .balance import deduct_balance
from ecloud_api import call_ecloud_api


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin', login_url='user_login')(view)


@admin_required
def manage_channels(request):
    channels = Channel.objects.all().order_by('sort_order')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add':
            Channel.objects.create(
                name=request.POST.get('name', ''),
                code=request.POST.get('code', ''),
                base_url=request.POST.get('base_url', ''),
                auth_type=request.POST.get('auth_type', 'hmac'),
                access_key=request.POST.get('access_key', ''),
                secret_key=request.POST.get('secret_key', ''),
                api_key=request.POST.get('api_key', ''),
                description=request.POST.get('description', ''),
                status=request.POST.get('status', 'enabled'),
            )
            messages.success(request, '渠道添加成功')
        elif action == 'edit':
            ch = get_object_or_404(Channel, id=request.POST.get('id'))
            ch.name = request.POST.get('name', ch.name)
            ch.code = request.POST.get('code', ch.code)
            ch.base_url = request.POST.get('base_url', ch.base_url)
            ch.auth_type = request.POST.get('auth_type', ch.auth_type)
            ch.access_key = request.POST.get('access_key', ch.access_key)
            ch.secret_key = request.POST.get('secret_key', ch.secret_key)
            ch.api_key = request.POST.get('api_key', ch.api_key)
            ch.description = request.POST.get('description', ch.description)
            ch.status = request.POST.get('status', ch.status)
            ch.save()
            messages.success(request, '渠道更新成功')
        elif action == 'delete':
            Channel.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, '渠道已删除')
        return redirect('manage_channels')

    paginator = Paginator(channels, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    search = request.GET.get('q', '').strip()
    if search:
        from django.db.models import Q
        page_obj = Paginator(Channel.objects.filter(Q(name__icontains=search) | Q(code__icontains=search)).order_by('sort_order'), 20).get_page(request.GET.get('page'))
    return render(request, 'admin_manage/channels.html', {'channels': page_obj, 'page_obj': page_obj, 'search': search})


@admin_required
def manage_models(request):
    channels = Channel.objects.filter(status='enabled').order_by('sort_order')
    qs = ApiModel.objects.select_related('channel').all()
    search = request.GET.get('q', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
    qs = qs.order_by('channel__sort_order', 'sort_order')
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add':
            channel = get_object_or_404(Channel, id=request.POST.get('channel_id'))
            model = ApiModel.objects.create(
                channel=channel,
                name=request.POST.get('name', ''),
                code=request.POST.get('code', ''),
                servlet_path=request.POST.get('servlet_path', ''),
                http_method=request.POST.get('http_method', 'POST'),
                bill_type=request.POST.get('bill_type', 'per_call'),
                price=request.POST.get('price', 0),
                unit_type=request.POST.get('unit_type', ''),
                icon=request.POST.get('icon', ''),
                description=request.POST.get('description', ''),
                status=request.POST.get('status', 'enabled'),
            )
            icon_file = request.FILES.get('icon_file')
            if icon_file:
                ext = os.path.splitext(icon_file.name)[1].lower()
                if ext in ('.svg','.png','.jpg','.jpeg','.webp'):
                    fname = f'model_{model.code}{ext}'
                    dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'icons', fname)
                    with open(dest, 'wb+') as f:
                        for chunk in icon_file.chunks():
                            f.write(chunk)
                    model.icon = fname
                    model.save(update_fields=['icon'])
            param_names = request.POST.getlist('param_name')
            param_types = request.POST.getlist('param_type')
            param_required = request.POST.getlist('param_required')
            param_desc = request.POST.getlist('param_desc')
            param_defaults = request.POST.getlist('param_default')
            for i, name in enumerate(param_names):
                if name.strip():
                    ApiParameter.objects.create(
                        model=model, param_name=name.strip(),
                        param_type=param_types[i] if i < len(param_types) else 'string',
                        required=str(i) in param_required,
                        description=param_desc[i] if i < len(param_desc) else '',
                        default_value=param_defaults[i] if i < len(param_defaults) else '',
                        sort_order=i,
                    )
            messages.success(request, '模型添加成功')
        elif action == 'edit':
            model = get_object_or_404(ApiModel, id=request.POST.get('id'))
            model.channel = get_object_or_404(Channel, id=request.POST.get('channel_id'))
            model.name = request.POST.get('name', model.name)
            model.code = request.POST.get('code', model.code)
            model.servlet_path = request.POST.get('servlet_path', model.servlet_path)
            model.http_method = request.POST.get('http_method', model.http_method)
            model.bill_type = request.POST.get('bill_type', model.bill_type)
            model.price = request.POST.get('price', model.price)
            model.unit_type = request.POST.get('unit_type', model.unit_type)
            icon_val = request.POST.get('icon', '')
            icon_file = request.FILES.get('icon_file')
            if icon_file and icon_val == '__custom__':
                ext = os.path.splitext(icon_file.name)[1].lower()
                if ext in ('.svg','.png','.jpg','.jpeg','.webp'):
                    fname = f'model_{model.code}{ext}'
                    dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'icons', fname)
                    with open(dest, 'wb+') as f:
                        for chunk in icon_file.chunks():
                            f.write(chunk)
                    model.icon = fname
                else:
                    model.icon = icon_val
            else:
                model.icon = icon_val
            model.description = request.POST.get('description', model.description)
            model.status = request.POST.get('status', model.status)
            model.save()
            model.parameters.all().delete()
            param_names = request.POST.getlist('param_name')
            param_types = request.POST.getlist('param_type')
            param_required = request.POST.getlist('param_required')
            param_desc = request.POST.getlist('param_desc')
            param_defaults = request.POST.getlist('param_default')
            for i, name in enumerate(param_names):
                if name.strip():
                    ApiParameter.objects.create(
                        model=model, param_name=name.strip(),
                        param_type=param_types[i] if i < len(param_types) else 'string',
                        required=str(i) in param_required,
                        description=param_desc[i] if i < len(param_desc) else '',
                        default_value=param_defaults[i] if i < len(param_defaults) else '',
                        sort_order=i,
                    )
            messages.success(request, '模型更新成功')
        elif action == 'delete':
            ApiModel.objects.filter(id=request.POST.get('id')).delete()
            messages.success(request, '模型已删除')
        return redirect('manage_models')

    return render(request, 'admin_manage/models.html', {
        'channels': channels,
        'models': page_obj,
        'page_obj': page_obj,
        'param_types': ApiParameter.PARAM_TYPE_CHOICES,
        'search': search,
    })


@login_required
def gateway_index(request):
    page1 = Paginator(ApiModel.objects.select_related('channel').filter(status='enabled').order_by('channel__sort_order', 'sort_order'), 10)
    api_models = page1.get_page(request.GET.get('page'))
    page2 = Paginator(ApiRequestRecord.objects.filter(user=request.user).order_by('-created_at'), 15)
    records = page2.get_page(request.GET.get('page2'))
    return render(request, 'gateway/index.html', {
        'api_models': api_models, 'page_obj': api_models,
        'records': records, 'page_obj2': records,
    })


@login_required
def api_test(request, model_id):
    api_model = get_object_or_404(ApiModel.objects.select_related('channel'), id=model_id, status='enabled')
    params = api_model.parameters.all().order_by('sort_order')

    if request.method == 'POST':
        if api_model.bill_type != 'free' and request.user.balance < api_model.price:
            messages.error(request, f'余额不足，需要 {api_model.price} 元，当前余额 {request.user.balance} 元')
            return render(request, 'gateway/test.html', {'api_model': api_model, 'params': params, 'post_data': request.POST})

        body_data = {}
        for p in params:
            val = request.POST.get(p.param_name, p.default_value)
            if val:
                if p.param_type == 'integer':
                    try: val = int(val)
                    except ValueError: val = 0
                elif p.param_type == 'number':
                    try: val = float(val)
                    except ValueError: val = 0.0
                elif p.param_type == 'boolean':
                    val = val.lower() in ('true', '1', 'yes')
                elif p.param_type in ('array', 'object'):
                    try: val = json.loads(val)
                    except (json.JSONDecodeError, TypeError): pass
            elif p.required:
                messages.error(request, f'参数 {p.param_name} 是必填的')
                return render(request, 'gateway/test.html', {'api_model': api_model, 'params': params, 'post_data': request.POST})
            body_data[p.param_name] = val

        balance_before = request.user.balance
        channel = api_model.channel

        result = forward_api(channel, api_model, body_data)

        duration_ms = result.pop('_duration_ms', 0)
        response_state = result.get('state', 'OK')
        cost = api_model.price if response_state == 'OK' else 0

        if cost > 0:
            ok, _ = deduct_balance(request.user, cost, f'调用 {api_model.name}')
            if not ok:
                cost = 0

        record = ApiRequestRecord.objects.create(
            user=request.user, api_model=api_model,
            request_method=api_model.http_method,
            request_url=f"{channel.base_url}{api_model.servlet_path}",
            request_params=body_data, response_data=result,
            response_state=response_state, cost=cost,
            balance_before=balance_before, balance_after=request.user.balance,
            status='success' if response_state == 'OK' else 'failed',
            duration_ms=duration_ms,
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        response_json = json.dumps(result, indent=2, ensure_ascii=False)
        return render(request, 'gateway/result.html', {
            'api_model': api_model, 'record': record,
            'response_data': result, 'response_json': response_json,
            'balance_before': balance_before,
        })

    return render(request, 'gateway/test.html', {'api_model': api_model, 'params': params})


@login_required
def api_records(request):
    paginator = Paginator(ApiRequestRecord.objects.select_related('api_model').filter(user=request.user).order_by('-created_at'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'gateway/records.html', {'records': page_obj, 'page_obj': page_obj})


@admin_required
def manage_sensitive_words(request):
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add':
            SensitiveWord.objects.create(
                word=request.POST.get('word', '').strip(),
                level=request.POST.get('level', 'replace'),
                replacement=request.POST.get('replacement', '***'),
                category=request.POST.get('category', ''),
            )
            filter_instance.reload()
            messages.success(request, '敏感词已添加')
        elif action == 'toggle':
            w = get_object_or_404(SensitiveWord, id=request.POST.get('id'))
            w.enabled = not w.enabled
            w.save()
            filter_instance.reload()
        elif action == 'delete':
            SensitiveWord.objects.filter(id=request.POST.get('id')).delete()
            filter_instance.reload()
            messages.success(request, '已删除')
        return redirect('manage_sensitive_words')

    search = request.GET.get('q', '').strip()
    qs = SensitiveWord.objects.all()
    if search:
        qs = qs.filter(word__icontains=search)
    paginator = Paginator(qs.order_by('-created_at'), 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_manage/sensitive_words.html', {'words': page_obj, 'page_obj': page_obj, 'search': search})


@login_required
def chat(request):
    from django.http import JsonResponse
    chat_models = ApiModel.objects.select_related('channel').filter(status='enabled').order_by('channel__sort_order', 'sort_order')

    if request.method == 'POST':
        model_id = request.POST.get('model_id', '')
        user_message = request.POST.get('message', '').strip()

        if not user_message:
            messages.error(request, '请输入消息')
            return redirect('chat')

        api_model = get_object_or_404(ApiModel.objects.select_related('channel'), id=model_id, status='enabled')

        if api_model.bill_type != 'free' and request.user.balance < api_model.price:
            messages.error(request, f'余额不足，需要 ¥{api_model.price}')
            return redirect('chat')

        history = request.session.get('chat_history', [])
        history.append({'role': 'user', 'content': user_message})

        # 按模型参数构造请求体
        body = {}
        params = {p.param_name: p for p in api_model.parameters.all()}
        if 'messages' in params or 'model' in params:
            if 'messages' in params:
                body['messages'] = history
            elif 'prompt' in params:
                body['prompt'] = user_message
            if 'model' in params:
                body['model'] = params['model'].default_value or 'default'
        else:
            body['model'] = api_model.code
            body['messages'] = history

        filtered_body, input_hits = filter_instance.filter_body(body)

        if any(filter_instance._words.get(h, {}).get('level') == 'block' for h in input_hits if h in filter_instance._words):
            messages.error(request, '消息包含敏感内容，已被拦截')
            return redirect('chat')

        balance_before = request.user.balance

        result = forward_api(api_model.channel, api_model, filtered_body)

        response_state = result.get('state', 'OK')
        cost = api_model.price if response_state == 'OK' else 0

        if cost > 0:
            ok, _ = deduct_balance(request.user, cost, f'对话: {api_model.name}')
            if not ok:
                cost = 0

        assistant_content = ''
        if response_state == 'OK':
            body_resp = result.get('body', {})
            if isinstance(body_resp, dict):
                assistant_content = body_resp.get('choices', [{}])[0].get('message', {}).get('content', '')
                if not assistant_content:
                    assistant_content = body_resp.get('choices', [{}])[0].get('text', '')
            elif isinstance(body_resp, str):
                assistant_content = body_resp
            if not assistant_content:
                assistant_content = json.dumps(result, ensure_ascii=False)

            filtered_content, out_hits = filter_instance.filter_body(assistant_content)
            assistant_content = filtered_content if filtered_content else assistant_content
        else:
            assistant_content = f'[错误] {result.get("errorMessage", result.get("errorCode", "Unknown error"))}'

        history.append({'role': 'assistant', 'content': assistant_content})
        request.session['chat_history'] = history

        ApiRequestRecord.objects.create(
            user=request.user, api_model=api_model,
            request_method=api_model.http_method,
            request_url=f"{api_model.channel.base_url}{api_model.servlet_path}",
            request_params=body, response_data=result,
            response_state=response_state, cost=cost,
            balance_before=balance_before, balance_after=request.user.balance,
            status='success' if response_state == 'OK' else 'failed',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        return render(request, 'gateway/chat.html', {
            'chat_models': chat_models,
            'selected_model': api_model,
            'history': history[-10:],
        })

    selected = request.GET.get('model', '')
    selected_model = None
    if selected:
        selected_model = ApiModel.objects.filter(id=selected, status='enabled').first()
    return render(request, 'gateway/chat.html', {
        'chat_models': chat_models,
        'selected_model': selected_model,
        'history': request.session.get('chat_history', [])[-10:],
    })


@login_required
def clear_chat(request):
    request.session['chat_history'] = []
    return redirect('chat')


@login_required
def chat_stream(request):
    import json as json_lib

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    model_id = request.POST.get('model_id', '')
    user_message = request.POST.get('message', '').strip()

    if not user_message:
        return JsonResponse({'error': 'empty'})

    api_model = get_object_or_404(ApiModel.objects.select_related('channel'), id=model_id, status='enabled')
    channel = api_model.channel

    if channel.auth_type != 'bearer':
        return JsonResponse({'error': 'unsupported auth'})

    history = request.session.get('chat_history', [])
    history.append({'role': 'user', 'content': user_message})

    body = {'model': api_model.code, 'messages': history}
    params = {p.param_name: p for p in api_model.parameters.all()}
    if 'model' in params:
        body['model'] = params['model'].default_value or api_model.code

    filtered_body, input_hits = filter_instance.filter_body(body)
    if any(filter_instance._words.get(h, {}).get('level') == 'block' for h in input_hits if h in filter_instance._words):
        return JsonResponse({'error': 'blocked'})

    url = f'{channel.base_url}{api_model.servlet_path}'
    headers = {'Authorization': f'Bearer {channel.api_key}', 'Content-Type': 'application/json'}
    start_time = time.time()

    try:
        resp = requests.post(url, json=filtered_body, headers=headers, timeout=120)
        resp.raise_for_status()
        result = resp.json()
    except Exception:
        return JsonResponse({'error': 'Upstream service unavailable'}, status=500)

    duration_ms = int((time.time() - start_time) * 1000)
    assistant_content = ''
    choices = result.get('choices', [])
    if choices:
        msg = choices[0].get('message', {})
        assistant_content = msg.get('content', '') or choices[0].get('text', '')
    if not assistant_content:
        assistant_content = json_lib.dumps(result, ensure_ascii=False)

    filtered_content, _ = filter_instance.filter_body(assistant_content)
    if filtered_content:
        assistant_content = filtered_content

    history.append({'role': 'assistant', 'content': assistant_content})
    request.session['chat_history'] = history

    if api_model.bill_type != 'free':
        deduct_balance(request.user, api_model.price, f'对话: {api_model.name}')

    return JsonResponse({
        'content': assistant_content,
        'duration_ms': duration_ms,
        'cost': float(api_model.price),
    })

