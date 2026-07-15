# API.md —— 同学前端对接接口文档

> **目标读者**: 把工作流 B 汇总成 APP 的前端 / 客户端开发者
> **协议**: HTTP + JSON(SSE 流式可选)
> **默认端口**: 5000
> **基础 URL**: `http://<host>:5000`

---

## 一、核心接口一览

| 方法 | 路径 | 用途 | 推荐场景 |
|------|------|------|----------|
| `POST` | `/async_run` | **异步执行**(推荐) | 生产环境,提交后轮询 |
| `GET`  | `/task/{task_id}` | 查询异步任务状态 | 配合 `/async_run` |
| `POST` | `/run` | **同步执行** | 测试 / 调试 / 短任务 |
| `POST` | `/stream_run` | **SSE 流式执行** | 实时显示中间步骤 |
| `POST` | `/cancel/{run_id}` | 取消运行中的任务 | 用户主动取消 |
| `POST` | `/node_run/{node_id}` | 单节点执行 | 调试单个节点 |
| `POST` | `/v1/chat/completions` | OpenAI 兼容接口 | 第三方工具对接 |
| `GET`  | `/health` | 健康检查 | 监控 / 探活 |
| `GET`  | `/graph_parameter` | 图入参出参定义 | 动态生成表单 |

**超时**: 同步接口默认 900 秒(15 分钟),长音频翻译可能不够,推荐用 `/async_run`。

---

## 二、图入参出参(GraphParameter)

### 入参 (`GraphInput`)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `media_file` | `File` | 条件必填 | 原始音视频(模式一)。`File` 结构:`{ url: string, file_type: "audio"\|"video"\|"document" }` |
| `finalized_excel` | `File` | 条件必填 | 定稿 Excel(模式二)。`File` 结构同上 |
| `original_audio_url` | `string` | 否 | 原始音频 URL。模式二专用,优先于 Supabase 缓存 |
| `run_mode` | `string` | 否 | `"预处理・生成待审校Excel"` \| `"回填・生成成品音视频"`,**不传则系统自动判断** |

**模式自动判断逻辑**:
- 有 `finalized_excel` → 模式二(回填)
- 有 `media_file` → 模式一(预处理)
- 都没有 → 报错

### 出参 (`GraphOutput`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `excel_url` | `string` | 生成的待审校 Excel URL(模式一才有) |
| `final_media_url` | `string` | 成品音视频 URL(模式二才有) |
| `qr_code_url` | `string` | 音频播放二维码图片 URL(模式二才有) |
| `message` | `string` | 提示消息 |
| `run_id` | `string` | 本次运行的唯一 ID(由 `/run` 路径自动附加) |

---

## 三、典型调用示例

### 3.1 模式一:音频 → 待审校 Excel

**请求**:
```bash
curl -X POST http://localhost:5000/async_run \
  -H "Content-Type: application/json" \
  -d '{
    "media_file": {
      "url": "https://your-bucket.s3.com/uploads/test.mp3",
      "file_type": "audio"
    }
  }'
```

**响应(立即返回)**:
```json
{
  "task_id": "a1b2c3d4e5f6...",
  "run_id": "a1b2c3d4e5f6...",
  "status": "pending"
}
```

**轮询任务**:
```bash
curl http://localhost:5000/task/a1b2c3d4e5f6
```

**轮询响应(进行中)**:
```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "running",
  "progress": "batch_translation",
  "result": null
}
```

**轮询响应(完成)**:
```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "success",
  "result": {
    "excel_url": "https://your-bucket.s3.com/outputs/excel_xxx.xlsx",
    "final_media_url": null,
    "qr_code_url": null,
    "message": "模式一执行完成,已生成待审校 Excel,审校后请再次上传触发模式二",
    "run_id": "a1b2c3d4e5f6"
  }
}
```

### 3.2 模式二:Excel → 成品音视频 + 二维码

**请求**:
```bash
curl -X POST http://localhost:5000/async_run \
  -H "Content-Type: application/json" \
  -d '{
    "finalized_excel": {
      "url": "https://your-bucket.s3.com/uploads/finalized.xlsx",
      "file_type": "document"
    },
    "original_audio_url": "https://your-bucket.s3.com/uploads/original.mp3"
  }'
```

> **如果 `original_audio_url` 留空**: 系统会自动从 Supabase 查询最近一次模式一保存的音频 URL。

**完成响应**:
```json
{
  "task_id": "...",
  "status": "success",
  "result": {
    "excel_url": null,
    "final_media_url": "https://your-bucket.s3.com/outputs/final_xxx.mp4",
    "qr_code_url": "https://your-bucket.s3.com/outputs/qr_xxx.png",
    "message": "模式二执行完成,已生成成品音视频和二维码",
    "run_id": "..."
  }
}
```

