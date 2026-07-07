import os
import json
import time
import threading
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apimodels.models import ApiModel, Channel
from .models import VideoTask
from .balance import deduct_balance
from .filter import filter_instance

logger = logging.getLogger('apigateway.video')

KEY_DIR = os.path.join(settings.MEDIA_ROOT, 'video_keys')
os.makedirs(KEY_DIR, exist_ok=True)

PUBLIC_KEY_PATH = os.path.join(KEY_DIR, 'seedance_pub.pem')
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, 'seedance_priv.pem')

_client_lock = threading.Lock()
_clients = {}


def get_seedance_client(base_url, api_key, model_code):
    key = f"{base_url}|{model_code}"
    if key not in _clients:
        with _client_lock:
            if key not in _clients:
                if not api_key:
                    raise RuntimeError('API Key not configured')

                from maas_seedance import MaasSeedanceClient
                client = MaasSeedanceClient(
                    maas_base_url=base_url,
                    maas_api_key=api_key,
                    maas_model=model_code,
                    enable_video_encrypt=True,
                )
                client.set_video_file_encrypt_key(
                    public_key_path=PUBLIC_KEY_PATH,
                    private_key_path=PRIVATE_KEY_PATH,
                )
                _clients[key] = client
    return _clients[key]


def _get_client_for_model(api_model):
    channel = api_model.channel
    return get_seedance_client(channel.base_url, channel.api_key, api_model.code)


@csrf_exempt
def video_generate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Bearer '):
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    from users.models import User
    try:
        user = User.objects.get(api_key=auth[7:], is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': {'message': 'Invalid JSON'}}, status=400)

    model_code = body.get('model', '').lower()
    api_model = ApiModel.objects.filter(code=model_code, status='enabled', task_type='video').select_related('channel').first()
    if not api_model:
        return JsonResponse({'error': {'message': f'Video model {model_code} not found', 'type': 'model_not_found'}}, status=404)

    content = body.get('content', [])
    if not content:
        return JsonResponse({'error': {'message': 'content is required'}}, status=400)

    for item in content:
        if isinstance(item, dict) and item.get('type') == 'text':
            text = item.get('text', '')
            if text:
                _, _, blocked = filter_instance.check(text)
                if blocked:
                    return JsonResponse({'error': {'message': 'Content blocked by policy'}}, status=403)

    cost = float(api_model.price) if api_model.bill_type != 'free' else 0
    if cost > 0 and user.balance < cost:
        return JsonResponse({'error': {'message': 'Insufficient balance'}}, status=402)

    request_data = {
        'content': content,
        'generate_audio': body.get('generate_audio', True),
        'ratio': body.get('ratio', '16:9'),
        'duration': body.get('duration', 11),
        'watermark': body.get('watermark', False),
    }

    client = _get_client_for_model(api_model)
    try:
        task_id = client.create_video_generation_task(request_data)
    except Exception as e:
        logger.error(f"Create video task failed: {e}")
        return JsonResponse({'error': {'message': f'Upstream error: {str(e)}'}}, status=502)

    if not task_id:
        return JsonResponse({'error': {'message': 'Video generation request rejected by upstream. Please verify your API Key has access to the model.'}}, status=403)

    if cost > 0:
        ok, _ = deduct_balance(user, cost, f'视频生成: {api_model.name}')
        if not ok:
            return JsonResponse({'error': {'message': 'Insufficient balance'}}, status=402)
    else:
        cost = 0

    prompt_text = ''
    for item in content:
        if isinstance(item, dict) and item.get('type') == 'text':
            prompt_text = item.get('text', '')
            break

    video_task = VideoTask.objects.create(
        user=user,
        api_model=api_model,
        remote_task_id=task_id,
        status='pending',
        prompt_text=prompt_text,
        request_data=request_data,
        cost=cost,
    )

    return JsonResponse({
        'task_id': task_id,
        'status': 'pending',
        'message': 'Task created successfully',
    })


@csrf_exempt
def video_query(request, task_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)

    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth.startswith('Bearer '):
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    from users.models import User
    try:
        user = User.objects.get(api_key=auth[7:], is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': {'message': 'Invalid API Key', 'type': 'invalid_api_key'}}, status=401)

    video_task = VideoTask.objects.filter(remote_task_id=task_id, user=user).select_related('api_model__channel').first()
    if not video_task or not video_task.api_model:
        return JsonResponse({'error': {'message': 'Task not found'}}, status=404)

    if video_task.status not in ('succeeded', 'failed'):
        client = _get_client_for_model(video_task.api_model)
        try:
            task_info = client.query_video_generation_task(task_id)
        except Exception as e:
            logger.error(f"Query video task failed: {e}")
            return JsonResponse({'task_id': task_id, 'status': video_task.status})

        remote_status = task_info.get('status', video_task.status)
        video_task.status = remote_status
        video_task.error_message = task_info.get('error', {}).get('message', '') if isinstance(task_info.get('error'), dict) else task_info.get('error', '')
        video_task.save(update_fields=['status', 'error_message', 'updated_at'])

        if remote_status == 'succeeded':
            video_url = task_info.get('content', {}).get('video_url', '')
            if video_url:
                video_task.video_url = video_url
                local_filename = f'{task_id}.mp4'
                local_path = os.path.join(settings.MEDIA_ROOT, 'videos', local_filename)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                try:
                    client.download_video(task_id, local_path)
                    video_task.local_path = f'media/videos/{local_filename}'
                except Exception as e:
                    logger.error(f"Download video failed: {e}")

                video_task.save(update_fields=['video_url', 'local_path', 'updated_at'])

    response = {
        'task_id': task_id,
        'status': video_task.status,
    }
    if video_task.status == 'succeeded' and video_task.local_path:
        response['video_url'] = video_task.local_path
    if video_task.status == 'failed':
        response['error'] = video_task.error_message or 'Unknown error'

    return JsonResponse(response)


def chat_video_poll(request, task_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    video_task = VideoTask.objects.filter(remote_task_id=task_id, user=request.user).select_related('api_model__channel').first()
    if not video_task or not video_task.api_model:
        return JsonResponse({'error': 'Task not found'}, status=404)

    if video_task.status not in ('succeeded', 'failed'):
        client = _get_client_for_model(video_task.api_model)
        try:
            task_info = client.query_video_generation_task(task_id)
        except Exception as e:
            logger.error(f"Query video task failed: {e}")
            return JsonResponse({'task_id': task_id, 'status': video_task.status})

        remote_status = task_info.get('status', video_task.status)
        video_task.status = remote_status
        video_task.error_message = task_info.get('error', {}).get('message', '') if isinstance(task_info.get('error'), dict) else task_info.get('error', '')
        video_task.save(update_fields=['status', 'error_message', 'updated_at'])

        if remote_status == 'succeeded':
            video_url = task_info.get('content', {}).get('video_url', '')
            if video_url:
                video_task.video_url = video_url
                local_filename = f'{task_id}.mp4'
                local_path = os.path.join(settings.MEDIA_ROOT, 'videos', local_filename)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                try:
                    client.download_video(task_id, local_path)
                    video_task.local_path = f'media/videos/{local_filename}'
                except Exception as e:
                    logger.error(f"Download video failed: {e}")

                video_task.save(update_fields=['video_url', 'local_path', 'updated_at'])

    return JsonResponse({
        'task_id': task_id,
        'status': video_task.status,
        'video_url': video_task.local_path or '',
        'error': video_task.error_message or '',
    })
