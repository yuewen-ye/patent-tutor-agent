# Patent Tutor 前端

专利智能导学系统的前端应用，采用 React + Vite + TypeScript + Tailwind CSS 构建，深色主题设计，完整对接后端 FastAPI 接口。

## 功能特性

- **深色高级 UI**：以 slate-950 为主背景，青/琥珀/翠绿色作为 Agent 状态强调色。
- **多智能体协同可视化**：使用 React Flow 展示工作流节点与专家 A/B 辩论阶段。
- **实时事件流**：通过 SSE 监听 Agent 执行事件，动态高亮当前节点。
- **学习路径可视化**：交互式路线图、难度曲线、混淆风险面板。
- **学员画像与学情报告**：BKT 掌握度热力图、知识盲区标签、历史会话。
- **三形态课程资源**：定制化讲义、实务操作指南、分级习题。
- **练习反馈闭环**：答题提交后生成反馈会话，动态迭代学习路径。

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env.local
```

编辑 `.env.local`。默认使用 Vite 代理（推荐，无需配置后端 CORS）：

```env
VITE_API_BASE_URL=/api
```

如需直接访问后端，可改为：

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. 启动后端

```bash
uv run python backend/main.py
```

> **使用代理时（默认 `/api`）**：Vite 会自动把前端请求转发到 `http://localhost:8000`，无需配置后端 CORS。
>
> **直接访问后端时**：必须在仓库根目录 `.env` 中配置：
> ```env
> PATENT_TUTOR_CORS_ORIGINS=http://localhost:5173
> ```

### 4. 启动前端开发服务器

```bash
npm run dev
```

打开浏览器访问 `http://localhost:5173`。

### 5. 生产构建

```bash
npm run build
```

构建产物位于 `frontend/dist/`。

## 主要页面

| 页面 | 路径 | 说明 |
|---|---|---|
| 首页 | `/` | 系统介绍、服务状态、快速入口 |
| 入学诊断 | `/onboarding` | 填写问卷并创建 teach 会话 |
| 会话详情 | `/session/:sessionId` | 工作流可视化、Agent 事件、学习路径 |
| 课程学习 | `/course/:sessionId` | 三形态资源展示与练习提交 |
| 反馈报告 | `/feedback/:sessionId` | 答题分析、画像更新、下一步建议 |
| 学员中心 | `/learner/:learnerId` | 画像、掌握度热力图、历史会话 |
| 会话列表 | `/sessions` | 分页会话管理 |
| 快速问答 | `/chat` | chat / diagnose 通用入口 |

## 项目结构

```text
frontend/src/
├── api/              # API 客户端（health、questionnaire、sessions、learners、artifacts）
├── components/       # 业务组件
│   ├── workflow/     # 工作流图、Agent 事件、专家辩论、Judge 面板
│   ├── learning-path/# 学习路径图、难度曲线、混淆风险
│   ├── profile/      # 学员画像、掌握度热力图
│   ├── course/       # 课程资源标签、练习提交
│   ├── layout/       # 页面布局与导航
│   └── ui/           # shadcn/ui 基础组件
├── hooks/            # 自定义 Hooks（SSE 事件）
├── lib/              # 工具函数与问卷解析器
├── pages/            # 页面组件
├── routes/           # 路由配置
├── types/            # TypeScript 类型
└── index.css         # 深色主题与全局样式
```

## 后端接口对接

前端已对接后端全部核心接口：

- `GET /health`、`GET /health/ready`
- `GET /questionnaires/onboarding`
- `POST /learners/:learner_id/questionnaire-responses`
- `POST /sessions`
- `GET /sessions`、`GET /sessions/:id`、`DELETE /sessions/:id`
- `GET /sessions/:id/events/stream`
- `GET /sessions/:id/artifacts/:path`
- `POST /sessions/:course_session_id/exercise-responses`
- `GET /learners/:learner_id`、`/profiles`、`/history`、`/sessions`
