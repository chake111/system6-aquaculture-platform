# 系统六：智慧水产养殖监测与调控平台

本仓库用于实现系统六的应用原型。任务范围来自 `系统6.csv`：采集溶氧、pH、声呐密度与图像数据，分析水质和养殖密度，输出增氧、换水及放流/捕捞建议，并对养殖效益和复杂天气稳定性进行验证。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Element Plus
- 后端：Python 3.12、FastAPI、Uvicorn、SQLAlchemy
- 质量工具：ESLint、Oxlint、Prettier、Vue TypeScript Checker、Vitest、Ruff、Mypy、Pytest

## 目录

```text
frontend/  Vue 单页应用及前端测试/检查配置
backend/   FastAPI 应用及后端测试/检查配置
```

## 开发命令

在项目根目录执行全部检查：

```powershell
npm run check
```

前端：

```powershell
cd frontend
npm install
npm run format:check
npm run lint
npm run type-check
npm run test:unit -- --run
npm run dev
```

后端：

```powershell
cd backend
uv sync
uv run ruff check .
uv run mypy src
uv run pytest
uv run uvicorn aquaculture_api.main:app --app-dir src --reload
```

当前初始化阶段只提供项目工程基线与健康检查接口，水质监测、密度调控和决策输出等业务模块将在后续迭代实现。
