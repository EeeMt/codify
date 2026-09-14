# 日志追踪方案

本文档描述前后端全链路日志追踪的实现与使用方式，便于快速定位线上问题。

## 概述

当用户报告问题时，通过 Trace ID 可以定位到相关日志。

### 核心机制

- 请求头带 `X-Trace-ID` 时后端直接沿用，否则生成一个 8 位短码
- Trace ID 写入 `request.state.trace_id`，在请求生命周期内可随时读取
- 每个请求的开始、结束（或异常）各写一条日志，都带同一个 Trace ID
- 响应头固定返回 `X-Trace-ID`，错误响应体里也带 `trace_id`
- 前端不生成也不回传 Trace ID：`frontend/src/api/client.ts` 只把错误响应体里的 `trace_id` 挂到 `error.apiError.traceId`，由各页面自行展示
- `frontend/src/api/interceptors.ts` 里另有一套保存并回传 Trace ID 的拦截器，但没有任何模块使用它创建的实例，引用它的 `ErrorToast.vue`（`showError` 无调用方）与 `TraceBadge.vue`（无人 import）也都没有渲染

要定位某一次具体请求，用那次响应或错误响应体返回的值；后端不校验请求头的格式，任何客户端
都可以自带任意值，服务端日志因此可能被伪造的 ID 误导。

### 效果示例

```
前端发起请求 → 响应头 X-Trace-ID = a1b2c3d4
   ↓
后端日志: a1b2c3d4 | -> GET /api/tasks
后端日志: a1b2c3d4 | <- 500 ...
   ↓
前端: error.apiError.traceId = a1b2c3d4
   ↓
运维: grep "a1b2c3d4" logs/app_2026-04-01.log
```

---

## 后端实现

### 1.1 依赖

`loguru>=0.7.0` 已在 `backend/requirements.txt` 中。

### 1.2 日志配置模块

`backend/app/core/logging.py` 负责初始化 Loguru，提供两个输出 sink：

| sink | 级别 | 格式 | 说明 |
|------|------|------|------|
| stderr | `LOG_LEVEL`，默认 `INFO` | 彩色单行 | 控制台输出 |
| `logs/app_<YYYY-MM-DD>.log` | `LOG_LEVEL`，默认 `INFO` | 单行文本 + `serialize=True` | JSON 行，便于检索 |

关键实现：

```python
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
RETENTION_DAYS = 7


def setup_logging():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    logger.remove()
    # 启动早期也可能写日志，先给 extra 一个默认值，避免格式串 KeyError
    logger.configure(extra={"trace_id": "--------"})

    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[trace_id]}</cyan> | <level>{message}</level>",
        colorize=True,
    )

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    logger.add(
        str(LOG_DIR / f"app_{today}.log"),
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[trace_id]} | {message}",
        rotation="00:00",       # 每天零点轮转
        retention=f"{RETENTION_DAYS} days",  # 保留 7 天
        serialize=True,         # JSON 格式
        enqueue=True,           # 异步写入
    )
```

日志目录是相对于进程工作目录的 `logs/`，所以从 `backend/` 启动时落在 `backend/logs/`。
`get_logger(name)` 目前忽略 `name` 参数，直接返回全局 `logger`；附加字段用 `logger.bind(...)`，
例如 `logger.bind(trace_id=...)`。模块还导出一个 `LoggerContext` 上下文管理器。

### 1.3 Trace 中间件

`backend/app/middleware/trace.py` 里是 `TraceMiddleware` 与 `get_trace_id(request)`，核心逻辑：

```python
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())[:8]
    request.state.trace_id = trace_id

    self.logger.bind(trace_id=trace_id).info(f"-> {request.method} {request.url.path}")

    start_time = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        status_code = response.status_code
        if status_code >= 400:
            self.logger.bind(trace_id=trace_id).warning(f"<- {status_code} ({duration_ms:.0f}ms)")
        else:
            self.logger.bind(trace_id=trace_id).info(f"<- {status_code} ({duration_ms:.0f}ms)")

        response.headers["X-Trace-ID"] = trace_id
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        self.logger.bind(trace_id=trace_id).error(
            f"X {type(e).__name__}: {str(e)} ({duration_ms:.0f}ms)"
        )
        return JSONResponse(
            status_code=500,
            headers={"X-Trace-ID": trace_id},
            content={
                "error": "Internal server error",
                "trace_id": trace_id,
                "type": type(e).__name__,
            },
        )
```

