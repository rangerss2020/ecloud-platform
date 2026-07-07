import os
import time
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, StreamingHttpResponse
from django.db.models import Q
import requests
from apimodels.models import Channel, ApiModel, ApiParameter, Capability
from billing.models import Transaction
from .models import ApiRequestRecord, SensitiveWord, VideoTask
from .filter import filter_instance
from .openapi import forward_api
from .balance import deduct_balance
from ecloud_api import call_ecloud_api
from .video import _get_client_for_model

UPLOAD_ALLOWED = {'.jpg','.jpeg','.png','.gif','.webp','.mp4','.mov','.avi','.mp3','.wav','.ogg','.m4a'}
import logging
logger = logging.getLogger('apigateway.views')

def parse_json_field(val):
    if not val or not val.strip():
        return []
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []

def get_max_size(file_ext):
    if file_ext in {'.mp4','.mov','.avi'}:
        return 200 * 1024 * 1024
    if file_ext in {'.mp3','.wav','.ogg','.m4a'}:
        return 50 * 1024 * 1024
    return 10 * 1024 * 1024


@login_required
def upload_media(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file'}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in UPLOAD_ALLOWED:
        return JsonResponse({'error': f'Unsupported format: {ext}'}, status=400)

    if file.size > get_max_size(ext):
        return JsonResponse({'error': 'File too large'}, status=400)

    upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = str(int(time.time() * 1000))
    safe_name = f'{request.user.id}_{timestamp}{ext}'
    filepath = os.path.join(upload_dir, safe_name)
    with open(filepath, 'wb+') as f:
        for chunk in file.chunks():
            f.write(chunk)

    url = f'{settings.MEDIA_URL}uploads/{safe_name}'

    media_type = 'image'
    if ext in {'.mp4','.mov','.avi'}:
        media_type = 'video'
    elif ext in {'.mp3','.wav','.ogg','.m4a'}:
        media_type = 'audio'

    return JsonResponse({
        'url': url,
        'type': media_type,
        'name': file.name,
    })


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
    import glob
    icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'icons')
    icon_files = [os.path.basename(f) for f in glob.glob(os.path.join(icon_dir, '*')) if os.path.splitext(f)[1] in ('.svg','.png','.jpg','.jpeg','.webp')]
    icon_files.sort()

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
                task_type=request.POST.get('task_type', 'chat'),
                bill_type=request.POST.get('bill_type', 'per_call'),
                price=request.POST.get('price', 0),
                unit_type=request.POST.get('unit_type', ''),
                icon=request.POST.get('icon', ''),
                description=request.POST.get('description', ''),
                status=request.POST.get('status', 'enabled'),
                duration_options=parse_json_field(request.POST.get('duration_options', '')),
                resolution_options=parse_json_field(request.POST.get('resolution_options', '')),
            )
            cap_ids = request.POST.getlist('capabilities')
            if cap_ids:
                model.capabilities.set(Capability.objects.filter(id__in=cap_ids))
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
            model.task_type = request.POST.get('task_type', model.task_type)
            model.duration_options = parse_json_field(request.POST.get('duration_options', ''))
            model.resolution_options = parse_json_field(request.POST.get('resolution_options', ''))
            model.save()
            cap_ids = request.POST.getlist('capabilities')
            model.capabilities.set(Capability.objects.filter(id__in=cap_ids))
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
        'all_capabilities': Capability.objects.all(),
        'icon_files': icon_files,
    })


@admin_required
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

        if api_model.task_type == 'video':
            return _chat_video_handler(request, api_model, user_message, chat_models)

        if api_model.bill_type != 'free' and request.user.balance < api_model.price:
            messages.error(request, f'余额不足，需要 ¥{api_model.price}')
            return redirect('chat')

        history = request.session.get('chat_history', [])
        history.append({'role': 'user', 'content': user_message})

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


