# 详细设计文档：智慧水产养殖监测与调控平台

## 1. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 + TypeScript                │
│  LoginView │ DashboardView │ MonitoringView │ ...    │
│  VoiceLogin │ TrendChart │ AgentPanel                │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (JWT Bearer)
┌──────────────────────┴──────────────────────────────┐
│                  FastAPI + SQLAlchemy                 │
│  routes/auth │ routes/ponds │ routes/alerts │ ...    │
│  routes/recommendations │ routes/density │ routes/edge│
│  routes/reports │ routes/operations │ routes/agent    │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │     SQLite      │  ← 进程内存储，演示环境
              │   (可切换PG)    │
              └─────────────────┘
```

技术栈：
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router
- 后端：Python 3.12 + FastAPI + SQLAlchemy + Pydantic
- 数据库：SQLite（演示环境，生产可切换 PostgreSQL/MySQL）
- 认证：JWT（PyJWT），支持 access_token + refresh_token
- AI 集成：DeepSeek 大模型，无 API 时降级到规则引擎

## 2. 状态机设计

### 2.1 建议状态机（溶氧调控 / 密度分析）

```
generated ──→ reviewed ──→ confirmed ──→ [execution] ──→ evaluated
    │              │
    └──→ rejected  └──→ (rejected)
```

| 转换 | 触发角色 | API 端点 |
| --- | --- | --- |
| generated → reviewed | 技术员/管理员 | `PATCH /recommendations/{id}/review` |
| generated → rejected | 技术员/管理员 | `PATCH /recommendations/{id}/review` |
| reviewed → confirmed | 养殖户/技术员 | `POST /recommendations/{id}/confirm` |
| confirmed → execution | 养殖户/技术员 | `POST /recommendations/{id}/executions` |
| execution → evaluated | 养殖户/技术员 | `PATCH /executions/{id}/feedback` |

### 2.2 告警状态机

```
open → delivered / delivery_failed → acknowledged → resolved → closed
```

| 转换 | 触发角色 | API 端点 |
| --- | --- | --- |
| → delivered/delivery_failed | 系统自动 | 通知发送结果 |
| delivered → acknowledged | 任意授权用户 | `POST /alerts/{id}/acknowledge` |
| acknowledged → resolved | 养殖户/技术员 | `POST /alerts/{id}/resolve` |
| resolved → closed | 技术员/管理员 | `POST /alerts/{id}/close` |
| 全链路快捷 | 养殖户/管理员 | `POST /alerts/{id}/quick-response` |

### 2.3 密度分析复核状态

```
pending → approved / rejected
```

复核通过后自动创建一条 `recommendation`（status=reviewed）。

### 2.4 通知送达状态

```
pending → delivered / failed (重试计数)
```

重试耗尽后标记为人工处理。

## 3. 数据库设计

### 3.1 核心表

| 表名 | 用途 | 关键字段 |
| --- | --- | --- |
| `users` | 用户账号 | id, phone, credential_hash, role, pond_scope |
| `ponds` | 塘口 | id, name, base_id, source_mode |
| `devices` | 设备 | code, pond_id, device_type, source_mode, status |
| `water_readings` | 水质读数 | id, event_id, pond_id, captured_at, dissolved_oxygen_mg_l, ph, source_mode |
| `threshold_rules` | 阈值规则 | id, warning_below, version, source_mode |
| `recommendations` | 建议 | id, pond_id, status, reason, rule_version, agent_mode |
| `control_executions` | 执行记录 | id, recommendation_id, idempotency_key, execution_mode, status |
| `alerts` | 告警 | id, pond_id, status, delivery_status, recommendation_id |
| `notification_deliveries` | 通知送达 | id, alert_id, channel, provider_mode, status, attempts |
| `audit_logs` | 审计日志 | id, actor_id, action, resource_id, trace_id, occurred_at |
| `media_samples` | 媒体样本 | id, pond_id, sample_type, object_ref, source_mode |
| `density_analyses` | 密度分析 | id, sample_id, estimated_density_fish_m2, error_margin_fish_m2, review_status |
| `benefit_metrics` | 效益指标 | id, pond_id, label, value, unit, period, source_mode |
| `export_records` | 导出记录 | id, actor_id, purpose, redaction_policy, expires_at, idempotency_key |
| `archive_records` | 归档记录 | id, actor_id, action, scope, approval_ref, evidence_only |
| `sync_batches` | 同步批次 | id, node_id, batch_key, accepted_count, duplicate_count |
| `edge_nonces` | 边缘去重 | nonce, seen_at |

### 3.2 关键约束

- `water_readings.event_id`：UNIQUE，边缘事件幂等键
- `control_executions.idempotency_key`：UNIQUE，执行幂等键
- `export_records.idempotency_key`：UNIQUE，导出幂等键
- `archive_records.idempotency_key`：UNIQUE，归档幂等键
- `sync_batches.batch_key`：UNIQUE，批次幂等键
- `users.phone`：UNIQUE + INDEX
- 所有时间字段存储 UTC 字符串

### 3.3 来源标识

每条业务数据包含 `source_mode` 字段：
- `simulation`：演示模拟数据
- `crawled`：通过爬虫脚本从公开数据源采集或基于真实参数生成
- `auto`：自动采集（生产环境）

执行记录额外包含 `execution_mode` 字段：`simulation` / `real`。

## 4. API 设计

### 4.1 认证模块

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 无 | 手机号 + 密码登录，返回 access_token, refresh_token, role |
| POST | `/api/v1/auth/refresh` | 无 | 刷新 access_token |
| GET | `/api/v1/me` | Bearer | 当前用户信息 |
| POST | `/api/v1/auth/offline-grants` | Bearer | 发放离线授权（最长 7 天） |

### 4.2 塘口与读数

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/ponds` | Bearer | 列出授权塘口 |
| GET | `/api/v1/devices` | 技术员/管理员 | 列出设备 |
| POST | `/api/v1/devices` | 管理员 | 创建设备 |
| GET | `/api/v1/ponds/{id}/readings` | Bearer | 塘口所有读数 |
| GET | `/api/v1/ponds/{id}/readings/latest` | Bearer | 最新读数 |

