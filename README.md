# Driver Monitoring System

## 快速启动（毕业设计模式）

- 后端和数据库用 Docker
- 前端本地运行（Vite）

```bash
cd /Users/yepi/driver_monitoring_system
docker compose up -d mysql8 backend-learnir
cd frontend
npm install
npm run dev
```

访问：

- 前端：`http://localhost:5173/login`
- 后端：`http://localhost:8000`

## 演示顺序

1. 登录
2. 看板（管理员）
3. 事件中心（筛选 / 复核 / 申诉）
4. 账号管理（管理员）

更多说明见：`frontend/README.md`