### 3.3 同步调用(短任务 / 测试)

```bash
curl -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -H "x-run-id: my-custom-run-id-001" \
  -d '{
    "media_file": {
      "url": "https://example.com/test.mp3",
      "file_type": "audio"
    }
  }'
```

> 默认超时 900 秒,长音频可能超时 → 推荐用 `/async_run`。
> `x-run-id` header 可选,用于自定义 run_id(方便后续 cancel)。

### 3.4 SSE 流式调用(实时显示中间步骤)

```bash
curl -X POST http://localhost:5000/stream_run \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "media_file": {
      "url": "https://example.com/test.mp3",
      "file_type": "audio"
    }
  }'
```

**SSE 事件流**:
```
id: 1
event: message
data: {"node": "auto_mode_judge", "status": "started", "ts": "..."}

id: 2
event: message
data: {"node": "asr_recognition", "status": "completed", "result": {...}, "ts": "..."}

id: 3
event: message
data: {"node": "batch_translation", "status": "started", "ts": "..."}

...

id: 10
event: message
data: {"node": "end_mode1", "status": "completed", "result": {"excel_url": "..."}, "ts": "..."}
```

### 3.5 取消任务

```bash
curl -X POST http://localhost:5000/cancel/my-custom-run-id-001
```

**响应**:
```json
{
  "status": "success",
  "run_id": "my-custom-run-id-001",
  "message": "Cancellation signal sent, task will be cancelled at next await point"
}
```

### 3.6 健康检查

```bash
curl http://localhost:5000/health
```

**响应**:
```json
{
  "status": "ok",
  "message": "Service is running"
}
```

### 3.7 获取图入参出参 Schema

```bash
curl http://localhost:5000/graph_parameter
```

**响应**(动态生成表单用):
```json
{
  "input": {
    "media_file": {"type": "File", "required": false, "description": "..."},
    "finalized_excel": {"type": "File", "required": false, "description": "..."},
    ...
  },
  "output": {
    "excel_url": {"type": "string", "description": "..."},
    "final_media_url": {"type": "string", "description": "..."},
    ...
  }
}
```

---

## 四、APP 集成示例(伪代码)

### 4.1 Web 前端(JavaScript)

```javascript
// 模式一:上传音频
async function translateAudio(audioFile) {
  // 1. 上传音频到对象存储,获取 URL
  const audioUrl = await uploadToS3(audioFile);

  // 2. 提交任务
  const submitRes = await fetch('http://localhost:5000/async_run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      media_file: { url: audioUrl, file_type: 'audio' }
    })
  });
  const { task_id } = await submitRes.json();

  // 3. 轮询任务状态
  while (true) {
    await sleep(2000);
    const statusRes = await fetch(`http://localhost:5000/task/${task_id}`);
    const status = await statusRes.json();

    if (status.status === 'success') {
      // 4. 返回 Excel URL 给用户下载
      window.location.href = status.result.excel_url;
      break;
    } else if (status.status === 'failed') {
      alert('翻译失败: ' + status.error);
      break;
    }
  }
}

// 模式二:上传已审校 Excel
async function generateFinalMedia(excelFile) {
  const excelUrl = await uploadToS3(excelFile);

  const submitRes = await fetch('http://localhost:5000/async_run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      finalized_excel: { url: excelUrl, file_type: 'document' }
      // original_audio_url 留空,系统自动从 Supabase 查
    })
  });
  const { task_id } = await submitRes.json();

  // 轮询逻辑同上...
  // 最终返回: { final_media_url, qr_code_url }
}
```

### 4.2 移动 APP(iOS Swift 示例)

```swift
func translateAudio(audioURL: String, completion: @escaping (String?) -> Void) {
    // 1. 提交任务
    let url = URL(string: "http://localhost:5000/async_run")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")

    let body: [String: Any] = [
        "media_file": [
            "url": audioURL,
            "file_type": "audio"
        ]
    ]
    request.httpBody = try? JSONSerialization.data(withJSONObject: body)

    URLSession.shared.dataTask(with: request) { data, response, error in
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let taskId = json["task_id"] as? String else {
            completion(nil)
            return
        }

        // 2. 轮询
        self.pollTask(taskId: taskId, completion: completion)
    }.resume()
}

func pollTask(taskId: String, completion: @escaping (String?) -> Void) {
    let url = URL(string: "http://localhost:5000/task/\(taskId)")!
    URLSession.shared.dataTask(with: url) { data, response, error in
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                self.pollTask(taskId: taskId, completion: completion)
            }
            return
        }

        let status = json["status"] as? String
        if status == "success" {
            if let result = json["result"] as? [String: Any],
               let excelURL = result["excel_url"] as? String {
                completion(excelURL)
            } else {
                completion(nil)
            }
        } else if status == "failed" {
            completion(nil)
        } else {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                self.pollTask(taskId: taskId, completion: completion)
            }
        }
    }.resume()
}
```

### 4.3 小程序(微信示例)

```javascript
// miniprogram/utils/api.js
const API_BASE = 'http://your-server:5000';

