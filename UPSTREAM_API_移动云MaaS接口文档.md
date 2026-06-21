# 移动云 API 调用说明文档

---

## 一、概述

移动云API开放平台提供可见即可用的API服务，支持快捷高效的云上接入。移动云产品的API通过云API网关开放，提供Access Key ID（AK）和Secret Access Key（SK）对称加密方式验证接口调用者身份。

### 1.1 认证方式

| 项目 | 说明 |
|---|---|
| **AK** (Access Key ID) | 访问密钥ID，用于标识访问者的身份 |
| **SK** (Secret Access Key) | 与AK结合使用的密钥，用于对请求签名字符串进行摘要加密 |

> **注意**：SK必须严格保密，只有移动云和用户知道。

### 1.2 获取AK/SK

登录移动云控制台，在【Access Key管理】模块自行申请和管理AK/SK。

---

## 二、签名机制

### 2.1 签名流程

移动云API服务会对每个访问的请求进行身份验证，无论使用HTTP还是HTTPS协议提交请求，都需要在请求中包含签名（Signature）信息。

#### 公共请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `Version` | string | 否 | 算法发布版本，默认2016-12-05 |
| `AccessKey` | string | 是 | 用户的accessKey |
| `Timestamp` | string | 是 | 发送请求的时间戳，距离当前时间不要超过5分钟 |
| `SignatureMethod` | string | 是 | 签名算法，支持HmacSHA1和HmacSHA256 |
| `SignatureVersion` | string | 是 | 签名版本，现行V2.0 |
| `SignatureNonce` | string | 是 | 随机生成的字符串，防重放攻击 |
| `Signature` | string | 是 | 签名值 |

#### 签名计算步骤

**第一步：构造规范化请求字符串（CanonicalizedQueryString）**

1. 参数排序：按参数名称字典顺序对所有请求参数排序（不包含Signature）
2. 参数编码：对排序后的参数名称和值分别用UTF-8进行URL编码
   - A-Z、a-z、0-9、"-"、"_"、"."、"~" 不编码
   - 其他字符编码为"%XY"格式
   - 空格编码为"%20"而非"+"
   - 标准库编码后需替换：`+`→`%20`，`*`→`%2A`，`%7E`→`~`
3. 连接参数：编码后的参数名称和值用"="连接
4. 拼接字符串：用"&"连接所有参数组合

**第二步：构造待签名字符串（StringToSign）**

```
StringToSign = HTTPMethod + "\n" + percentEncode(servletPath) + "\n" + sha256(CanonicalizedQueryString)
```

**第三步：计算签名**

```
Key = "BC_SIGNATURE&" + AccessKeySecret
Signature = HMAC(StringToSign, Key, SignatureMethod)
```

### 2.2 错误码

| 错误码 | 错误信息 | 说明 |
|---|---|---|
| `MISSING_PARAMETER` | Input parameter AccessKey missing | 缺少AccessKey参数 |
| `MISSING_PARAMETER` | Input parameter Timestamp missing | 缺少Timestamp参数 |
| `MISSING_PARAMETER` | Input parameter Signature missing | 缺少Signature参数 |
| `MISSING_PARAMETER` | Input parameter SignatureMethod missing | 缺少SignatureMethod参数 |
| `MISSING_PARAMETER` | Invalid parameter SignatureNonce | 缺少SignatureNonce参数 |
| `MISSING_PARAMETER` | Invalid parameter SignatureVersion | 缺少SignatureVersion参数 |
| `INVALID_PARAMETER` | Invalid parameter Timestamp | Timestamp格式错误或时间差超过10分钟 |

---

## 三、SDK调用方式（推荐）

### 3.1 Java SDK

#### 环境要求
- Java JDK 1.8及以上版本
- Maven

#### Maven配置

**设置移动云镜像仓库**（settings.xml）：

```xml
<mirror>
    <id>nexus-ecloud</id>
    <mirrorOf>*</mirrorOf>
    <name>Nexus ecloud</name>
    <url>https://ecloud.10086.cn/api/query/developer/nexus/repository/eCloudSDK/</url>
</mirror>
```