中间件自己把未捕获异常转成 500 响应，所以异常不会继续往外抛。

### 1.4 注册到应用

`backend/app/main.py` 在模块加载时初始化日志并注册中间件：

```python
setup_logging()
logger = get_logger(__name__)

app.add_middleware(TraceMiddleware)
```

另外注册了一个统一异常处理器，兜住走到中间件之外的异常：

```python
@app.exception_handler(Exception)
async def handle_exception(request: Request, exc: Exception):
    trace_id = get_trace_id(request)
    logger.bind(trace_id=trace_id).error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}"
    )
    return JSONResponse(
        status_code=500,
        headers={"X-Trace-ID": trace_id},
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "type": type(exc).__name__,
        },
    )
```

健康检查端点是 `GET /health`，返回体里带 `trace_id`：

```python
@app.get("/health")
async def health(request: Request) -> dict:
    trace_id = get_trace_id(request)
    health_status = {
        "status": "healthy",
        "checks": {},
        "trace_id": trace_id,
        "harness_execution_mode": get_settings().harness_execution_mode,
    }
    ...
```

### 1.5 业务代码中使用

`get_logger` 返回全局 logger，用 `bind` 附加 Trace ID：

```python
from app.core.logging import get_logger
from app.middleware.trace import get_trace_id

@app.post("/api/tasks")
async def create_task(request: Request, task_data: TaskCreate):
    trace_id = get_trace_id(request)
    logger = get_logger()

    logger.bind(trace_id=trace_id).info(f"创建任务: {task_data.title}")
    try:
        task = await task_service.create(task_data)
        logger.bind(trace_id=trace_id).info(f"任务创建成功: {task.id}")
        return task
    except Exception as e:
        logger.bind(trace_id=trace_id).error(f"任务创建失败: {e}")
        raise
```

---

## 前端实现

### 2.1 API 拦截器

`frontend/src/api/interceptors.ts` 提供 axios 实例与两个取值函数。拦截器的关键部分：

```typescript
let lastTraceId = ''

api.interceptors.request.use((config) => {
  // 把上一次的 Trace ID 传下去
  if (lastTraceId) {
    config.headers['X-Trace-ID'] = lastTraceId
  }
  return config
})

api.interceptors.response.use(
  (response: AxiosResponse) => {
    const traceId = response.headers['x-trace-id']
    if (traceId) {
      lastTraceId = traceId
      window.__lastTraceId = traceId
    }
    return response
  },
  async (error: AxiosError) => {
    const errorData = error.response?.data as Record<string, unknown> | undefined
    const traceId =
      error.response?.headers?.['x-trace-id'] ||
      errorData?.trace_id ||
      lastTraceId ||
      'unknown'

    window.__lastTraceId = traceId
    window.__lastError = {
      message: (typeof errorData?.error === 'string' ? errorData.error : undefined) || error.message,
      traceId,
      timestamp: new Date().toISOString(),
      status: error.response?.status,
    }

    return Promise.reject({ ...error, traceId, trace_id: traceId })
  }
)

export { api }
export function getLastTraceId(): string { return lastTraceId }
export function getLastError(): { message: string; traceId: string; timestamp: string; status?: number } | null {
  return (window as any).__lastError || null
}
```

错误对象同时带 `traceId` 与 `trace_id` 两个字段。

### 2.2 错误提示组件

`frontend/src/components/ErrorToast.vue` 读取 `getLastError()`，把错误信息和 Trace ID 显示在右下角，
点击 Trace ID 复制到剪贴板，面板在 5000ms 后自动隐藏。显示入口是组件暴露的 `showError()`，
目前没有调用方，页面上的报错不会自动弹出这个提示。

### 2.3 全局挂载

`frontend/src/main.ts` 单独挂载一个 ErrorToast 实例，并挂到 `window.__errorToast`：

```typescript
const app = createApp(App)
app.use(i18n)
app.use(router)

const errorToast = createApp(ErrorToast)
const errorToastMount = errorToast.mount(document.createElement('div'))
document.body.appendChild(errorToastMount.$el)

;(window as any).__errorToast = errorToastMount

app.config.errorHandler = (err, _instance, info) => {
  console.error('Vue Error:', err, info)
}
```

组件通过 `defineExpose({ showError })` 暴露显示方法，调用方从 `window.__errorToast` 取。

### 2.4 调试面板

