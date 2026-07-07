import json
import time
import requests
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from apimodels.models import ApiModel
from billing.models import Transaction
from .models import ApiRequestRecord
from .balance import deduct_balance
from .filter import filter_instance


@csrf_exempt
def openai_models(request):
    models = ApiModel.objects.filter(status='enabled', task_type='chat').order_by('sort_order')
    data = [{'id': m.code, 'object': 'model', 'created': int(m.created_at.timestamp()), 'owned_by': m.channel.name} for m in models]
    return JsonResponse({'object': 'list', 'data': data})


@csrf_exempt
def openai_chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': {'message': 'Method not allowed', 'type': 'invalid_request_error'}}, status=405)

    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Bearer '):
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    from users.models import User
    try:
        user = User.objects.get(api_key=auth[7:], is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    body = request.body

    try:
        body_json = json.loads(body)
        model_code = body_json.get('model', '').lower()
    except json.JSONDecodeError:
        return JsonResponse({'error': {'message': 'Invalid JSON', 'type': 'invalid_request_error'}}, status=400)

    api_model = ApiModel.objects.filter(code=model_code, status='enabled', task_type='chat').select_related('channel').first()
    if not api_model:
        return JsonResponse({'error': {'message': f'Model {model_code} not found', 'type': 'model_not_found'}}, status=404)

    channel = api_model.channel
    if channel.auth_type != 'bearer':
        return JsonResponse({'error': {'message': 'Unsupported auth', 'type': 'server_error'}}, status=500)

    for msg in body_json.get('messages', []):
        content = msg.get('content', '') if isinstance(msg, dict) else ''
        if isinstance(content, str) and content:
            _, _, blocked = filter_instance.check(content)
            if blocked:
                return JsonResponse({'error': {'message': 'Content blocked by policy', 'type': 'content_filter'}}, status=403)

    is_per_call = api_model.bill_type == 'per_call'
    is_per_unit = api_model.bill_type == 'per_unit'

    if is_per_call:
        cost = float(api_model.price)
        if user.balance < cost:
            return JsonResponse({'error': {'message': 'Insufficient balance', 'type': 'insufficient_quota'}}, status=402)
    else:
        cost = 0

    url = f'{channel.base_url}{api_model.servlet_path}'

    is_stream = body_json.get('stream', False) is True
    upstream_headers = {
        'Authorization': f'Bearer {channel.api_key}',
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream' if is_stream else 'application/json',
    }

    balance_before = user.balance
    start_time = time.time()

    try:
        upstream_resp = requests.request(
            method='POST', url=url, headers=upstream_headers,
            data=body, stream=is_stream, timeout=120,
        )
    except Exception:
        return JsonResponse({'error': {'message': 'Upstream service unavailable', 'type': 'server_error'}}, status=502)

    duration_ms = int((time.time() - start_time) * 1000)

    if is_stream:
        def generate():
            prompt_tokens = 0
            completion_tokens = 0
            try:
                for chunk in upstream_resp.iter_content(chunk_size=None):
                    yield chunk
                    line = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                    for part in line.split('\n'):
                        if not part.startswith('data: '):
                            continue
                        raw = part.replace('data: ', '', 1)
                        if raw.strip() == '[DONE]':
                            continue
                        try:
                            data = json.loads(raw)
                            u = data.get('usage')
                            if u:
                                prompt_tokens = u.get('prompt_tokens', 0)
                                completion_tokens = u.get('completion_tokens', 0)
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass

            if is_per_call and cost > 0:
                ok, ba = deduct_balance(user, cost, f'API: {api_model.name}')
                balance_after = ba if ok else balance_before
            elif is_per_unit:
                total = prompt_tokens + completion_tokens
                if api_model.unit_type == 'per_1m':
                    actual_cost = round(total / 1000000.0 * float(api_model.price), 6)
                elif api_model.unit_type == 'per_1k':
                    actual_cost = round(total / 1000.0 * float(api_model.price), 6)
                else:
                    actual_cost = float(api_model.price)
                if actual_cost > 0:
                    ok, ba = deduct_balance(user, actual_cost, f'API: {api_model.name} ({total} tokens)')
                    balance_after = ba if ok else balance_before
                    cost = actual_cost
                else:
                    balance_after = balance_before
            else:
                balance_after = balance_before

            ApiRequestRecord.objects.create(
                user=user, api_model=api_model, request_method='POST',
                request_url=url, request_params=json.loads(body),
                response_state='OK', cost=cost,
                balance_before=balance_before, balance_after=balance_after,
                status='success', duration_ms=duration_ms,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )

        sse_resp = StreamingHttpResponse(generate(), content_type='text/event-stream')
        sse_resp['Cache-Control'] = 'no-cache'
        sse_resp['X-Accel-Buffering'] = 'no'
        return sse_resp

    upstream_resp.raise_for_status()

    result_data = upstream_resp.json()

    usage = result_data.get('usage', {})
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)

    if is_per_call and cost > 0:
        ok, ba = deduct_balance(user, cost, f'API: {api_model.name}')
        balance_after = ba if ok else balance_before
    elif is_per_unit:
        total = prompt_tokens + completion_tokens
        if api_model.unit_type == 'per_1m':
            actual_cost = round(total / 1000000.0 * float(api_model.price), 6)
        elif api_model.unit_type == 'per_1k':
            actual_cost = round(total / 1000.0 * float(api_model.price), 6)
        else:
            actual_cost = float(api_model.price)
        if actual_cost > 0:
            ok, ba = deduct_balance(user, actual_cost, f'API: {api_model.name} ({total} tokens)')
            balance_after = ba if ok else balance_before
            cost = actual_cost
        else:
            balance_after = balance_before
    else:
        balance_after = balance_before

    ApiRequestRecord.objects.create(
        user=user, api_model=api_model, request_method='POST',
        request_url=url, request_params=json.loads(body),
        response_state='OK', cost=cost,
        balance_before=balance_before, balance_after=balance_after,
        status='success', duration_ms=duration_ms,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    return JsonResponse(result_data)