**引入SDK依赖**（pom.xml）：

```xml
<dependency>
    <groupId>com.ecloud.sdk</groupId>
    <artifactId>ecloud-sdk-tag</artifactId>
    <version>1.0.18</version>
</dependency>
```

#### 代码示例

```java
import com.ecloud.sdk.ApiException;
import com.ecloud.sdk.JSON;
import com.ecloud.sdk.config.Config;
import com.ecloud.sdk.tag.v1.Client;
import com.ecloud.sdk.tag.v1.model.QuerySystemTagListRequest;
import com.ecloud.sdk.tag.v1.model.QuerySystemTagListResponse;

public class QuerySystemTagListSample {

    private static Client createClient(String accessKey, String secretKey, String poolId) {
        Config config = new Config();
        config.setAccessKey(accessKey);
        config.setSecretKey(secretKey);
        config.setPoolId(poolId);
        return new Client(config);
    }

    public static void main(String[] args) throws ApiException {
        Client client = QuerySystemTagListSample.createClient("<YOUR AK>", "<YOUR SK>", "poolId");
        QuerySystemTagListRequest request = new QuerySystemTagListRequest();
        QuerySystemTagListResponse result = client.querySystemTagList(request);
        System.out.println(new JSON().getGson().toJson(result));
    }
}
```

#### 客户端配置

```java
Config config = new Config();

// 超时配置（可选）
config.setConnectTimeout(10);  // 连接超时，默认60秒
config.setReadTimeout(10);     // 响应超时，默认120秒

// 认证信息
config.setAccessKey(accessKey);
config.setSecretKey(secretKey);
config.setPoolId(poolId);      // 服务部署区域（资源池编号）

Client client = new Client(config);
```

### 3.2 Python SDK

#### 代码示例

```python
import uuid
import requests
import json
import hmac
from hashlib import sha1, sha256
import urllib.parse
import copy
import time

access_key = "<YOUR AK>"
secret_key = "<YOUR SK>"

def percent_encode(encode_str):
    encode_str = str(encode_str)
    res = urllib.parse.quote(encode_str.encode('utf-8'), '')
    res = res.replace('+', '%20')
    res = res.replace('*', '%2A')
    res = res.replace('%7E', '~')
    return res

def sign(http_method, params, servlet_path):
    time_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime())
    params['Timestamp'] = time_str
    parameters = copy.deepcopy(params)
    parameters.pop('Signature', None)
    sorted_parameters = sorted(parameters.items(), key=lambda x: x[0])
    
    canonicalized_query_string = ''
    for (k, v) in sorted_parameters:
        canonicalized_query_string += '&' + percent_encode(k) + '=' + percent_encode(v)
    
    string_to_sign = f"{http_method}\n{percent_encode(servlet_path)}\n{sha256(canonicalized_query_string[1:].encode('utf-8')).hexdigest()}"
    key = ("BC_SIGNATURE&" + secret_key).encode('utf-8')
    signature = hmac.new(key, string_to_sign.encode('utf-8'), sha1).hexdigest()
    return signature

if __name__ == '__main__':
    method = 'POST'
    url = "https://ecloud.10086.cn"
    path = '/api/v2/keypair'
    headers = {'Content-Type': 'application/json'}
    
    querystring = {
        "AccessKey": access_key,
        "Timestamp": "",
        "Signature": "",
        "SignatureMethod": "HmacSHA1",
        "SignatureNonce": "",
        "SignatureVersion": "V2.0"
    }
    
    querystring['SignatureNonce'] = str(uuid.uuid4())
    querystring['Signature'] = sign(method, querystring, path)
    
    response = requests.request(method, url + path, headers=headers, params=querystring, json={})
    print(json.dumps(response.json(), indent=4, ensure_ascii=False))
```

---

## 四、HTTP直接调用示例

### 4.1 解冻归档存储文件

