# 弱网同步模块最小任务

> 模块范围：`FR-07`；支撑 `AT-07`、`NFR-06`。
> 前置依赖：完成 [认证与权限](./auth-and-access.md) 的数据范围基础及 [水质监测](./water-quality-monitoring.md) 的幂等读数接收服务。

**完成定义：** 边缘身份可按批次上传不可变事件；断网缓存可保留至少 7 天的模拟数据；恢复同步后重复事件不产生重复读数/预警；用户页面明确显示离线和最后同步状态。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`repositories/sync.py` | `edge_nodes`、`sync_batches` 与事件去重 |
| 后端新增 | `backend/src/aquaculture_api/integrations/edge_identity/` | 节点认证/签名模拟适配器 |
| 后端新增 | `backend/src/aquaculture_api/schemas/edge_sync.py`、`services/sync_service.py`、`api/routers/edge_sync.py` | 批次协议、逐项结果和确认游标 |
| 后端新增 | `backend/src/aquaculture_api/tasks/sync_backlog.py` | 同步积压检查 |
| 演示工具新增 | `backend/tests/fixtures/edge_events.json` 或 `backend/scripts/simulate_edge_sync.py` | 可重复的断网/补传输入 |
| 前端新增/修改 | `frontend/src/services/offline-cache.ts`、`stores/connectivity.ts`、`components/layout/ConnectivityBar.vue` | 最近视图缓存与同步状态 |
| 测试新增 | `backend/tests/{unit,api}/test_sync*.py`、`frontend/src/__tests__/connectivity.spec.ts` | 幂等、恢复与离线展示 |

## Checklist

### S01 边缘身份与同步协议

- [ ] 创建边缘节点和同步批次模型，保存节点绑定基地、批次键、接收/接受/拒绝计数、确认游标、最后心跳和状态。
- [ ] 定义边缘事件 schema，要求 `event_id`、节点/设备/鱼塘、UTC 采集时间、载荷校验值与 `source_mode`；定义逐项接受、重复和拒绝响应。
- [ ] 实现 `EdgeIdentityProvider` 模拟鉴权及请求防重放校验接口，拒绝未绑定设备或超出基地范围的事件。
- [ ] 编写测试覆盖有效节点、错误签名/重放、越权鱼塘和格式不合法事件的诊断响应。

### S02 批量上传和幂等补传

- [ ] 实现 `POST /api/v1/edge/readings:batch`：逐项校验后调用监测服务入库，并在事务完成后返回接受、重复、拒绝及确认时间。
- [ ] 对 `batch_key` 与 `event_id` 建立唯一处理规则，重复上传返回已接收且不得再次触发读数、建议或预警。
- [ ] 实现同步积压检查任务，按最后同步时间和待补传数量输出运维可消费的告警状态。
- [ ] 编写集成测试模拟在线上传、断网后多批恢复、重复补传和部分坏记录，核对最终读数数量与批次结果。

### S03 离线缓存与现场提示

- [ ] 实现前端最近成功仪表盘/水质视图缓存封装，缓存内容包含采集时间、获取时间和是否来自模拟数据。
- [ ] 在在线状态条展示网络可达性、最后同步时间和“缓存数据”标签；离线时禁止将缓存视图显示为实时数据。
- [ ] 准备可重复运行的边缘模拟数据或脚本，覆盖断网超过多个批次后重新同步的演示路径。
- [ ] 编写前端测试，验证在线到离线切换、缓存读取、重新联网刷新和数据时间标识。

### S04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_sync_service.py tests/api/test_edge_sync.py`。
- [ ] 运行 `npm run frontend:test -- src/__tests__/connectivity.spec.ts`。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 运行断网/补传演示数据，确认重复事件只保存一次、批次确认可查询、缓存视图清晰标识，并记录至少 7 天保留策略的配置或测试证据。

## 接口交付

本模块向运维页面交付节点健康与同步积压状态，向水质/预警闭环提供可靠且幂等的现场数据输入。
