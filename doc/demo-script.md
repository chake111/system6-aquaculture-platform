# 五分钟演示脚本

## 前置条件

1. 按 [deployment.md](./deployment.md) 启动 FastAPI 与 Vue 服务。
2. 打开 `http://127.0.0.1:4173/`。
3. 演示中的塘口操作均为 `simulation`，不操作真实设备。
4. 语音登录需使用 Chrome 浏览器（支持 Web Speech API）。

## 演示步骤

| 时间 | 操作 | 可见证据 |
| --- | --- | --- |
| `0:00-0:30` | 展示语音登录功能。点击”语音登录”按钮，说”技术员”。 | 语音识别状态显示”识别到：技术员，正在登录”，自动进入技术员仪表盘。 |
| `0:30-1:00` | 打开”水质监测”。 | 展示 `GX-HZ-001`（广西惠州鲈鱼养殖基地）、`crawled`、北京时间、`24` 条配对 DO/pH 记录；溶氧 5.1-7.8 mg/L、pH 7.0-7.7 符合广西鲈鱼养殖塘口特征；通过 `scripts/fetch_guangxi_data.py` 脚本尝试从广西公共数据开放平台等公开 API 采集，降级时基于广西生态环境厅公开参数范围生成。 |
| `0:40-1:30` | 返回登录页，选择养殖户，在仪表盘点击“注入模拟低溶氧事件”。 | 页面显示 `simulation`、低溶氧读数 `3.2 mg/L`，建议停留在“等待技术员复核”，养殖户无法越过复核直接执行。 |
| `1:30-2:00` | 选择技术员登录，仪表盘点击“复核模拟建议”。 | 建议状态变为“等待养殖户确认”；状态来自后端存储，不是页面本地占位。 |
| `2:00-2:45` | 选择养殖户登录，依次点击“确认模拟建议”“模拟执行增氧”“记录处置完成”。 | 页面显示“已处置，等待技术员复核关闭”；执行与效果反馈均标注模拟/需现场验证。 |
| `2:45-3:15` | 选择技术员登录，点击“复核并关闭预警”。 | 页面显示“预警已关闭，演示审计记录可查询”。 |
| `3:15-3:45` | 技术员进入“密度调控”，点击“运行模拟分析并复核”。 | 显示 `38` 尾/平方米、误差 `+/- 4`、`density-demo-v1`、`approved` 和模拟声明。 |
| `3:45-4:20` | 技术员进入“效益报表”，点击“导出演示摘要”。 | 展示五项服务器指标、`simulation_unverified`、脱敏策略 `mask-identifiers-v1` 及到期时间。 |
| `4:20-5:00` | 管理员登录进入“运维管理”，点击“登记模拟归档审批”。 | 展示官方观测数量、同步保留 7 天、通知模拟模式及 `DEMO-APPROVAL-UI / evidence_only`。 |

## 浏览器证据

2026-05-27 使用本机 Chrome 在双服务模式下完成上述流程，截图位于：

- `output/playwright/integrated-farmer-injected.png`
- `output/playwright/integrated-technician-reviewed.png`
- `output/playwright/integrated-farmer-resolved.png`
- `output/playwright/integrated-technician-closed.png`
- `output/playwright/integrated-density-reviewed.png`
- `output/playwright/integrated-report-export.png`
- `output/playwright/integrated-admin-archive.png`

## 演示限制

- 外部真实数据仅证明来源可追踪与界面处理正确，不证明广东塘口水质。
- 增氧、通知、密度、效益和归档均只证明演示流程、权限、审计与标识能力。
- 未在本脚本中验证 500 并发、长期弱网缓存、真实第三方通知送达、现场设备执行或完整养殖周期收益。

