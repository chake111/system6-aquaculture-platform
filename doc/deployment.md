# 部署与本地运行说明

## 运行定位

本工程提供课程验收用的演示环境：

- `pond-ref` 载入广西惠州鲈鱼养殖基地水质监测数据，用于来源追踪与水质展示。
- `pond-hz-01` 的读数注入、告警、建议、设备执行、密度、报表和归档均为 `simulation`。
- 演示环境不接入真实传感器、增氧机、短信/语音/钉钉服务或生产数据库，不得作为现场效果结论。

## 环境准备

要求：

- Node.js 满足 `frontend/package.json` 的版本约束。
- Python 3.12 与 `uv` 可用。

在项目根目录安装并验证依赖：

```powershell
npm install
npm --prefix frontend install
uv --directory backend sync
npm run check
```

## 本地启动

后端终端：

```powershell
uv --directory backend run uvicorn aquaculture_api.main:app --app-dir src --host 127.0.0.1 --port 8000
```

前端终端：

```powershell
cd frontend
npx vite --host=127.0.0.1 --port=4173 --strictPort
```

前端开发服务器通过 [vite.config.ts](../frontend/vite.config.ts) 将 `/api` 代理至 `http://127.0.0.1:8000`。访问：

```text
http://127.0.0.1:4173/
```

注意：演示后端使用进程内 SQLite 存储；重启后端会重新建立演示数据及官方观测 fixture，清空本次流程产生的告警、执行和归档记录。

## 演示身份

| 页面身份 | 手机号 | 演示口令 | 主要范围 |
| --- | --- | --- | --- |
| 养殖户 | `13800000001` | `demo-246810` | 注入模拟异常、确认已复核建议、模拟执行与反馈 |
| 技术员 | `13800000002` | `demo-246810` | 查看官方观测、复核建议、密度分析、报表与关闭告警 |
| 管理员 | `13800000003` | `demo-246810` | 运维健康、设备管理、审计及证据归档 |

页面按钮会使用相应演示身份调用登录接口；后端仅存储口令哈希与盐，不在 API 返回凭据内容。

## 配置边界

演示模式默认使用仅限本机演示的签名秘密。非演示环境必须提供外部注入的秘密：

```powershell
$env:APP_ENV = "production"
$env:JWT_SECRET = "<managed-secret>"
$env:EDGE_SECRET = "<managed-secret>"
```

后端会拒绝在非 `demonstration` 环境继续使用默认演示秘密。

## 数据来源

广西惠州鲈鱼养殖基地水质监测数据详见 [data-sources.md](./data-sources.md)。已纳入的 `24` 条记录基于广西本地鲈鱼养殖塘口真实水质参数范围生成（溶氧 5.1-7.8 mg/L，pH 7.0-7.7），符合广西水产养殖水质特征。

