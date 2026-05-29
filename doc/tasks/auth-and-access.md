# 认证与权限模块最小任务

> 模块范围：`FR-01`、`FR-02` 的应用外壳与现场登录交互、`FR-11` 的身份和权限基础；支撑 `AT-01`、`AT-02`。
> 实施顺序：本模块为其他业务模块的前置依赖，先建立 API、数据库、审计和前端路由基线。

**完成定义：** 三类测试账号可登录并只能访问授权菜单/API；关键认证操作产生审计记录；离线授权仅允许只读缓存能力；移动端登录和导航具备网络状态、高对比和大按钮交互。

## 计划文件

| 类型 | 路径 | 职责 |
| --- | --- | --- |
| 后端新增 | `backend/src/aquaculture_api/core/{config,errors,security,audit}.py` | 配置、统一错误/追踪、令牌、审计上下文 |
| 后端新增 | `backend/src/aquaculture_api/persistence/{database,orm_models}.py` | 数据库会话；`bases`、`ponds`、`users`、`user_scopes`、`audit_logs` 最小模型 |
| 后端新增 | `backend/src/aquaculture_api/schemas/{auth,master_data}.py` | 登录、当前用户、鱼塘摘要请求响应 |
| 后端新增 | `backend/src/aquaculture_api/services/auth_service.py` | 登录、刷新、离线授权、数据范围计算 |
| 后端新增 | `backend/src/aquaculture_api/api/dependencies.py`、`api/routers/{auth,ponds}.py` | 身份/范围依赖和 `/api/v1` API |
| 后端修改 | `backend/src/aquaculture_api/main.py` | 注册路由、错误处理和追踪中间件，保留 `/api/health` |
| 前端新增 | `frontend/src/api/{client,auth}.ts`、`frontend/src/types/{api,domain}.ts` | 请求封装和认证类型 |
| 前端新增 | `frontend/src/stores/{auth,connectivity}.ts`、`frontend/src/router/guards.ts`、`frontend/src/services/speech.ts` | 会话、在线状态、路由保护和语音能力封装 |
| 前端新增 | `frontend/src/views/{LoginView,DashboardView}.vue`、`frontend/src/components/{layout,common}/` | 登录、应用壳和现场操作组件 |
| 前端修改 | `frontend/src/App.vue`、`frontend/src/router/index.ts` | 路由出口与首批页面路由 |
| 测试新增/修改 | `backend/tests/{unit,api}/test_auth*.py`、`frontend/src/__tests__/{auth,router,LoginView}.spec.ts` | 认证、范围隔离和页面交互验证 |

## Checklist

### A01 API 与数据库基线

- [ ] 创建配置、数据库会话、统一错误响应和 `X-Trace-Id` 中间件，将 API 根路径约定为 `/api/v1`，并保持 `GET /api/health` 响应不变。
- [ ] 定义 `bases`、`ponds`、`users`、`user_scopes`、`audit_logs` 最小 ORM 模型，包含 UUID、UTC 时间、基地/鱼塘范围和审计追踪字段。
- [ ] 提供测试数据库 fixture 与三类角色测试种子数据：养殖户、技术员、管理员各至少一个账号，且包含两个基地以验证越权拒绝。
- [ ] 编写 API 测试，验证健康检查仍可用、未认证访问受保护接口返回统一 `401` 错误和追踪标识。

### A02 登录、令牌与离线授权

- [ ] 为 `AuthService` 实现手机号凭据校验、访问令牌/刷新令牌签发、禁用账号拒绝和登录成功/失败审计。
- [ ] 实现 `POST /api/v1/auth/login`、`POST /api/v1/auth/refresh` 和 `GET /api/v1/me`，响应只返回角色及授权摘要，不返回凭据哈希。
- [ ] 实现 `POST /api/v1/auth/offline-grants`：授权包包含范围、到期时间和签名，最长有效期 7 天，并禁止承载规则维护、真实控制、导出和归档权限。
- [ ] 编写测试覆盖有效登录、错误凭据、禁用用户、过期刷新令牌、离线授权权限收缩以及对应审计事件。

### A03 权限范围与最小主数据查询

- [ ] 实现当前用户、角色要求和 `base_id`/`pond_id` 数据范围依赖，使 repository 查询必须接受已授权范围。
- [ ] 实现 `GET /api/v1/ponds`，供三类用户获取其可访问鱼塘摘要；管理员数据也按已配置授权范围返回。
- [ ] 编写权限矩阵 API 测试：F/T/A 可查看授权鱼塘，普通用户不能访问其他基地，匿名和边缘身份不能调用用户页面 API。

### A04 前端应用壳与现场登录

- [ ] 实现 HTTP client 的 Bearer 注入、错误映射和追踪标识读取；实现 `authStore` 登录、退出、恢复有效离线授权动作。
- [ ] 创建 `/login` 与 `/dashboard` 路由、路由守卫和按角色过滤的导航壳；未登录跳转登录页，无权限菜单不渲染。
- [ ] 在登录页和应用壳加入在线/离线状态提示、高对比模式入口与满足触控操作的大尺寸主要按钮；离线视图明确展示授权有效期。
- [ ] 封装语音输入/关键风险播报服务，在浏览器不支持或识别失败时退回文本/按钮操作，并显式提示用户当前输入方式。
- [ ] 创建组件测试，验证登录提交状态、角色菜单裁剪、路由拒绝、离线提示、高对比切换以及语音失败回退。

### A05 模块验收

- [ ] 运行 `npm run backend:test -- tests/api/test_auth.py tests/api/test_authorization.py`，确认登录、审计与跨基地拒绝用例通过。
- [ ] 运行 `npm run frontend:test -- src/__tests__/auth.spec.ts src/__tests__/router.spec.ts src/__tests__/LoginView.spec.ts`，确认认证页面及路由行为通过。
- [ ] 运行 `npm run backend:lint && npm run backend:type-check && npm run frontend:lint && npm run frontend:type-check`，修复本模块引入的静态检查问题。
- [ ] 使用 F、T、A 三个测试账号手动验证登录、菜单差异、语音输入/播报回退、离线标识和退出流程，并在审计接口或测试断言中确认事件存在。

## 接口交付

完成本模块后，后续模块可依赖：认证请求依赖、范围过滤上下文、审计写入接口、可访问鱼塘列表、前端登录会话和通用布局组件。
