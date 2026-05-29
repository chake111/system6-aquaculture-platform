# 溶氧调控模块最小任务

> 模块范围：`FR-05`；支撑 `AT-04` 和演示链路中的增氧建议/执行。
> 前置依赖：完成 [认证与权限](./auth-and-access.md) 与 [水质监测](./water-quality-monitoring.md)。

**完成定义：** 低溶氧输入可产生带理由和版本的增氧建议；建议按状态机复核、确认、执行和评价；真实设备执行必须在授权确认后调用，演示默认使用明确标识的模拟适配器。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增 | `backend/src/aquaculture_api/domain/oxygen_control.py` | 增氧规则与建议状态机 |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`repositories/recommendations.py` | `recommendations`、`control_executions` |
| 后端新增 | `backend/src/aquaculture_api/integrations/weather/`、`integrations/device_control/` | 可替换气象和设备控制适配器 |
| 后端新增 | `backend/src/aquaculture_api/schemas/recommendations.py`、`services/recommendation_service.py`、`api/routers/recommendations.py` | 建议与执行 API |
| 前端新增 | `frontend/src/api/recommendations.ts`、`components/common/ActionConfirmDialog.vue` | 建议请求和二次确认 |
| 前端修改 | `frontend/src/views/DashboardView.vue` | 风险、理由、确认执行和反馈入口 |
| 测试新增 | `backend/tests/{unit,api}/test_recommendations*.py`、`frontend/src/__tests__/recommendations.spec.ts` | 规则、闸门、界面操作 |

## Checklist

### O01 建议规则和持久化

- [ ] 创建建议与执行模型，保存类型、风险等级、输入快照、规则版本、`source_mode`、`execution_mode`、幂等键和状态变化证据。
- [ ] 实现增氧建议规则：使用有效溶氧读数、近期趋势、养殖阶段与气象结果；气象失败时生成需复核的保守建议并记录缺失来源。
- [ ] 实现 `Generated -> Reviewed/Rejected -> Confirmed -> Executing -> Completed/Failed -> Evaluated` 状态迁移校验。
- [ ] 编写单元测试，验证低溶氧建议内容、气象降级、无效读数不产生控制建议和禁止跳过确认执行。

### O02 适配器与服务/API

- [ ] 定义 `WeatherProvider` 与 `DeviceControlProvider` 接口及模拟实现，使模拟执行结果固定标注 `execution_mode=simulation`。
- [ ] 实现建议生成、审核/确认、登记执行、回填结果和观察窗口效果评价服务，所有写操作记录审计和幂等键。
- [ ] 实现 `GET /api/v1/ponds/{pond_id}/recommendations`、`POST /api/v1/recommendations/{id}/confirm`、`POST /api/v1/recommendations/{id}/executions` 与 `PATCH /api/v1/executions/{id}/feedback`。
- [ ] 编写 API 测试，验证 F/T 权限、确认前禁止设备指令、重复执行幂等、模拟标识和后续读数效果评价。

### O03 前端建议处置

- [ ] 在仪表盘呈现待处理增氧建议的风险等级、建议时长、依据读数、气象/规则来源和模拟状态。
- [ ] 实现确认执行二次确认、执行模式显示和结果反馈表单；无权限角色只能查看授权允许的信息。
- [ ] 实现气象缺失、设备执行失败和待评价状态的清晰文案，不将演示结果显示为生产效果。
- [ ] 编写组件测试覆盖建议展示、确认对话框、失败反馈和模拟标签。

### O04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_oxygen_control.py tests/api/test_recommendations.py`。
- [ ] 运行 `npm run frontend:test -- src/__tests__/recommendations.spec.ts`。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 以低溶氧模拟事件完成“生成建议 -> 确认 -> 模拟执行 -> 回填读数 -> 效果评价”流程，确认审计和版本证据可追踪。

## 接口交付

本模块交付统一的调控建议/执行状态机，密度分析模块可以复用该状态机发布放流或捕捞建议，预警中心可在同一异常场景关联建议记录。