**URL**：`PUT https://ecloud.10086.cn/api/v3/eos/{location}/object/restoreObject`

**请求头**：

| 参数 | 说明 |
|---|---|
| `eos_pool_id` | EOS资源池的唯一标识 |

**请求体**：

```json
{
    "bucketName": "bucket1",
    "key": "object1",
    "versionId": "H5qOTdRCTac.XlVtklREUJNXhhhQYEr"
}
```

**返回示例**（200 OK）：

```json
{
    "body": "true",
    "requestId": "reqId-05b3a066e88551fd21334-10ed790d-5",
    "state": "OK"
}
```

### 4.2 删除实例群组成员

**URL**：`POST https://ecloud.10086.cn/api/openapi-instance/v4/instance-group/unbind-instances`

**请求体**：

```json
{
    "groupId": "4ed219c8-4ef6-4d41-8711-d04651cafdf0",
    "instanceIds": [
        "c37945d7-0859-4c88-906b-0c49f79b64e0",
        "a3e664c3-f3cd-43ee-9f76-32476f218af2"
    ]
}
```

**返回示例**（200 OK）：

```json
{
    "requestId": "req-150f330d-2b38-4da8-9113-99992ded4601",
    "state": "OK",
    "body": {
        "batchResult": [
            {
                "instanceId": "c37945d7-0859-4c88-906b-0c49f79b64e0",
                "result": true,
                "message": ""
            },
            {
                "instanceId": "a3e664c3-f3cd-43ee-9f76-32476f218af2",
                "result": true,
                "message": ""
            }
        ]
    }
}
```

### 4.3 密钥绑定标签

**URL**：`POST https://ecloud.10086.cn/api/openapi-ecs/customer/v3/keypair/tags/bind`

**请求体**：

```json
{
    "keypairName": "testKeypair",
    "tags": [
        {
            "key": "testKey",
            "value": "testValue"
        }
    ]
}
```

**返回示例**（200 OK）：

```json
{
    "body": "",
    "requestId": "reqId-bbc8cd9eccbac18a2f62e-41d94183-1",
    "state": "OK"
}
```

---

## 五、响应结构说明

### 5.1 标准响应字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `body` | object/string | 请求成功时返回的数据 |
| `errorCode` | string | 统一错误码 |
| `errorMessage` | string | 页面国际化错误提示 |
| `errorParams` | string[] | 统一错误码的自定义参数 |
| `requestId` | string | 每个请求的序列号 |
| `state` | enum | 返回状态码：OK/ERROR/EXCEPTION/ALARM/FORBIDDEN |

### 5.2 状态码说明

| 状态码 | 说明 |
|---|---|
| `OK` | 返回正常 |
| `ERROR` | 返回错误 |
| `EXCEPTION` | 返回异常 |
| `ALARM` | 需要告警实现 |
| `FORBIDDEN` | 禁止访问 |

---

## 六、大模型API调用（MaaS）

### 6.1 概述

移动云一站式模型服务平台（MaaS）提供大模型API调用能力，支持智能体对话、文本生成等功能。支持**API Key**和**AK/SK**两种鉴权方式，支持流式和非流式响应。

### 6.2 前提条件

1. 登录移动云控制台，进入【AccessKey管理】获取AK/SK
2. 在MaaS平台创建个人智能体并发布
3. 获取智能体ID（agent_id）

### 6.3 智能体对话接口

#### 请求说明

| 请求地址 | `https://zhenze-huhehaote.cmecloud.cn/api/maas/agent/{agent_id}` |
|---|---|
| 请求方法 | POST |

#### 请求参数

**Header**

| 参数名称 | 类型 | 必填 | 示例值 | 说明 |
|---|---|---|---|---|
| Content-Type | string | 是 | application/json | 请求类型 |
| Accept | string | 是 | text/event-stream | 流式推理时使用 |
| Authorization | string | 是 | Bearer &lt;apikey&gt; | API Key鉴权时使用 |

**Path**