### 4.3 建议（溶氧调控）

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/ponds/{id}/recommendations` | Bearer | 塘口建议列表 |
| PATCH | `/api/v1/recommendations/{id}/review` | 技术员/管理员 | 复核（approve/reject） |
| POST | `/api/v1/recommendations/{id}/confirm` | 养殖户/技术员 | 确认 |
| POST | `/api/v1/recommendations/{id}/executions` | 养殖户/技术员 | 执行（幂等） |
| PATCH | `/api/v1/executions/{id}/feedback` | 养殖户/技术员 | 执行后反馈 |

### 4.4 告警

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/alerts` | Bearer | 告警列表 |
| POST | `/api/v1/alerts/{id}/acknowledge` | Bearer | 确认告警 |
| POST | `/api/v1/alerts/{id}/resolve` | 养殖户/技术员 | 处置告警 |
| POST | `/api/v1/alerts/{id}/close` | 技术员/管理员 | 关闭告警 |
| POST | `/api/v1/alerts/{id}/quick-response` | 养殖户/管理员 | 快捷全链路 |

### 4.5 密度分析

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/media-samples` | 技术员/管理员 | 注册样本 |
| POST | `/api/v1/media-samples/{id}/analyses` | 技术员/管理员 | 创建分析 |
| PATCH | `/api/v1/density-analyses/{id}/review` | 技术员/管理员 | 复核分析 |

### 4.6 边缘同步

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/edge/readings:batch` | 边缘签名 | 批量上传，幂等去重 |

签名验证：`X-Edge-Timestamp` + `X-Edge-Nonce` + `X-Edge-Signature`。

### 4.7 报表与归档

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/reports/benefits` | 技术员/管理员 | 效益指标 |
| POST | `/api/v1/exports` | 技术员/管理员 | 脱敏导出（幂等） |
| POST | `/api/v1/archives` | 管理员 | 归档/销毁（需审批引用） |

### 4.8 运维

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/operations/health` | 管理员 | 组件健康状态 |
| GET | `/api/v1/operations/sync-batches` | 管理员 | 同步批次历史 |
| GET | `/api/v1/audit-logs` | 管理员 | 审计日志查询 |
| PUT | `/api/v1/threshold-rules/{id}` | 管理员 | 阈值配置（带审计） |

