# ECloud API 管理平台 - 用户指南

> 一站式大模型 API 中转服务 | 分发 API Key | 计费管理 | 多模型接入

---

## 一、平台简介

ECloud 是一个大模型 API 中转平台，为您提供：

- **统一 API 入口**：一个 API Key 调用 21+ 大模型（DeepSeek / GLM / Qwen / Kimi / Llama 等）
- **自动计费**：按量消费，余额实时扣减，无需分别对接各模型厂商
- **API Key 管理**：自主申请/重置，秒级生效
- **安全管理**：敏感词过滤、调用日志、余额告警

### 调用架构

```
您的代码 ──Bearer Token──→  本平台  ──转发──→  移动云MaaS（底层模型）
                       自动计费+日志+过滤
```

---

## 二、快速开始

### 2.1 注册账号

访问平台 → 注册 → 选择"会员"身份。

### 2.2 获取 API Key

登录后 → 右上角菜单 → **API Key** → 点击"生成 API Key"。

> SecretKey 仅显示一次，请立即保存。

### 2.3 充值

进入 **计费** → **立即充值** → 选择金额和支付方式。

### 2.4 开始调用

```python
import requests

API_KEY = "你的API_KEY"

resp = requests.post(
    'http://127.0.0.1:8000/api/v1/deepseek-v3/',
    headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
    json={
        'model': 'deepseek-v3',
        'messages': [{'role': 'user', 'content': '你好，请介绍一下你自己'}]
    }
)
print(resp.json())
```

就这么简单——无需关心签名，只需一个 Bearer Token。

---

## 三、API 调用规范

### 3.1 鉴权方式

#### 方式一：Bearer Token（推荐）

```http
POST /api/v1/{model_code}/
Authorization: Bearer <你的API_KEY>
Content-Type: application/json
```

#### 方式二：HMAC 签名（兼容旧版）