| 参数名称 | 类型 | 必填 | 示例值 | 说明 |
|---|---|---|---|---|
| agent_id | string | 是 | agent_1297862150388744192 | 智能体ID |

**Body**

| 参数名称 | 类型 | 必填 | 示例值 | 说明 |
|---|---|---|---|---|
| chatId | string | 否 | chat-a3549d55-1377-408a-aac1-17011c1e0 | 对话ID，继续历史对话时传入 |
| query | string | 是 | 你好 | 本轮对话请求内容 |
| stream | bool | 是 | true | 流式开关 |
| input | object | 否 | {"arg1": 111} | 输入参数 |
| fileIds | list | 否 | ["file_1359996735595192320"] | 文件ID列表 |
| append | bool | 否 | true | 是否流式追加 |

#### 返回参数

| 参数名称 | 类型 | 说明 |
|---|---|---|
| chatId | string | 对话ID |
| messageId | string | 消息ID |
| createdTime | long | 时间戳（毫秒） |
| answer | string | 智能体回答内容 |
| segments | list | 知识库召回段落 |
| - text | string | 分段内容 |
| - fileName | string | 来源文件名 |
| - score | double | 分段得分 |
| sqlResults | list | SQL检索结果 |
| toolExecutionInfos | list | 工具执行结果 |
| agentId | string | 智能体ID |
| finishReason | string | 结束原因，stop表示结束 |
| usage | object | Token用量统计 |
| - prompt_tokens | int | 用户输入token数 |
| - completion_tokens | int | 模型生成token数 |
| - total_tokens | int | 总token数 |

#### 错误码

| HTTP状态码 | 错误码 | 说明 |
|---|---|---|
| 400 | InvalidParameter | 请求包含无效参数 |
| 401 | 未经授权错误 | 检查accessKey、secretKey或apiKey |
| 404 | NotFound | 请求地址错误/model not found |
| 405 | 调用方式错误 | stream为true时需设置Accept:text/event-stream |
| 500 | 当前服务异常，请稍后再试 | 服务异常 |

### 6.4 API Key调用示例

#### Python示例（API Key鉴权）

```python
import requests
import json

api_key = "<YOUR_API_KEY>"
agent_id = "<YOUR_AGENT_ID>"

url = f"https://zhenze-huhehaote.cmecloud.cn/api/maas/agent/{agent_id}"

headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'Authorization': f'Bearer {api_key}'
}

data = {
    "chatId": "",  # 首次对话为空，后续传入返回的chatId
    "query": "你好，你可以提供哪些AI能力？",
    "stream": True
}

response = requests.post(url, headers=headers, json=data, stream=True)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

#### cURL示例（API Key鉴权）

```bash
curl -X POST 'https://zhenze-huhehaote.cmecloud.cn/api/maas/agent/agent_1332004683745542144' \
--header 'Accept: text/event-stream' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <apikey>' \
--data '{
    "chatId": "chat-f1e8afc9-1fbe-4349-aa42-769f1bc5067a",
    "query": "你好，你可以提供哪些AI能力？",
    "stream": true
}'
```

### 6.5 AK/SK调用示例

#### Python示例（AK/SK鉴权）

```python
# coding: utf-8
import requests
from ecloudsdkcore.auth.credential import Credential, CredentialType
from ecloudsdkcore.auth.credential_impl import CredentialFactory
from ecloudsdkcore.request.http_request import HttpRequest

user_access_key = '<YOUR_ACCESS_KEY>'
user_secret_key = '<YOUR_SECRET_KEY>'
agent_id = '<YOUR_AGENT_ID>'

credential = Credential(
    access_key=user_access_key,
    secret_key=user_secret_key,
    credential_type=CredentialType.ECLOUD_AKSK
)
http_request = HttpRequest(url='https://ecloud.10086.cn', path=f'/api/maas/agent/{agent_id}')

CredentialFactory.get_credential_manager(credential.credential_type).sign(http_request, credential)
http_request.build_final_url()

headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
}

data = {
    "chatId": "",
    "query": "你好！",
    "stream": True,
}