def _chat_video_handler(request, api_model, user_message, chat_models):
    duration = int(request.POST.get('duration', 11))
    ratio = request.POST.get('ratio', '16:9')

    base_price = float(api_model.price)
    duration_mult = 1.0
    if api_model.duration_options:
        for opt in api_model.duration_options:
            if opt.get('seconds') == duration:
                duration_mult = opt.get('multiplier', 1.0)
                break
    resolution_mult = 1.0
    if api_model.resolution_options:
        for opt in api_model.resolution_options:
            if opt.get('ratio') == ratio:
                resolution_mult = opt.get('multiplier', 1.0)
                break
    cost = round(base_price * duration_mult * resolution_mult, 2) if api_model.bill_type != 'free' else 0
    if cost > 0 and request.user.balance < cost:
        messages.error(request, f'余额不足，需要 ¥{cost}')
        return redirect('chat')

    _, _, blocked = filter_instance.check(user_message)
    if blocked:
        messages.error(request, '消息包含敏感内容')
        return redirect('chat')

    request_data = {
        'content': [{'type': 'text', 'text': user_message}],
        'generate_audio': True,
        'ratio': ratio,
        'duration': duration,
        'watermark': False,
    }

    client = _get_client_for_model(api_model)
    try:
        task_id = client.create_video_generation_task(request_data)
    except Exception as e:
        messages.error(request, f'视频生成失败: {e}')
        return redirect('chat')

    if not task_id:
        messages.error(request, '视频生成请求被上游拒绝，请确认API Key已订购Seedance 2.0模型')
        return redirect('chat')

    if cost > 0:
        ok, _ = deduct_balance(request.user, cost, f'视频生成: {api_model.name}')
        if not ok:
            messages.error(request, '扣费失败')
            return redirect('chat')

    VideoTask.objects.create(
        user=request.user,
        api_model=api_model,
        remote_task_id=task_id,
        status='pending',
        prompt_text=user_message,
        request_data=request_data,
        cost=cost,
    )

    history = request.session.get('chat_history', [])
    history.append({'role': 'user', 'content': user_message, 'type': 'text'})
    history.append({'role': 'assistant', 'content': '', 'type': 'video', 'video_task_id': task_id, 'video_status': 'pending'})
    request.session['chat_history'] = history

    return render(request, 'gateway/chat.html', {
        'chat_models': chat_models,
        'selected_model': api_model,
        'history': history[-10:],
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

    is_json = request.content_type == 'application/json'
    model_id = ''
    user_message = ''

    if is_json:
        try:
            body = json.loads(request.body)
            model_id = body.get('model_id', '')
            user_message = body.get('message', '').strip()
        except (json.JSONDecodeError, ValueError):
            pass
    else:
        model_id = request.POST.get('model_id', '')
        user_message = request.POST.get('message', '').strip()

    if not user_message:
        return JsonResponse({'error': 'empty'})

    api_model = get_object_or_404(ApiModel.objects.select_related('channel'), id=model_id, status='enabled')
    channel = api_model.channel

    if api_model.task_type == 'video':
        return _handle_video_chat(request, api_model, user_message)

    if channel.auth_type != 'bearer':
        return JsonResponse({'error': 'unsupported auth'})

    history = request.session.get('chat_history', [])

    ref_images = []
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            ref_images = body.get('ref_images', []) if isinstance(body, dict) else []
        except (json.JSONDecodeError, ValueError):
            pass

    if ref_images:
        host = request.build_absolute_uri('/').rstrip('/')
        content = [{'type': 'text', 'text': user_message}]
        for img_url in ref_images:
            full_url = img_url if img_url.startswith('http') else host + img_url
            content.append({'type': 'image_url', 'image_url': {'url': full_url}})
        history.append({'role': 'user', 'content': content})
    else:
        history.append({'role': 'user', 'content': user_message})

    req_body = {'model': api_model.code, 'messages': history, 'stream': True}
    params = {p.param_name: p for p in api_model.parameters.all()}
    if 'model' in params:
        req_body['model'] = params['model'].default_value or api_model.code

    filtered_body, input_hits = filter_instance.filter_body(req_body)
    if any(filter_instance._words.get(h, {}).get('level') == 'block' for h in input_hits if h in filter_instance._words):
        return JsonResponse({'error': 'blocked'})

    url = f'{channel.base_url}{api_model.servlet_path}'
    headers = {'Authorization': f'Bearer {channel.api_key}', 'Content-Type': 'application/json'}

    is_per_call = api_model.bill_type == 'per_call'
    is_per_unit = api_model.bill_type == 'per_unit'
    cost_val = 0
    if is_per_call:
        cost_val = float(api_model.price)
        deduct_balance(request.user, cost_val, f'对话: {api_model.name}')

    record = ApiRequestRecord.objects.create(
        user=request.user, api_model=api_model,
        request_method='POST', request_url=url,
        request_params=filtered_body,
        response_state='OK', cost=cost_val,
        balance_before=0, balance_after=request.user.balance,
        status='success', duration_ms=0,
        prompt_tokens=0, completion_tokens=0,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    def generate():
        start_time = time.time()
        assistant_content = ''
        reasoning_content = ''
        prompt_tokens = 0
        completion_tokens = 0
        try:
            resp = requests.post(url, json=filtered_body, headers=headers, timeout=120, stream=True)
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                chunk = raw.replace('data: ', '', 1) if raw.startswith('data: ') else raw
                if chunk.strip() == '[DONE]':
                    break
                try:
                    data = json.loads(chunk)
                    u = data.get('usage')
                    if u:
                        prompt_tokens = u.get('prompt_tokens', 0) or 0
                        completion_tokens = u.get('completion_tokens', 0) or 0
                    choices = data.get('choices', [])
                    if choices:
                        delta = choices[0].get('delta', {})
                        if not delta:
                            continue
                        rt = delta.get('reasoning_content', '') or delta.get('reasoning', '') or ''
                        ct = delta.get('content', '') or ''
                        if rt:
                            reasoning_content += rt
                            yield f"data: {json_lib.dumps({'t': rt})}\n\n"
                        if ct:
                            assistant_content += ct
                            yield f"data: {json_lib.dumps({'c': ct})}\n\n"
                except (json.JSONDecodeError, KeyError):
                    continue

            duration_ms = int((time.time() - start_time) * 1000)

            full_content = assistant_content
            if reasoning_content:
                full_content = f"<think>{reasoning_content}</think>{assistant_content}"

            history.append({'role': 'assistant', 'content': full_content})
            request.session['chat_history'] = history

            ApiRequestRecord.objects.filter(id=record.id).update(
                duration_ms=duration_ms,
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=completion_tokens or 0,
                response_data={'body': {'choices': [{'message': {'content': full_content}}]}},
            )

            if is_per_unit and (prompt_tokens or completion_tokens):
                total = (prompt_tokens or 0) + (completion_tokens or 0)
                if api_model.unit_type == 'per_1m':
                    actual_cost = round(total / 1000000.0 * float(api_model.price), 6)
                elif api_model.unit_type == 'per_1k':
                    actual_cost = round(total / 1000.0 * float(api_model.price), 6)
                else:
                    actual_cost = float(api_model.price)
                if actual_cost > 0:
                    deduct_balance(request.user, actual_cost, f'对话: {api_model.name} ({total} tokens)')
                    ApiRequestRecord.objects.filter(id=record.id).update(cost=actual_cost)

            yield f"data: {json_lib.dumps({'d': duration_ms, 'pt': prompt_tokens, 'ct': completion_tokens})}\n\n"
        except Exception as e:
            yield f"data: {json_lib.dumps({'e': str(e)})}\n\n"

    response = StreamingHttpResponse(generate(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def _handle_video_chat(request, api_model, user_message):
    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        body = {}

    duration = int(body.get('duration', 11))
    ratio = body.get('ratio', '16:9')
    ref_images = body.get('ref_images', [])
    ref_videos = body.get('ref_videos', [])
    ref_audio = body.get('ref_audio', [])

    base_price = float(api_model.price)
    duration_mult = 1.0
    if api_model.duration_options:
        for opt in api_model.duration_options:
            if opt.get('seconds') == duration:
                duration_mult = opt.get('multiplier', 1.0)
                break

    resolution_mult = 1.0
    if api_model.resolution_options:
        for opt in api_model.resolution_options:
            if opt.get('ratio') == ratio:
                resolution_mult = opt.get('multiplier', 1.0)
                break

    cost = round(base_price * duration_mult * resolution_mult, 2) if api_model.bill_type != 'free' else 0
    if cost > 0 and request.user.balance < cost:
        return JsonResponse({'error': f'余额不足，需要 ¥{cost}'})

    _, _, blocked = filter_instance.check(user_message)
    if blocked:
        return JsonResponse({'error': '消息包含敏感内容'})

    host = request.build_absolute_uri('/').rstrip('/')
    content = [{'type': 'text', 'text': user_message}]

    for img_url in ref_images:
        full_url = img_url if img_url.startswith('http') else host + img_url
        content.append({'type': 'image_url', 'image_url': {'url': full_url}, 'role': 'reference_image'})
    for vid_url in ref_videos:
        full_url = vid_url if vid_url.startswith('http') else host + vid_url
        content.append({'type': 'video_url', 'video_url': {'url': full_url}, 'role': 'reference_video'})
    for aud_url in ref_audio:
        full_url = aud_url if aud_url.startswith('http') else host + aud_url
        content.append({'type': 'audio_url', 'audio_url': {'url': full_url}, 'role': 'reference_audio'})

    request_data = {
        'content': content,
        'generate_audio': True,
        'ratio': ratio,
        'duration': duration,
        'watermark': False,
    }

    client = _get_client_for_model(api_model)
    try:
        task_id = client.create_video_generation_task(request_data)
    except Exception as e:
        return JsonResponse({'error': f'视频生成失败: {str(e)}'})

    if not task_id:
        return JsonResponse({'error': '视频生成请求被上游拒绝，请确认API Key已订购Seedance 2.0模型'})

    if cost > 0:
        ok, _ = deduct_balance(request.user, cost, f'视频生成: {api_model.name} ({duration}s {ratio})')
        if not ok:
            return JsonResponse({'error': '扣费失败'})

    VideoTask.objects.create(
        user=request.user,
        api_model=api_model,
        remote_task_id=task_id,
        status='pending',
        prompt_text=user_message,
        request_data=request_data,
        cost=cost,
    )

    display_content = user_message
    if ref_images:
        display_content += f' [+{len(ref_images)}张图片]'
    if ref_videos:
        display_content += f' [+{len(ref_videos)}个视频]'
    if ref_audio:
        display_content += f' [+{len(ref_audio)}个音频]'

    history = request.session.get('chat_history', [])
    history.append({'role': 'user', 'content': display_content, 'type': 'text'})
    history.append({'role': 'assistant', 'content': '', 'type': 'video', 'video_task_id': task_id, 'video_status': 'pending'})
    request.session['chat_history'] = history

    return JsonResponse({
        'type': 'video',
        'task_id': task_id,
        'content': f'视频生成任务已提交 ({duration}秒 {ratio}, ¥{cost})',
        'status': 'pending',
        'cost': cost,
    })


@admin_required
def admin_api_records(request):
    from datetime import datetime as dt, timedelta
    from django.utils import timezone

    search = request.GET.get('q', '').strip()
    filter_model = request.GET.get('fm', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()

    qs = ApiRequestRecord.objects.select_related('user', 'api_model').all()
    if search:
        qs = qs.filter(user__username__icontains=search)
    if filter_model:
        qs = qs.filter(api_model__code=filter_model)
    if date_from:
        try:
            qs = qs.filter(created_at__gte=dt.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(created_at__lt=dt.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass

    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_manage/api_records.html', {
        'records': page_obj, 'page_obj': page_obj,
        'search': search, 'filter_model': filter_model,
        'date_from': date_from, 'date_to': date_to,
        'all_models': ApiModel.objects.filter(status='enabled').order_by('channel__sort_order', 'sort_order'),
    })