如果需要 HMAC 签名调用，详见 [附录A](#附录a-hmac-签名调用方式)。

### 3.2 请求地址

```
http://127.0.0.1:8000/api/v1/{model_code}/
```

### 3.3 请求格式

所有模型统一使用 OpenAI 兼容格式：

```json
{
    "model": "模型名称",
    "messages": [
        {"role": "system", "content": "系统提示词（可选）"},
        {"role": "user", "content": "用户消息"}
    ],
    "max_tokens": 2048,
    "temperature": 0.6,
    "stream": false
}
```

### 3.4 响应格式

```json
{
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "模型回复内容",
                "role": "assistant"
            }
        }
    ],
    "usage": {
        "prompt_tokens": 15,
        "completion_tokens": 50,
        "total_tokens": 65
    }
}
```

| 状态码 | 说明 |
|--------|------|
| 200 | 调用成功 |
| 401 | API Key 无效 |
| 402 | 余额不足 |
| 403 | 内容被敏感词拦截 |

### 3.5 错误响应

```json
{
    "state": "ERROR",
    "errorCode": "INSUFFICIENT_BALANCE",
    "errorMessage": "余额不足，需要 0.004，当前余额 0.001"
}
```

---

## 四、可用模型列表

| model_code | 模型名称 | 计费 | 单价 |
|------------|----------|------|------|
| `deepseek-v4-pro` | DeepSeek-V4-Pro | 按量(M) | ¥0.02 |
| `deepseek-v4-flash` | DeepSeek-V4-Flash | 按量(M) | ¥0.01 |
| `deepseek-v3.2` | DeepSeek-V3.2 | 按量(M) | ¥0.008 |
| `deepseek-v3.1` | DeepSeek-V3.1 | 按量(M) | ¥0.006 |
| `deepseek-v3` | DeepSeek-V3 | 按量(M) | ¥0.004 |
| `deepseek-r1` | DeepSeek-R1 | 按量(M) | ¥0.008 |
| `deepseek-7b` | DeepSeek-7B | 按量(M) | ¥0.001 |
| `glm-4.6` | GLM-4.6 | 按量(M) | ¥0.015 |
| `glm-5` | GLM-5 | 按量(M) | ¥0.02 |
| `qwen3-235b` | Qwen3-235B | 按量(M) | ¥0.03 |
| `qwen3-32b` | Qwen3-32B | 按量(M) | ¥0.008 |
| `qwen-vl` | Qwen-VL | 按次 | ¥0.05 |
| `jiutian-qianyuan` | 九天-乾元 | 按量(M) | ¥0.003 |
| `jiutian-kunyu` | 九天-坤舆 | 按量(M) | ¥0.001 |
| `kimi-k2.6` | Kimi-K2.6 | 按量(M) | ¥0.02 |
| `llama-3.3` | Llama-3.3 | 按量(M) | ¥0.004 |
| `llama-3.2` | Llama-3.2 | 按量(M) | ¥0.002 |
| `llama-3.1` | Llama-3.1 | 按量(M) | ¥0.002 |
| `hunyuan` | 混元(腾讯) | 按量(M) | ¥0.005 |
| `wxyy` | 文心一言(百度) | 按量(M) | ¥0.005 |
| `embedding` | Embedding向量 | 按量(K) | ¥0.001 |

> 计费单位：M = 百万tokens，K = 千tokens

---

## 五、SDK 调用示例

### 5.1 Python

```python
import requests

API_KEY = "你的API_KEY"
BASE_URL = "http://127.0.0.1:8000"

def chat(model, messages, **kwargs):
    resp = requests.post(
        f'{BASE_URL}/api/v1/{model}/',
        headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': messages, **kwargs},
        timeout=60
    )
    if resp.status_code == 200:
        return resp.json()['choices'][0]['message']['content']
    raise Exception(f'调用失败 [{resp.status_code}]: {resp.text}')

# 使用示例
reply = chat('deepseek-v3', [
    {'role': 'user', 'content': '用Python写一个快速排序'}
])
print(reply)
```

### 5.2 cURL

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/deepseek-v3/" \
  -H "Authorization: Bearer 你的API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 5.3 JavaScript (Node.js)

```javascript
const API_KEY = '你的API_KEY';

async function chat(model, messages) {
    const resp = await fetch(`http://127.0.0.1:8000/api/v1/${model}/`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ model, messages })
    });
    const data = await resp.json();
    return data.choices[0].message.content;
}
```

---

## 六、计费说明

### 6.1 计费方式

| 类型 | 说明 | 示例 |
|------|------|------|
| 按量(M) | 每百万tokens计费 | DeepSeek-V3: ¥0.004/M |
| 按量(K) | 每千tokens计费 | Embedding: ¥0.001/K |
| 按次 | 每次调用计费 | Qwen-VL: ¥0.05/次 |

### 6.2 扣费规则

- 仅在调用**成功**时扣费
- 余额不足时返回 402 错误，不扣费
- 敏感词拦截不扣费
- 交易记录可在 **计费 → 交易记录** 查看

### 6.3 充值

进入 **计费 → 立即充值**，支持支付宝/微信。

---

## 七、敏感词过滤

平台内置敏感词过滤，处理级别：

| 级别 | 行为 |
|------|------|
| 拦截 | 请求直接拒绝（403），不扣费 |
| 替换 | 敏感词替换为 `***` 后继续转发 |
| 审核 | 记录命中但不拦截 |

---

## 八、Web 控制台

| 页面 | URL | 说明 |
|------|-----|------|
| 控制台 | `/` | 概览仪表盘 + 统计图表 |
| 对话 | `/gateway/chat/` | 在线选择模型直接对话 |
| 模型 | `/models/` | 浏览可用模型 |
| 网关 | `/gateway/` | API 调用测试 |
| 计费 | `/billing/` | 交易记录 + 充值 |
| API Key | `/users/apikey/` | 申请/查看/重置 |
| 个人设置 | `/users/profile/` | 修改密码/资料 |

---

## 九、常见问题

**Q: API Key 在哪里获取？**
A: 登录后 → 右上角菜单 → API Key → 生成。SecretKey 仅显示一次。

**Q: 如何查看消费明细？**
A: 计费 → 交易记录，或控制台查看调用日志。

**Q: 调用报 401 错误？**
A: 检查 Authorization 头是否以 `Bearer ` 开头，API Key 是否正确。

**Q: 调用报 402 错误？**
A: 余额不足，请充值后重试。

**Q: 支持哪些模型？**
A: 目前接入 21 个大模型，详见 [第四章](#四可用模型列表)，持续增加中。

**Q: 调用有频率限制吗？**
A: 目前无频率限制，仅按余额控制。

---

## 附录A：HMAC 签名调用方式

> 推荐使用 Bearer Token 方式（第三章），如确需 HMAC 签名：

### 公共参数

| 参数 | 说明 |
|------|------|
| `AccessKey` | 平台 API Key |
| `SignatureMethod` | HmacSHA1 / HmacSHA256 |
| `SignatureVersion` | 固定 V2.0 |
| `SignatureNonce` | 随机UUID |
| `Timestamp` | UTC时间 `2024-01-01T00:00:00Z` |
| `Signature` | 计算签名值 |

### Python 示例

```python
import requests, time, uuid, hmac, hashlib, urllib.parse

AK = "你的API_KEY"
SK = "你的SecretKey"

def percent_encode(s):
    res = urllib.parse.quote(str(s).encode('utf-8'), '')
    return res.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

def sign(method, params, path, sk):
    d = dict(params); d.pop('Signature', None)
    q = ''; [q := q + '&' + percent_encode(k) + '=' + percent_encode(d[k]) for k in sorted(d.keys())]
    s = f'{method}\n{percent_encode(path)}\n{hashlib.sha256(q[1:].encode()).hexdigest()}'
    return hmac.new(('BC_SIGNATURE&'+sk).encode(), s.encode(), hashlib.sha1).hexdigest()

path = '/api/v1/deepseek-v3/'
params = {
    'AccessKey': AK, 'SignatureMethod': 'HmacSHA1', 'SignatureVersion': 'V2.0',
    'SignatureNonce': str(uuid.uuid4()),
    'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
}
params['Signature'] = sign('POST', params, path, SK)

r = requests.post(f'http://127.0.0.1:8000{path}',
    params=params,
    json={'model': 'deepseek-v3', 'messages': [{'role': 'user', 'content': '你好'}]})
print(r.json())
```