try:
    response = requests.post(http_request.url, headers=headers, json=data, stream=True)
    response.raise_for_status()
    print(f"response status: {response.status_code}")
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            print(decoded_line)

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
```

#### SDK安装

```bash
pip install ecloudsdkcore==1.0.4 -i https://ecloud.10086.cn/api/query/developer/nexus/repository/python-sdk/simple
```

### 6.6 流式响应说明

流式响应采用SSE（Server-Sent Events）格式，不同event类型含义如下：

| event类型 | 说明 |
|---|---|
| THINKING | 模型进行深度思考的内容（Deepseek-R1系列模型） |
| ANSWER | 模型回答用户问题的正式内容 |

**响应示例**：

```
event:ANSWER
data:{"chatId":"fdc2d0f4-5e4d-4d43-9352-111480154efd","messageId":"62c39b62-49ad-414c-86a7-1a5256ca2c31","createdTime":1733129065436,"answer":"我是云","agentId":"agent_1297862150388744192","finishReason":null,"usage":null}

event:ANSWER
data:{"chatId":"fdc2d0f4-5e4d-4d43-9352-111480154efd","messageId":"62c39b62-49ad-414c-86a7-1a5256ca2c31","createdTime":1733129068044,"answer":"我是云电脑知识助手...","agentId":"agent_1297862150388744192","finishReason":"stop","usage":{"prompt_tokens":516,"completion_tokens":55,"total_tokens":571}}
```

### 6.7 注意事项

1. 智能体API调用**不允许非流式模式**（stream必须为true）
2. 主账号和子账号都必须使用**主账号的AK/SK**
3. 智能体必须**发布**后才能通过API调用
4. 使用流式响应时，请求头必须设置`Accept: text/event-stream`
5. 对话时支持传入文件，通过fileIds参数指定文件列表

### 6.8 模型API调用（文本模型）

#### 支持的模型

移动云一站式模型服务平台（MaaS）支持多种大模型，包括自研模型和第三方模型：

##### 一、自研模型 - 九天大模型（JIUTIAN）

| 模型名称 | 说明 |
|---|---|
| jiutian-qianyuan | 旗舰版，效果好 |
| jiutian-kunyu | 通用版，性价比高 |
| jiutian-xunfei | 语音融合版 |

##### 二、GLM系列（智谱AI）

| 模型名称 | 上下文长度 | 最大输入长度 | 最大回复长度 | API调用地址 |
|---|---|---|---|---|
| glm-4.6 | 200k | 100k | 100k | https://zhenze-huhehaote.cmecloud.cn/v1/chat/completions |
| glm-5 | 200k | -- | -- | https://zhenze-huabei.cmecloud.cn/v1/chat/completions |

##### 三、DeepSeek系列

| 模型名称 | 上下文长度 | 最大输入长度 | 最大输出长度 | 说明 |
|---|---|---|---|---|
| DeepSeek-V4-Pro | 1M | 1M | 128K | 高性能版本 |
| DeepSeek-V4-Flash | 1M | 1M | 128K | 快速版本 |
| DeepSeek-V3.2 | 160K | 128K | 32K | V3系列升级版 |
| DeepSeek-V3.1 | 128K | 96K | 32K | V3系列 |
| DeepSeek-V3 | 128K | 128K | 64K | V3基础版 |
| DeepSeek-R1 | 128K | 96K | 32K | 深度思考模型 |
| DeepSeek-V1/V2 | -- | -- | -- | 经典版本 |
| DeepSeek-7B/14B | -- | -- | -- | 高效蒸馏小模型 |

##### 四、Qwen系列（通义千问）

| 模型名称 | 说明 |
|---|---|
| Qwen3-235B-A22B | 大参数版本 |
| Qwen3-32B | 中等参数版本 |
| Qwen2系列 | 全尺寸系列 |
| Qwen-VL | 视觉语言模型 |

##### 五、其他第三方模型

| 模型名称 | 提供商 | 说明 |
|---|---|---|
| Kimi-K2.6 | MiniMax | 长上下文模型（256K） |
| Llama 3.1/3.2/3.3 | Meta | 开源模型全系列 |
| 混元 | 腾讯 | 腾讯自研模型 |
| 文心一言 | 百度 | 百度自研模型 |

##### 六、语音模型

| 模型名称 | 说明 |
|---|---|
| paraformer | 语音识别模型 |
| Sensevoice | 语音模型 |

##### 七、向量模型（Embedding）

| 模型名称 | 说明 |
|---|---|
| embedding模型 | 文本向量化 |

##### 八、视觉模型

| 模型名称 | 说明 |
|---|---|
| Qwen-VL | 视觉语言模型 |

#### 请求说明

| 请求地址 | `https://zhenze-huhehaote.cmecloud.cn/v1/chat/completions` |
|---|---|
| 请求方法 | POST |

