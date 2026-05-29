# 预警中心模块最小任务

> 模块范围：`FR-06`；支撑 `AT-06` 及五分钟演示中的预警处置闭环。
> 前置依赖：完成 [认证与权限](./auth-and-access.md) 与 [水质监测](./water-quality-monitoring.md)；关联建议时依赖 [溶氧调控](./oxygen-control.md)。

**完成定义：** 阈值异常会创建或合并活动预警；模拟通知渠道可返回送达/失败状态并重试；授权用户可确认、处置与复核关闭；时间线和审计完整显示。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增 | `backend/src/aquaculture_api/domain/alerting.py` | 告警去重与状态机 |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`repositories/alerts.py` | `alerts`、`alert_events`、`notification_deliveries` |
| 后端新增 | `backend/src/aquaculture_api/integrations/notifications/`、`tasks/notification_delivery.py` | 短信/语音/钉钉模拟适配与重试 |
| 后端新增 | `backend/src/aquaculture_api/schemas/alerts.py`、`services/alert_service.py`、`api/routers/alerts.py` | 预警用例和 API |
| 前端新增 | `frontend/src/api/alerts.ts`、`stores/alerts.ts`、`components/alerts/`、`views/AlertCenterView.vue` | 预警列表、时间线和处置 |
| 前端修改 | `frontend/src/views/DashboardView.vue`、`router/index.ts` | 活动预警摘要和入口 |
| 测试新增 | `backend/tests/{unit,api}/test_alerts*.py`、`frontend/src/__tests__/AlertCenterView.spec.ts` | 去重、通知、处置 UI |

## Checklist

### L01 预警领域与去重

- [ ] 创建预警、事件和通知送达模型，保存鱼塘、严重度、状态、去重键、触发读数、渠道及时间线字段。
- [ ] 实现 `Open -> Notifying -> Delivered/DeliveryFailed -> Acknowledged -> Resolved -> Closed` 状态规则及误报关闭路径。
- [ ] 实现同一鱼塘、指标和等级在去重窗口内合并事件的逻辑，确保重复异常不会创建多条活动预警。
- [ ] 编写单元测试覆盖状态非法迁移、去重窗口、恢复读数关闭前置条件和处置时间计算。

### L02 通知与预警 API

- [ ] 定义 `NotificationProvider` 接口，为短信、语音和钉钉创建可配置模拟实现，保留送达回执与失败原因。
- [ ] 实现通知发送任务和有限次数指数退避重试；耗尽重试后标记人工处理，不丢弃预警。
- [ ] 实现 `GET /api/v1/alerts`、`GET /api/v1/alerts/{id}`、`POST /api/v1/alerts/{id}/acknowledge`、`resolve` 和 `close` API，并记录关键审计事件。
- [ ] 将水质阈值异常和已复核的密度异常结果接入预警创建，将关联增氧/密度建议 ID 展示在详情中；编写 API 测试覆盖两类来源、送达、失败、重试与权限范围。

### L03 前端预警处置

- [ ] 实现预警 store 和列表/详情组件，按严重程度排序并显示渠道送达状态、触发数据和处置时间线。
- [ ] 创建预警中心页面的确认收到、填写处置结果、申请关闭/复核关闭动作，并对关键关闭操作二次确认。
- [ ] 在仪表盘显示活动预警与送达失败提示；渠道失败时提供人工获知标记而非隐藏异常。
- [ ] 编写组件测试，验证排序、失败渠道显示、确认/处置表单和角色可执行动作。

### L04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_alerting.py tests/api/test_alerts.py`。
- [ ] 运行 `npm run frontend:test -- src/__tests__/AlertCenterView.spec.ts`。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 注入低溶氧异常并使用模拟通知渠道完成“生成/合并预警 -> 送达 -> 确认 -> 处置 -> 恢复 -> 关闭”，核对时间线和审计事件。

## 接口交付

本模块交付活动预警、通知状态和处置闭环 API；运维模块可读取通知失败/积压健康数据，报表模块可统计处置时长。
