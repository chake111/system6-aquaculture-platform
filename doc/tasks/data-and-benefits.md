# 数据与效益模块最小任务

> 模块范围：`FR-08`、`FR-09`；支撑 `AT-08` 与效益验证数据准备。
> 前置依赖：完成 [认证与权限](./auth-and-access.md) 的最小基地/鱼塘模型；效益聚合使用调控、密度和预警模块已保存的业务证据。

**完成定义：** 管理员可维护基地、鱼塘和设备主数据；技术员/管理员可按授权范围查询指标口径和生成脱敏导出；所有指标说明数据来源、统计周期及模拟/真实属性。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增/修改 | `backend/src/aquaculture_api/persistence/orm_models.py`、`repositories/{master_data,reports}.py` | 设备、效益指标、导出任务 |
| 后端新增 | `backend/src/aquaculture_api/schemas/{master_data,reports}.py`、`services/report_service.py` | 台账、指标与脱敏导出 |
| 后端新增 | `backend/src/aquaculture_api/api/routers/{ponds,reports}.py`、`tasks/report_export.py` | 主数据与报表 API/导出任务 |
| 前端新增 | `frontend/src/api/reports.ts`、`views/BenefitReportView.vue`、`components/reports/` | 指标、口径、导出视图 |
| 前端修改 | `frontend/src/api/admin.ts`、`views/OperationsView.vue` | 主数据维护入口，由运维页承载 |
| 测试新增 | `backend/tests/{unit,api}/test_reports*.py`、`frontend/src/__tests__/BenefitReportView.spec.ts` | 计算、脱敏与导出权限 |

## Checklist

### B01 主数据和效益数据模型

- [ ] 扩展基地/鱼塘维护能力并创建 `devices`、`benefit_metrics`、`export_jobs` 模型，纳入范围、来源、统计周期和软删除/过期字段约定。
- [ ] 实现管理员维护鱼塘和设备所需的新增/查询接口，审计新增、变更和停用动作；非管理员不得修改主数据。
- [ ] 准备效益指标 fixture，分别标注模拟演示数据与可验证真实数据，涵盖用电成本、成活率、亩产、饲料成本和综合成本。
- [ ] 编写 API 测试覆盖主数据权限、数据溯源字段和跨基地查询隔离。

### B02 指标聚合与脱敏导出

- [ ] 实现 `ReportService` 按周期和鱼塘聚合指标，返回指标值、单位、计算口径、数据来源和 `verified` 状态。
- [ ] 实现 `GET /api/v1/reports/benefits` 与幂等的 `POST /api/v1/exports`，仅允许 T/A 在授权范围发起。
- [ ] 创建导出任务的演示实现，输出不含明文手机号、原始媒体存储地址和审计敏感内容的文件，并记录用途、策略、到期时间和导出审计。
- [ ] 编写测试验证计算口径、模拟数据提示、导出脱敏、重复导出幂等与未授权拒绝。

### B03 报表页面

- [ ] 创建效益报表页面，提供鱼塘和统计周期筛选，显示五类指标、单位、来源、口径以及是否已验证。
- [ ] 实现导出操作与导出状态显示；对仅含模拟数据或未完成真实周期的结果显示“仅供演示/评估”，不显示为既成收益。
- [ ] 在管理员运维页面预留基地、鱼塘和设备维护区域，复用管理员 API 并展示变更审计引用。
- [ ] 编写组件测试覆盖筛选、口径展开、导出权限和模拟/未验证提示。

### B04 模块验收

- [ ] 运行 `npm run backend:test -- tests/unit/test_report_service.py tests/api/test_reports.py`。
- [ ] 运行 `npm run frontend:test -- src/__tests__/BenefitReportView.spec.ts`。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`。
- [ ] 用模拟执行和密度反馈数据生成一份报表及脱敏导出，核对来源、用途、有效期和审计记录，同时确认页面没有宣称真实生产收益。

## 接口交付

本模块交付可追踪的台账、指标查询和脱敏导出；归档模块可将已导出的证据文件纳入批准后的归档或销毁流程。
