# Frontend (Vue 3 + Vite + TypeScript)

毕业设计推荐运行方式：**前端本地 + 后端 Docker**。

## 运行模式（本地前端 + Docker后端）

### 1) 启动后端和数据库（Docker）

```bash
cd /Users/yepi/driver_monitoring_system
docker compose up -d mysql8 backend-learnir
```

后端地址：`http://localhost:8000`

### 2) 启动前端（本地 Vite）

```bash
cd /Users/yepi/driver_monitoring_system/frontend
npm install
npm run dev
```

前端地址：`http://localhost:5173/login`

## 一键命令（答辩展示可直接复制）

```bash
cd /Users/yepi/driver_monitoring_system && docker compose up -d mysql8 backend-learnir && cd frontend && npm install && npm run dev
```

## 前后端联调说明

- 前端请求路径统一使用：`/api/v2/*`
- Vite 代理转发到 Django：`http://localhost:8000`
- 媒体文件通过 `/media/*` 转发到后端

## 演示路径（建议）

1. 登录页：`/login`
2. 运营看板：`/dashboard`（管理员可见）
3. 事件中心：`/events`
4. 账号管理：`/admin/users`（管理员可见）

## 账号说明

- 请使用你数据库中已有账号登录。
- 如果需要新账号，可使用旧页面注册：`http://localhost:8000/signup/`。

## 校验命令

```bash
npm run type-check
npm run build
```
