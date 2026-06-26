import hmac
import hashlib
import urllib.parse
import time


def percent_encode(encode_str):
    encode_str = str(encode_str)
    res = urllib.parse.quote(encode_str.encode('utf-8'), '')
    res = res.replace('+', '%20')
    res = res.replace('*', '%2A')
    res = res.replace('%7E', '~')
    return res


def verify_user_signature(request):
    access_key = request.GET.get('AccessKey', '') or request.POST.get('AccessKey', '')
    signature = request.GET.get('Signature', '') or request.POST.get('Signature', '')
    timestamp = request.GET.get('Timestamp', '') or request.POST.get('Timestamp', '')
    nonce = request.GET.get('SignatureNonce', '') or request.POST.get('SignatureNonce', '')
    sig_method = request.GET.get('SignatureMethod', 'HmacSHA1')

    if not all([access_key, signature, timestamp, nonce]):
        return None, 'MISSING_PARAMETER', 'Missing signature parameters'

    try:
        ts = time.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        ts_seconds = time.mktime(ts)
        now = time.time()
        if abs(now - ts_seconds) > 600:
            return None, 'INVALID_PARAMETER', 'Timestamp expired (>10 min)'
    except ValueError:
        return None, 'INVALID_PARAMETER', 'Invalid Timestamp format'

    from users.models import User
    try:
        user = User.objects.get(api_key=access_key)
    except User.DoesNotExist:
        return None, 'INVALID_ACCESSKEY', 'Invalid AccessKey'

    if not user.is_active or not user.api_secret:
        return None, 'INVALID_ACCESSKEY', 'AccessKey not active'

    params = {}
    for key in request.GET.keys():
        params[key] = request.GET.get(key)
    for key in request.POST.keys():
        params[key] = request.POST.get(key)

    sign_params = dict(params)
    sign_params.pop('Signature', None)

    sorted_keys = sorted(sign_params.keys())
    canonicalized = ''
    for k in sorted_keys:
        canonicalized += '&' + percent_encode(k) + '=' + percent_encode(sign_params[k])

    sha256_hash = hashlib.sha256(canonicalized[1:].encode('utf-8')).hexdigest()
    string_to_sign = f"{request.method}\n{percent_encode(request.path)}\n{sha256_hash}"

    key = ("BC_SIGNATURE&" + user.api_secret).encode('utf-8')

    if sig_method == 'HmacSHA256':
        h = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha256)
    else:
        h = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1)

    if h.hexdigest() != signature:
        return None, 'SIGNATURE_ERROR', 'Signature mismatch'

    return user, None, None


def verify_user_apikey(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None, 'MISSING_PARAMETER', 'Missing Authorization header'

    token = auth_header[7:]
    if not token:
        return None, 'INVALID_ACCESSKEY', 'Empty API Key'

    from users.models import User
    try:
        user = User.objects.get(api_key=token, is_active=True)
    except User.DoesNotExist:
        return None, 'INVALID_ACCESSKEY', 'Invalid API Key'

    return user, None, None
