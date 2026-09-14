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

前端不生成、也不回传 Trace ID。应用里的请求都走 `frontend/src/api/client.ts` 的 axios 实例，
它只做两件事：401 且未显式跳过时跳到登录页，其余错误把响应体里的 `trace_id` 挂到 `error.apiError`。

```typescript
export const api = axios.create({ baseURL: '/api', timeout: 30000, withCredentials: true })

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 且未带 X-Skip-Auth-Redirect 时 window.location.assign('/login?next=…&reason=…')
    error.apiError = {
      status: error?.response?.status ?? 0,
      message: error?.message ?? 'Unknown error',
      traceId: error?.response?.data?.trace_id,
      detail: typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : undefined,
    }
    return Promise.reject(error)
  }
)
```

所以页面上的错误提示由各视图自己用 `message.error` 给出，错误对象上带 `error.apiError.traceId`。
要反查一次请求，用后端返回的那个值：响应头 `X-Trace-ID`、错误响应体的 `trace_id`，或者让用户
提供任务 / 需求编号与大致时间。

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
| `frontend/src/api/client.ts` | 应用唯一的 axios 实例；401 跳转与 `error.apiError.traceId` |
| `frontend/src/main.ts` | 挂载应用；`errorHandler` 只写控制台 |

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

### 前端错误对象

页面从 `catch` 里拿到的是挂过 `apiError` 的 axios 错误，可以直接把 `traceId` 一起展示：

```typescript
{
  message: 'Request failed with status code 500',
  apiError: { status: 500, message: '...', traceId: 'a1b2c3d4', detail: '...' },
}
```
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