### 4.9 AI Agent

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/agent/status` | Bearer | Agent 状态 |
| POST | `/api/v1/agent/analyze` | 技术员/管理员 | 水质分析 |
| POST | `/api/v1/agent/recommend` | 技术员/管理员 | 生成建议 |

### 4.10 演示

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/demo/ponds/{id}/low-oxygen` | Bearer | 注入低溶氧事件 |

## 5. 安全设计

### 5.1 认证与授权
- JWT access_token（短期）+ refresh_token（长期）
- 角色：farmer / technician / admin
- 数据范围：pond_scope 字段控制塘口级访问
- 离线授权：最长 7 天，限制敏感操作

### 5.2 审计日志
所有关键操作写入 `audit_logs`：
- 登录、授权变更
- 建议复核、确认、执行
- 告警处置
- 通知发送
- 同步拒绝
- 导出、归档
- 配置变更

每条审计记录包含：actor_id, action, resource_id, trace_id, occurred_at。

### 5.3 敏感数据保护
- 凭据哈希 + 盐值存储，API 响应不返回
- 导出脱敏策略 `mask-identifiers-v1`：去除手机号、媒体存储地址
- 环境密钥不暴露在 API 响应或异常信息中
- 所有 API 错误使用统一格式 `{"error": {"code": "...", "message": "..."}}`

### 5.4 请求追踪
所有 HTTP 响应包含 `X-Trace-Id` 头，关联审计日志。

## 6. 前端设计

### 6.1 页面结构

| 页面 | 路由 | 功能 |
| --- | --- | --- |
| 登录页 | `/login` | 角色登录、语音登录、高对比度切换 |
| 仪表盘 | `/dashboard` | DO/pH 卡片、告警工作流、AI 建议面板 |
| 水质监测 | `/monitoring` | DO/pH 趋势图、读数表格、10 秒轮询、离线缓存提示 |
| 密度分析 | `/density` | 样本注册、密度结果、复核工作流 |
| 预警中心 | `/alerts` | 告警详情、严重度、通知送达状态 |
| 效益报表 | `/reports` | 效益指标表格、脱敏导出 |
| 运维管理 | `/operations` | 组件健康、同步批次、审计日志、阈值配置、归档 |

### 6.2 核心组件

| 组件 | 功能 |
| --- | --- |
| `VoiceLogin.vue` | Web Speech API 语音识别（zh-CN），识别角色名登录 |
| `TrendChart.vue` | SVG 趋势图，含阈值线和 Y 轴网格 |
| `AgentPanel.vue` | DeepSeek AI 建议面板，显示 LLM/规则引擎模式 |

### 6.3 状态管理
- Pinia store 管理认证状态和用户信息
- 路由守卫强制认证和角色过滤
- 10 秒轮询水质数据，失败时显示缓存数据

## 7. 测试设计

### 7.1 后端测试（109 个 pytest 用例）

| 测试文件 | 用例数 | 覆盖范围 |
| --- | --- | --- |
| test_domain_logic.py | 65 | 领域规则、状态机、权限、来源标识 |
| test_error_paths.py | 20 | 异常路径、未认证、越权、输入错误 |
| test_agent.py | 8 | AI Agent 集成、规则引擎降级 |
| test_compliance_api.py | 7 | 脱敏导出、归档、审计 |
| test_platform_api.py | 5 | API 端点集成测试 |
| test_reference_data.py | 3 | 参考数据验证 |
| test_health.py | 1 | 健康检查 |

### 7.2 测试命令

```bash
# 后端
cd backend && uv run pytest tests/ -q

# 前端类型检查
cd frontend && npm run type-check

# 前端构建
cd frontend && npm run build
```

## 8. 部署架构

演示环境使用双服务模式：
- 后端：FastAPI on `localhost:8000`
- 前端：Vite dev server on `localhost:4173`（代理 API 到后端）

启动脚本：`start-demo.bat`

生产环境可切换：
- 数据库：SQLite → PostgreSQL/MySQL
- 部署：Docker + Nginx 反向代理
- 边缘：4G 路由器 + 边缘计算节点
