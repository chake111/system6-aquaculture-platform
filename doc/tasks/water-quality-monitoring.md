# 水质监测模块最小任务

> 模块范围：`FR-03`，并提供 `FR-05`、`FR-06` 的水质输入；支撑 `AT-03`。
> 前置依赖：完成 [认证与权限](./auth-and-access.md) 的范围过滤、数据库和前端应用壳。

**完成定义：** 授权用户可按鱼塘查看溶氧/pH 最新值和历史趋势；读数标注来源与质量；阈值判断产生可供调控和预警模块消费的异常结果；页面刷新与缓存标识符合设计。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增 | `backend/src/aquaculture_api/domain/water_quality.py` | 读数质量、阈值结果和值对象 |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`persistence/repositories/readings.py` | `water_readings`、`threshold_rules` 与查询 |
| 后端新增 | `backend/src/aquaculture_api/schemas/readings.py`、`services/monitoring_service.py`、`api/routers/readings.py` | 水质入库与查询 API |
| 前端新增 | `frontend/src/api/monitoring.ts`、`stores/monitoring.ts` | 最新值、趋势和最近成功缓存 |
| 前端新增 | `frontend/src/components/monitoring/`、`views/WaterQualityView.vue` | 指标卡、趋势展示、来源/质量状态 |
| 前端修改 | `frontend/src/views/DashboardView.vue`、`router/index.ts` | 仪表盘摘要和水质路由 |
| 测试新增 | `backend/tests/{unit,api}/test_monitoring*.py`、`frontend/src/__tests__/WaterQualityView.spec.ts` | 规则、查询、刷新与缓存展示 |

## Checklist

### W01 数据模型与质量规则

- [ ] 增加 `water_readings` 和 `threshold_rules` 持久化模型及 `(pond_id, captured_at)`、`event_id` 约束，保留 `source_mode` 和规则版本。
- [ ] 定义水质请求/响应 schema，校验溶氧、pH、采集时间、设备、质量状态和模拟/真实来源。
- [ ] 实现质量判断与版本化阈值评估：无效或未校准读数只能返回人工复核结果，不能直接产生设备执行意图。
- [ ] 编写单元测试覆盖正常读数、低溶氧、异常 pH、无效质量和缺失个性化规则时回退基地默认规则。

### W02 查询与采集服务

- [ ] 实现 `MonitoringService` 的幂等保存、最新读数查询、按时间范围/指标的历史序列查询和阈值评估结果返回。
- [ ] 实现 `GET /api/v1/ponds/{pond_id}/readings/latest` 与 `GET /api/v1/ponds/{pond_id}/readings`，执行鱼塘范围检查、分页/时间筛选和审计关联。
- [ ] 提供服务层接收单条模拟读数的测试入口或 fixture，批量边缘接入由弱网同步模块复用服务接口，不在本模块重复实现协议。
- [ ] 编写 API 测试，验证读数一致性、跨基地拒绝、来源标识、趋势排序以及 `event_id` 重复提交不重复入库。

### W03 前端水质视图

- [ ] 实现 `monitoring` API client 与 store：获取当前鱼塘最新值和历史序列，保存最后成功响应及同步时间。
- [ ] 创建水质页面的鱼塘/时间筛选、溶氧和 pH 指标卡、阈值状态与趋势呈现，并在仪表盘展示最新摘要。
- [ ] 实现最多 10 秒的页面轮询；请求失败时只读显示最近缓存并以文字标记“缓存数据”和采集时间。
- [ ] 编写组件测试，验证风险状态、质量异常提示、轮询更新、失败后缓存标识和无授权路由不可访问。

### W04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_water_quality.py tests/api/test_readings.py`，确认阈值、幂等和范围用例通过。
- [ ] 运行 `npm run frontend:test -- src/__tests__/WaterQualityView.spec.ts`，确认页面数据展示与缓存退化行为通过。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 注入一条正常和一条低溶氧模拟读数，确认页面内容与 API 一致，且异常评估输出包含鱼塘、规则版本和来源模式。

## 接口交付

本模块向调控与预警模块交付已校验水质读数、阈值评估结果及趋势查询能力；异常处理闭环不得在本模块内提前实现。