#### 请求头

| 参数名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| Authorization | string | 是 | Bearer &lt;API_KEY&gt; |
| Content-Type | string | 是 | application/json |

#### 请求参数

| 名称 | 类型 | 必选 | 默认值 | 描述 |
|---|---|---|---|---|
| model | String | 是 | - | 模型名称，如glm-4-32b-0414 |
| messages | Array | 是 | - | 用户输入指令，支持多轮对话 |
| max_tokens | Int | 否 | 2048 | 允许推理生成的最大token个数 |
| temperature | Float | 否 | 0.6 | 温度系数，值越大随机性越强 |
| top_p | Float | 否 | 0.9 | top_p采样，控制词汇选择范围 |
| top_k | Int | 否 | 1 | top_k采样，限制候选词数量 |
| presence_penalty | Float | 否 | 0 | 存在惩罚，减少重复词汇 |
| frequency_penalty | Float | 否 | 0 | 频率惩罚，减少高频词汇 |
| seed | Int | 否 | - | 随机种子，控制结果可复现性 |
| stop | List/String | 否 | null | 推理停止标识 |
| stream | Boolean | 否 | false | 流式推理开关 |

#### messages参数格式

```json
[
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你是谁"},
    {"role": "assistant", "content": "我是AI助手"},
    {"role": "user", "content": "你能做什么"}
]
```

| role取值 | 说明 |
|---|---|
| system | 系统消息，仅在messages[0]中允许 |
| user | 用户提问 |
| assistant | 模型回答 |

#### 返回参数

| 名称 | 类型 | 描述 |
|---|---|---|
| choices | Array | 模型返回结果列表 |
| - finish_reason | String | 生成终止原因，stop表示终止 |
| - index | Int | 第几个choice |
| - message | Object | 生成结果 |
| -- content | String | 生成的回答语句 |
| -- role | String | 角色，assistant |
| object | String | 模型类，chat.completion |
| usage | Object | Token计数信息 |
| - prompt_tokens | Int | 输入token数量 |
| - completion_tokens | Int | 输出token数量 |
| - total_tokens | Int | 总token数量 |
| prefill_time | float | 流式推理首次token时延（毫秒） |

#### Python代码示例（GLM模型）

```python
import requests

url = "https://zhenze-huhehaote.cmecloud.cn/v1/chat/completions"
api_key = "<API_KEY>"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "model": "glm-4-32b-0414",
    "messages": [
        {"role": "user", "content": "你是谁"},
        {"role": "system", "content": ""}
    ],
    "max_tokens": 16384,
    "stream": True,
    "temperature": 0.7,
    "top_p": 0.9
}

response = requests.post(url, headers=headers, json=data, stream=True)

if response.status_code == 200:
    for line in response.iter_lines():
        if line:
            print(line.decode('utf-8'))
else:
    print(f"请求失败，状态码: {response.status_code}")
    print(response.text)
```

#### Java代码示例（GLM模型）

