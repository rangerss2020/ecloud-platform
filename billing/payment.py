import hashlib
import json
import time
import uuid
import urllib.parse
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .models import RechargeOrder, SystemConfig


def get_config(key, default=''):
    return SystemConfig.get(key, default)


class AlipayGateway:
    """支付宝当面付 - Native扫码支付"""

    def get_params(self):
        return {
            'app_id': get_config('alipay_app_id', ''),
            'merchant_private_key': get_config('alipay_private_key', ''),
            'alipay_public_key': get_config('alipay_public_key', ''),
            'notify_url': get_config('alipay_notify_url', ''),
            'gateway': 'https://openapi.alipay.com/gateway.do',
        }

    def create_order(self, order):
        params = self.get_params()
        if not params['app_id']:
            return None, 'Alipay app_id not configured'

        biz_content = {
            'out_trade_no': order.order_no,
            'total_amount': str(order.amount),
            'subject': f'API平台充值{order.amount}元',
            'product_code': 'FACE_TO_FACE_PAYMENT',
        }

        sign_params = {
            'app_id': params['app_id'],
            'method': 'alipay.trade.precreate',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'notify_url': params['notify_url'],
            'biz_content': json.dumps(biz_content, ensure_ascii=False),
        }

        sign_params['sign'] = self._rsa_sign(sign_params, params['merchant_private_key'])

        try:
            resp = requests.post(params['gateway'], data=sign_params, timeout=15)
            result = resp.json()
            alipay_resp = result.get('alipay_trade_precreate_response', {})
            if alipay_resp.get('code') == '10000':
                return {'qr_code': alipay_resp.get('qr_code'), 'out_trade_no': order.order_no}, None
            return None, alipay_resp.get('sub_msg', 'Alipay API error')
        except Exception as e:
            return None, str(e)

    def verify_callback(self, data):
        params = self.get_params()
        sign = data.pop('sign', '')
        sign_type = data.pop('sign_type', 'RSA2')
        content = self._build_sign_str(data)
        return self._rsa_verify(content, sign, params['alipay_public_key'])

    def _rsa_sign(self, params, private_key):
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from Crypto.Hash import SHA256
        import base64
        content = self._build_sign_str(params)
        key = RSA.import_key(private_key)
        h = SHA256.new(content.encode('utf-8'))
        signer = PKCS1_v1_5.new(key)
        return base64.b64encode(signer.sign(h)).decode()

    def _rsa_verify(self, content, sign, public_key):
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from Crypto.Hash import SHA256
        import base64
        key = RSA.import_key(public_key)
        h = SHA256.new(content.encode('utf-8'))
        verifier = PKCS1_v1_5.new(key)
        return verifier.verify(h, base64.b64decode(sign))

    def _build_sign_str(self, params):
        sorted_items = sorted(params.items())
        return '&'.join(f'{k}={v}' for k, v in sorted_items)

    def _mock_sign(self, params):
        return 'MOCK_SIGN_' + hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


class WechatPayGateway:
    """微信Native支付"""

    def get_params(self):
        return {
            'app_id': get_config('wechat_app_id', ''),
            'mch_id': get_config('wechat_mch_id', ''),
            'api_key': get_config('wechat_api_key', ''),
            'notify_url': get_config('wechat_notify_url', ''),
            'gateway': 'https://api.mch.weixin.qq.com/pay/unifiedorder',
        }

    def create_order(self, order):
        params = self.get_params()
        if not params['app_id']:
            return None, 'Wechat app_id not configured'

        req_data = {
            'appid': params['app_id'],
            'mch_id': params['mch_id'],
            'nonce_str': uuid.uuid4().hex[:30],
            'body': f'API平台充值{order.amount}元',
            'out_trade_no': order.order_no,
            'total_fee': int(order.amount * Decimal(100)),
            'spbill_create_ip': '127.0.0.1',
            'notify_url': params['notify_url'],
            'trade_type': 'NATIVE',
        }
        req_data['sign'] = self._sign(req_data, params['api_key'])

        xml_body = '<xml>' + ''.join(f'<{k}>{v}</{k}>' for k, v in req_data.items()) + '</xml>'

        try:
            resp = requests.post(params['gateway'], data=xml_body.encode('utf-8'),
                                 headers={'Content-Type': 'application/xml'}, timeout=15)
            result = self._parse_xml(resp.text)
            if result.get('return_code') == 'SUCCESS' and result.get('result_code') == 'SUCCESS':
                return {'qr_code': result.get('code_url'), 'out_trade_no': order.order_no}, None
            return None, result.get('return_msg', 'Wechat API error')
        except Exception as e:
            return None, str(e)

    def verify_callback(self, data):
        params = self.get_params()
        sign = data.pop('sign', '')
        return self._sign(data, params['api_key']) == sign

    def _sign(self, data, api_key):
        sorted_items = sorted((k, v) for k, v in data.items() if v and k != 'sign')
        sign_str = '&'.join(f'{k}={v}' for k, v in sorted_items) + f'&key={api_key}'
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def _parse_xml(self, xml_str):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        return {child.tag: child.text for child in root}


class MockPaymentGateway:
    """模拟支付网关 - 测试用"""

    def create_order(self, order):
        mock_qr = f'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%23f5f5f5"/><text x="50" y="100" font-size="14">MOCK_PAY</text><text x="30" y="130" font-size="10">{order.order_no}</text></svg>'
        return {'qr_code': mock_qr, 'out_trade_no': order.order_no}, None

    def verify_callback(self, data):
        return True


def get_gateway(pay_method):
    mock_mode = get_config('pay_mock_mode', '0') == '1'
    if mock_mode:
        return MockPaymentGateway()
    if pay_method == 'alipay':
        return AlipayGateway()
    return WechatPayGateway()
