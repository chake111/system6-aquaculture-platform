# 密度分析模块最小任务

> 模块范围：`FR-04`；支撑 `AT-05`。
> 前置依赖：完成 [认证与权限](./auth-and-access.md)；发布放流/捕捞建议前完成 [溶氧调控](./oxygen-control.md) 提供的通用建议状态机。

**完成定义：** 技术员可登记声呐/图像样本并获得带模型版本和误差的密度结果；结果须复核后发布处置建议；养殖户能提交执行反馈；模拟样本与效果口径清晰标注。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增 | `backend/src/aquaculture_api/domain/density_analysis.py` | 密度结果、复核和建议判定 |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`repositories/density.py` | `media_samples`、`density_analyses` |
| 后端新增 | `backend/src/aquaculture_api/integrations/object_storage/` | 本地/对象媒体存储适配 |
| 后端新增 | `backend/src/aquaculture_api/schemas/density.py`、`services/density_service.py`、`api/routers/density.py` | 样本、分析和复核 API |
| 前端新增 | `frontend/src/api/density.ts`、`components/density/`、`views/DensityControlView.vue` | 样本、分析、审核与反馈页面 |
| 前端修改 | `frontend/src/router/index.ts` | `/control/density` 权限路由 |
| 测试新增 | `backend/tests/{unit,api}/test_density*.py`、`frontend/src/__tests__/DensityControlView.spec.ts` | 可追溯分析和权限交互 |

## Checklist

### D01 媒体样本与分析模型

- [ ] 创建 `media_samples`、`density_analyses` 持久化模型，保存鱼塘、采样时间、对象引用、校验值、来源模式、模型版本、误差和复核状态。
- [ ] 定义 `MediaStorageProvider` 接口及演示用本地实现，仅向响应暴露受控下载引用，不暴露任意服务器文件路径。
- [ ] 实现密度分析领域逻辑的首期可重复模拟算法或标注结果导入方式，输出单位面积尾数、误差范围、模型版本及建议草稿。
- [ ] 编写单元测试，验证媒体元数据校验、分析结果可追踪、未复核标记和模拟来源标签。

### D02 分析、复核与处置 API

- [ ] 实现 `POST /api/v1/media-samples` 与 `POST /api/v1/media-samples/{id}/analyses`，仅允许 T/A 或已认证绑定设备输入相应数据。
- [ ] 实现 `PATCH /api/v1/density-analyses/{id}/review`，记录技术员审核结论、标注说明和审计事件。
- [ ] 复用建议状态机，在复核通过后生成放流/捕捞建议，并允许养殖户通过建议执行反馈 API 记录处置。
- [ ] 编写 API 测试，验证角色限制、对象引用授权、复核前不可发布、模型版本/反馈追踪和跨基地拒绝。

### D03 前端密度调控页面

- [ ] 创建密度调控页面，显示样本元数据或安全缩略信息、密度值、误差、模型版本、来源和待复核状态。
- [ ] 为技术员提供复核/标注动作，为养殖户提供已发布放流或捕捞建议的执行反馈动作，按角色隐藏无权限控件。
- [ ] 在媒体暂不可下载时显示元数据和重试操作，不影响查看已有分析结论。
- [ ] 编写组件测试覆盖待复核/已复核显示、角色动作、媒体失败退化以及模拟标签。

### D04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_density_analysis.py tests/api/test_density.py`。
- [ ] 运行 `npm run frontend:test -- src/__tests__/DensityControlView.spec.ts`。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 以一份模拟样本完成“登记 -> 分析 -> 技术复核 -> 发布建议 -> 反馈处置”，确认样本、模型、审核人与执行记录均可追踪。

## 接口交付

本模块向效益报表提供密度建议与处置结果来源；准确率和误差验收必须使用经确认的标注样本集，不以演示样本宣称达到生产指标。
