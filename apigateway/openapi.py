import json
import time
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apimodels.models import ApiModel
from billing.models import Transaction
from .models import ApiRequestRecord
from .filter import filter_instance
from ecloud_api import call_ecloud_api, call_bearer_api
from users.signature import verify_user_signature, verify_user_apikey
from .balance import deduct_balance


def forward_api(channel, api_model, body_data, headers=None):
    if channel.auth_type == 'bearer':
        return call_bearer_api(
            base_url=channel.base_url,
            servlet_path=api_model.servlet_path,
            http_method=api_model.http_method,
            api_key=channel.api_key,
            body_data=body_data,
            headers=headers,
        )
    else:
        return call_ecloud_api(
            base_url=channel.base_url,
            servlet_path=api_model.servlet_path,
            http_method=api_model.http_method,
            access_key=channel.access_key,
            secret_key=channel.secret_key,
            body_data=body_data,
        )


@csrf_exempt
def open_api(request, model_code):
    if request.method not in ('GET', 'POST', 'PUT', 'DELETE'):
        return JsonResponse({'state': 'ERROR', 'error': 'Method not allowed'}, status=405)

    user, err_code, err_msg = verify_user_apikey(request)
    if user is None:
        user, err_code, err_msg = verify_user_signature(request)
    if user is None:
        return JsonResponse({
            'state': 'ERROR', 'errorCode': err_code, 'errorMessage': err_msg, 'requestId': '',
        }, status=401)

    api_model = get_object_or_404(ApiModel.objects.select_related('channel'), code=model_code, status='enabled')
    channel = api_model.channel

    if api_model.bill_type != 'free' and user.balance < api_model.price:
        return JsonResponse({
            'state': 'ERROR', 'errorCode': 'INSUFFICIENT_BALANCE',
            'errorMessage': 'Insufficient balance',
            'requestId': '',
        }, status=402)

    body_data = {}
    if request.content_type == 'application/json' and request.body:
        try:
            body_data = json.loads(request.body)
        except json.JSONDecodeError:
            body_data = {}
    if not body_data:
        body_data = dict(request.POST.dict())

    to_remove = ['AccessKey', 'Timestamp', 'Signature', 'SignatureMethod',
                 'SignatureNonce', 'SignatureVersion']
    for k in to_remove:
        body_data.pop(k, None)

    filtered_body, input_hits = filter_instance.filter_body(body_data)
    all_hits = list(input_hits)

    if any(filter_instance._words.get(h, {}).get('level') == 'block' for h in input_hits if h in filter_instance._words):
        return JsonResponse({
            'state': 'ERROR',
            'errorCode': 'CONTENT_BLOCKED',
            'errorMessage': 'Content blocked by sensitive word filter',
            'requestId': '',
            'blockedWords': [h for h in input_hits if filter_instance._words.get(h, {}).get('level') == 'block'],
        }, status=403)

    balance_before = user.balance
    start_time = time.time()

    result = forward_api(channel, api_model, filtered_body)

    duration_ms = int((time.time() - start_time) * 1000)
    response_state = result.get('state', None)
    if response_state is None:
        response_state = 'OK' if result.get('_status_code', 0) == 200 else 'ERROR'
    cost = api_model.price if response_state == 'OK' else 0

    if response_state == 'OK' and 'body' in result:
        filtered_resp, output_hits = filter_instance.filter_body(result.get('body'))
        if filtered_resp:
            result['body'] = filtered_resp
        all_hits.extend(output_hits)

    if cost > 0:
        ok, balance_after = deduct_balance(user, cost, f'API: {api_model.name}')
        if not ok:
            cost = 0
            balance_after = balance_before
    else:
        balance_after = balance_before

    ApiRequestRecord.objects.create(
        user=user, api_model=api_model,
        request_method=api_model.http_method,
        request_url=f"{channel.base_url}{api_model.servlet_path}",
        request_params=body_data, response_data=result,
        response_state=response_state, cost=cost,
        balance_before=balance_before, balance_after=balance_after,
        status='success' if response_state == 'OK' else 'failed',
        duration_ms=duration_ms,
        filter_hits=','.join(all_hits) if all_hits else '',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    result.pop('_duration_ms', None)
    result.pop('_status_code', None)
    result.setdefault('requestId', '')
    return JsonResponse(result)