`frontend/src/components/TraceBadge.vue` 是一个固定右下角的小徽标，每 1000ms 从 `getLastTraceId()`
刷新一次，点击复制当前 ID。这个组件没有被 `main.ts` 或任何页面引用，需要时自己 import 并挂载。

---

## 日志查询

### 按 Trace ID 查询

```bash
grep "a1b2c3d4" logs/app_2026-04-01.log
tail -f logs/app_2026-04-01.log | grep "a1b2c3d4"
grep "a1b2c3d4" logs/app_2026-04-*.log
```

文件是 JSON 行，用 `jq` 过滤字段更省事：

```bash
grep "a1b2c3d4" logs/app_2026-04-01.log | jq -r '.record.time.repr + " " + .record.level.name + " " + .record.message'
```

### 按时间范围查询

```bash
grep "2026-04-01 1[01]:" logs/app_2026-04-01.log
grep "user_id=123" logs/app_2026-04-01.log | grep "a1b2c3d4"
```

### 日志查询脚本

`scripts/grep_logs.sh` 按 Trace ID 与日期取日志，找到时优先用 `jq` 格式化：

```bash
./scripts/grep_logs.sh a1b2c3d4 2026-04-01
```

不带日期参数时用当天日期。脚本在 `logs/` 下找 `app_<日期>.log`，所以要在日志所在目录执行，
或者自己改 `LOG_DIR`。

---

## 模块清单

### 后端

| 文件 | 说明 |
|------|------|
| `backend/requirements.txt` | 声明 `loguru>=0.7.0` |
| `backend/app/core/logging.py` | 日志配置模块，`setup_logging` / `get_logger` / `LoggerContext` |
| `backend/app/middleware/trace.py` | Trace ID 中间件与 `get_trace_id` |
| `backend/app/main.py` | 初始化日志、注册中间件与统一异常处理器 |
| `backend/logs/` | 运行期日志目录，已在 `.gitignore` 中忽略 |

### 前端

| 文件 | 说明 |
|------|------|
| `frontend/src/api/interceptors.ts` | axios 实例、`getLastTraceId` / `getLastError` |
| `frontend/src/components/ErrorToast.vue` | 错误提示组件 |
| `frontend/src/components/TraceBadge.vue` | 调试徽标组件（未被引用，按需挂载） |
| `frontend/src/main.ts` | 挂载 ErrorToast 并暴露到 `window.__errorToast` |

### 运维

| 文件 | 说明 |
|------|------|
| `.gitignore` | 忽略 `backend/logs/` |
| `scripts/grep_logs.sh` | 按 Trace ID 查询日志 |

---

## 示例输出

### 后端日志（JSON 行）

文件 sink 开了 `serialize=True`，每行是 Loguru 的完整记录对象：

```json
{"text": "2026-04-01 12:00:00 | INFO     | a1b2c3d4 | -> POST /api/tasks\n", "record": {"extra": {"trace_id": "a1b2c3d4"}, "level": {"name": "INFO"}, "message": "-> POST /api/tasks", "time": {"repr": "2026-04-01 12:00:00.123456+08:00"}, "name": "app.middleware.trace", "function": "dispatch"}}
{"text": "2026-04-01 12:00:01 | INFO     | a1b2c3d4 | <- 201 (150ms)\n", "record": {"extra": {"trace_id": "a1b2c3d4"}, "level": {"name": "INFO"}, "message": "<- 201 (150ms)", "time": {"repr": "2026-04-01 12:00:01.234567+08:00"}, "name": "app.middleware.trace", "function": "dispatch"}}
```

`text` 字段就是控制台看到的那一行。要看某个请求的全部日志，过滤 `record.extra.trace_id`。

### 前端错误提示

组件挂载后的渲染效果（需要调用方触发 `showError()`）：

```
┌─────────────────────────────────────┐
│ ⚠️ 请求失败                           │
│ ID: a1b2c3d4 (点击复制)              │
└─────────────────────────────────────┘
```

### 运维查询

```bash
$ ./scripts/grep_logs.sh a1b2c3d4
=== Trace ID: a1b2c3d4 | 日期: 2026-04-01 ===
{
  "text": "2026-04-01 12:00:00 | INFO     | a1b2c3d4 | -> POST /api/tasks\n",
  "record": {
    "extra": { "trace_id": "a1b2c3d4" },
    "message": "-> POST /api/tasks"
  }
}
```