```java
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONObject;
import org.json.JSONArray;

public class StreamApiRequest {
    public static void main(String[] args) {
        String apiUrl = "https://zhenze-huhehaote.cmecloud.cn/v1/chat/completions";
        String apiKey = "<your API-KEY>";

        try {
            URL url = new URL(apiUrl);
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Authorization", "Bearer " + apiKey);
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setDoOutput(true);

            JSONObject requestBody = new JSONObject();
            requestBody.put("model", "glm-4-32b-0414");

            JSONObject systemMessage = new JSONObject();
            systemMessage.put("role", "system");
            systemMessage.put("content", "");

            JSONObject message = new JSONObject();
            message.put("role", "user");
            message.put("content", "你好");

            JSONArray messagesArray = new JSONArray();
            messagesArray.put(systemMessage);
            messagesArray.put(message);
            requestBody.put("messages", messagesArray);

            requestBody.put("max_tokens", 16384);
            requestBody.put("temperature", 0.7);
            requestBody.put("stream", true);
            requestBody.put("top_p", 0.9);

            try (OutputStream os = connection.getOutputStream()) {
                byte[] input = requestBody.toString().getBytes("utf-8");
                os.write(input, 0, input.length);
            }

            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), "UTF-8"));

            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.isEmpty()) {
                    System.out.println(line);
                }
            }

            reader.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

#### Golang代码示例（GLM模型）

```go
package main

import (
    "fmt"
    "strings"
    "net/http"
    "io"
)

func main() {
    url := "https://zhenze-huhehaote.cmecloud.cn/v1/chat/completions"
    apiKey := "<your API-KEY>"
    method := "POST"

    payload := strings.NewReader(`{
        "model": "glm-4-32b-0414",
        "messages": [
            {"role": "user", "content": "你是谁"},
            {"role": "system", "content": ""}
        ],
        "max_tokens": 16384,
        "stream": true,
        "temperature": 0.7,
        "top_p": 0.9
    }`)

    client := &http.Client{}

    req, err := http.NewRequest(method, url, payload)
    if err != nil {
        fmt.Println(err)
        return
    }

    req.Header.Add("Authorization", "Bearer "+apiKey)
    req.Header.Add("Content-Type", "application/json")

    res, err := client.Do(req)
    if err != nil {
        fmt.Println(err)
        return
    }
    defer res.Body.Close()

    body, err := io.ReadAll(res.Body)
    if err != nil {
        fmt.Println(err)
        return
    }

    fmt.Println(string(body))
}
```

### 6.9 API调用分类总览

| 分类 | 说明 | 接口类型 |
|---|---|---|
| 智能体API调用 | 与指定智能体进行对话 | POST /api/maas/agent/{agent_id} |
| 工作流API调用 | 工作流相关接口 | - |
| 模型API调用 | 直接调用大模型 | POST /v1/chat/completions |
| 文本模型API调用 | DeepSeek等文本模型 | - |
| 视觉模型API调用 | 视觉识别相关模型 | - |
| 向量模型API调用 | Embedding向量模型 | - |
| 语音模型API调用 | 语音识别模型（如paraformer） | - |
| 排序模型API调用 | 排序相关模型 | - |

---

## 七、参考资源

| 资源 | 链接 |
|---|---|
| API开放平台 | https://ecloud.10086.cn/op-oneapi-static/#/overview |
| SDK中心 | https://ecloud.10086.cn/op-oneapi-static/#/center/sdk |
| 签名机制文档 | https://ecloud.10086.cn/op-help-center/doc/article/24283 |
| 鉴权方式文档 | https://ecloud.10086.cn/op-help-center/doc/article/41967 |
| Java SDK | https://gitee.com/chinamobile_ecloud/eloud-sdk-java |
| 资源池编号 | https://ecloud.10086.cn/op-help-center/doc/article/54462 |
| 地域和访问域名 | https://ecloud.10086.cn/op-help-center/doc/article/48082 |
| 大模型API详情 | http://console.ecloud.10086.cn/op-help-center/doc/article/88743 |
| AK/SK调用示例 | http://console.ecloud.10086.cn/op-help-center/doc/article/88742 |
