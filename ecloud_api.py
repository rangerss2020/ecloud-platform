import hmac
import uuid
import time
import hashlib
import urllib.parse
import requests
import json

def percent_encode(encode_str):
    encode_str = str(encode_str)
    res = urllib.parse.quote(encode_str.encode('utf-8'), '')
    res = res.replace('+', '%20')
    res = res.replace('*', '%2A')
    res = res.replace('%7E', '~')
    return res

def sign(http_method, params, servlet_path, secret_key, signature_method='HmacSHA1'):
    sign_params = dict(params)
    sign_params.pop('Signature', None)

    sorted_keys = sorted(sign_params.keys())
    canonicalized_query_string = ''
    for k in sorted_keys:
        canonicalized_query_string += '&' + percent_encode(k) + '=' + percent_encode(sign_params[k])

    sha256_hash = hashlib.sha256(canonicalized_query_string[1:].encode('utf-8')).hexdigest()
    string_to_sign = f"{http_method}\n{percent_encode(servlet_path)}\n{sha256_hash}"

    key = ("BC_SIGNATURE&" + secret_key).encode('utf-8')

    if signature_method == 'HmacSHA256':
        h = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha256)
    else:
        h = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1)

    return h.hexdigest()

def build_api_params(access_key, secret_key, signature_method='HmacSHA1'):
    if signature_method not in ('HmacSHA1', 'HmacSHA256'):
        signature_method = 'HmacSHA1'
    return {
        'AccessKey': access_key,
        'SignatureMethod': signature_method,
        'SignatureVersion': 'V2.0',
        'SignatureNonce': str(uuid.uuid4()),
        'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime()),
        'Signature': ''
    }

def call_ecloud_api(base_url, servlet_path, http_method, access_key, secret_key,
                    signature_method='HmacSHA1', body_data=None, extra_params=None,
                    headers=None, timeout=30):
    params = build_api_params(access_key, secret_key, signature_method)
    if extra_params:
        params.update(extra_params)

    signature = sign(http_method, params, servlet_path, secret_key, signature_method)
    params['Signature'] = signature

    url = base_url + servlet_path

    if headers is None:
        headers = {}
    headers.setdefault('Content-Type', 'application/json')

    start_time = time.time()

    if http_method.upper() == 'GET':
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    elif http_method.upper() == 'POST':
        resp = requests.post(url, params=params, json=body_data or {}, headers=headers, timeout=timeout)
    elif http_method.upper() == 'PUT':
        resp = requests.put(url, params=params, json=body_data or {}, headers=headers, timeout=timeout)
    elif http_method.upper() == 'DELETE':
        resp = requests.delete(url, params=params, headers=headers, timeout=timeout)
    else:
        resp = requests.request(http_method, url, params=params, json=body_data or {}, headers=headers, timeout=timeout)

    duration_ms = int((time.time() - start_time) * 1000)

    try:
        result = resp.json()
    except ValueError:
        result = {'body': resp.text, 'state': 'OK' if resp.ok else 'ERROR'}

    result['_duration_ms'] = duration_ms
    result['_status_code'] = resp.status_code
    return result


def call_bearer_api(base_url, servlet_path, http_method, api_key,
                    body_data=None, headers=None, timeout=30, stream=False):
    url = base_url + servlet_path

    if headers is None:
        headers = {}
    headers.setdefault('Content-Type', 'application/json')
    headers['Authorization'] = f'Bearer {api_key}'

    start_time = time.time()

    if http_method.upper() == 'GET':
        resp = requests.get(url, headers=headers, timeout=timeout)
    elif http_method.upper() == 'POST':
        resp = requests.post(url, json=body_data or {}, headers=headers, timeout=timeout)
    elif http_method.upper() == 'PUT':
        resp = requests.put(url, json=body_data or {}, headers=headers, timeout=timeout)
    elif http_method.upper() == 'DELETE':
        resp = requests.delete(url, headers=headers, timeout=timeout)
    else:
        resp = requests.request(http_method, url, json=body_data or {}, headers=headers, timeout=timeout)

    duration_ms = int((time.time() - start_time) * 1000)

    try:
        result = resp.json()
    except ValueError:
        result = {'body': resp.text, 'state': 'OK' if resp.ok else 'ERROR'}

    result['_duration_ms'] = duration_ms
    result['_status_code'] = resp.status_code
    return result