function translateAudio(audioUrl) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE}/async_run`,
      method: 'POST',
      data: {
        media_file: { url: audioUrl, file_type: 'audio' }
      },
      success: (res) => {
        if (res.statusCode === 200) {
          pollTask(res.data.task_id, resolve, reject);
        } else {
          reject(new Error('提交失败'));
        }
      },
      fail: reject
    });
  });
}

function pollTask(taskId, resolve, reject) {
  wx.request({
    url: `${API_BASE}/task/${taskId}`,
    success: (res) => {
      if (res.data.status === 'success') {
        resolve(res.data.result);
      } else if (res.data.status === 'failed') {
        reject(new Error(res.data.error));
      } else {
        setTimeout(() => pollTask(taskId, resolve, reject), 2000);
      }
    },
    fail: reject
  });
}

module.exports = { translateAudio };
```

---

## 五、状态码与错误处理

### 5.1 HTTP 状态码

| 状态码 | 含义 | 处理建议 |
|--------|------|----------|
| `200` | 成功 | - |
| `400` | 请求 JSON 格式错误 | 检查请求体 |
| `404` | task_id 不存在 | 检查 ID 是否正确 |
| `500` | 工作流执行错误 | 查看 `error_code` 与 `error_message` |
| `503` | 异步任务存储不可用 | 重试 |

### 5.2 业务错误码

| error_code | 含义 | 解决方案 |
|------------|------|----------|
| `4404` | TTS QPS 限流 | 已自动重试 3 次,用户无感 |
| `429` | TTS 限流(同类) | 已自动重试 3 次 |
| `4036` | TTS 月度配额耗尽 | 等下月刷新 / 升级 plan |
| `INVALID_INPUT` | 入参错误 | 检查请求字段 |
| `TASK_TIMEOUT` | 任务执行超时(>15min) | 用 `/async_run` 异步执行 |
| `LLM_ERROR` | LLM 调用失败 | 重试或检查凭据 |
| `ASR_ERROR` | ASR 识别失败 | 检查音频 URL 是否可访问 |

### 5.3 错误响应示例

```json
{
  "error_code": "TTS_QUOTA_EXCEEDED",
  "error_message": "TTS 月度配额已用尽 (code=4036),请等下月刷新或升级 plan",
  "stack_trace": "..."
}
```

---

## 六、性能与限制

| 维度 | 限制 | 备注 |
|------|------|------|
| 同步接口超时 | 900 秒(15 分钟) | 长音频翻译建议用 `/async_run` |
| 异步任务并发 | 由后端控制 | 默认无显式限制 |
| 音频大小 | ASR 客户端限制 | 建议 < 100MB |
| TTS 月度配额 | 扣子平台 plan 决定 | 当前已实施段合并节省 67% |
| TTS 并发 | 3(代码层限制) | 防止 4404 限流 |

---

## 七、调试工具推荐

### 7.1 命令行(curl + jq)

```bash
# 提交任务 + 自动轮询
TASK_ID=$(curl -s -X POST http://localhost:5000/async_run \
  -H "Content-Type: application/json" \
  -d '{"media_file":{"url":"https://example.com/test.mp3","file_type":"audio"}}' \
  | jq -r '.task_id')

# 轮询直到完成
while true; do
  STATUS=$(curl -s http://localhost:5000/task/$TASK_ID | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "success" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done

# 打印结果
curl -s http://localhost:5000/task/$TASK_ID | jq .
```

### 7.2 图形化(Postman / Apifox)

导入以下 Swagger 规范即可自动生成测试集合:
- 路径: `http://localhost:5000/openapi.json` (FastAPI 自动生成)
- 在 Postman 中: Import → Link → 输入上述 URL

### 7.3 浏览器直接访问

```
http://localhost:5000/docs
```
FastAPI 自动生成的 Swagger UI 文档。

---

## 八、生产环境部署建议

1. **必须用 HTTPS**: 工作流处理用户音频,涉及隐私
2. **加 API Key 鉴权**: 在 `src/main.py` 加 `Depends(verify_api_key)`
3. **加 Rate Limit**: 用 `slowapi` 限制单 IP QPS
4. **日志收集**: 把 `logs/app.log` 接入 ELK / Loki
5. **监控告警**: `/health` 接入 Prometheus
6. **异步任务持久化**: 用 Redis 替换默认内存存储

---

## 九、联系方式

遇到本文档**未覆盖**的问题:
1. 先看 `docs/workflow_operation_log.md` 的"异常码对照表"
2. 再 grep `logs/app.log` 关键字
3. 实在搞不定 → 联系原作者
