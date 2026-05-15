# ClawShell v1.12.0 Release Notes

> Release Date: 2026-05-15 | 从 v1.8.1 以来的全部变更

---

## 一、交互式安装器 (P20)

**`clawshell install`** — 一条命令完成全部安装配置。

- 5步交互向导：系统检测 → 框架发现 → 云枢连接 → 记忆配置 → 框架注入
- 自动发现 Hermes / Wukong / OpenClaw 框架
- 自动测试云枢连通性
- 自动配置 Wukong MCP (STDIO, 18 tools)
- 自动注入 Hermes Adapter
- 支持 `--quick` (静默) 和 `--dry-run` (预览)
- `clawshell status` 一键状态检查

---

## 二、Edge MCP 服务器 (P11-P12)

### clawshell-edge (15 tools)
- 事件总线: `publish` / `query` / `stats`
- LLM分析: `brain_analyze` / `brain_status`
- 节点管理: `nodes_list` / `nodes_register`
- 任务管理: `tasks_create` / `tasks_list`
- 技能市场: `skills_list`
- 知识库: `vault_search` / `sync_push` / `sync_pull`
- 健康检查: `cloud_health` / `edge_status`

### clawshell-memory (3 tools)
- `memory_search` — 三层搜索 (MemPalace → MemOS Local → MemOS Cloud)
- `memory_store` — 持久化到 MemPalace + 自动推送事件到云枢
- `memory_stats` — 三层统计

### 传输方式
STDIO 而非 streamableHttp — Wukong 按需 spawn wsl 进程，无需守护进程，重启即生效。

---

## 三、云枢能力增强

### CloudBrain LLM 分析 (P17)
- 根因分析: 事件驱动，实时响应 critical error
- 趋势判断: 300s 周期洞察
- 深度复盘: 6h 周期全量分析
- 架构规划: 按需触发
- **记忆复盘**: 新增 `POST /api/v1/brain/review/memories` — 分析端脑记忆事件

### 事件驱动记忆共享 (P17)
- 端脑存储记忆 → 自动推送 `memory.stored` 事件到 EventBus
- CloudBrain 复盘时读取记忆事件，生成知识洞察
- 零轮询开销，使用现有 EventBus 基础设施

### 全局 Router app.state 迁移 (P12)
- 所有路由器统一使用 `request.app.state` 访问引擎
- 修复了 uvicorn worker 中全局变量为 None 的 bug
- 涉及: events, nodes, tasks, skills, brain, insights, broadcasts, reviews, evolution

### skills/stats 端点修复 (P18)
- `/stats` 路由移至 `/{skill_id}` 之前，修复路径冲突

---

## 四、OSS Vault 知识库 (P15)

- 新增 `cloud/routers/vault.py` — 完整 CRUD + 搜索 + 双向同步
- OSS Bucket: `clawshell-vault` (oss-cn-hongkong)
- 端点: `GET/POST/DELETE /api/v1/vault/note/*` + `search` + `sync/push` + `sync/pull`
- hermes_cron optimize 每日 2am 自动执行 Vault 双向同步

---

## 五、MemOS Cloud API 修复 (P16)

发现文档站 `memos-docs.openmem.net` 为 Nuxt SPA，需检查 `__NUXT__` 配置块获取 API 信息。

| 修复项 | 旧值(错误) | 新值(正确) |
|--------|-----------|-----------|
| Auth Header | `Bearer <key>` | `Token <key>` |
| 搜索端点 | `GET /search` | `POST /search/memory` |
| 存储端点 | `POST /memories` | `POST /message` |

搜索已连通 (HTTP 200)，存储需提升 API Key 权限。

---

## 六、MemOS Local Bridge (P14)

- `edge/mcp/memos_local_bridge.py` — 零依赖 Python HTTP 服务，端口 18800
- 直连 MemPalace SQLite (knowledge_graph.sqlite3)
- 提供 `/health` `/api/search` `/api/memories` `/api/stats`

---

## 七、Hermes Cron 定时任务 (P6)

部署于 ECS crontab:

```
*/5 * * * *  insight     快速洞察(事件分析)
0 */6 * * *  review      深度复盘(6h事件+记忆)
0 2 * * *    optimize    日报 + 记忆复盘 + Vault双向同步 + 旧数据清理
```

---

## 八、Bug 修复

| 问题 | 修复 |
|------|------|
| EventBus 时间戳类型不一致 | ingest/query/sort 全部加 string→float 转换 |
| TaskBoard 优先级 int 崩溃 | `_normalize_priority()` 兼容 int→string enum |
| edges_online 始终为 0 | 求和 swarm + capability_registry 计数 |
| MemPalace 路径回退失败 | WSL symlink `~/.mempalace` → Windows 真实路径 |
| MCP stdout 污染 | 删除 `print()` 调试输出 |
| Skills /stats 返回 404 | 路由顺序修复 |
| Vault 端点 404 | 创建完整 Vault Router |

---

## 九、文档

- `docs/INSTALL_BEST_PRACTICES.md` — 安装最佳实践
- `docs/WUKONG_INTEGRATION.md` — Wukong MCP 集成参考
- `docs/REPO_COMPARISON_ANALYSIS.md` — ClawShell vs ClawShell-MacOS 对比分析
- `README.md` — 重写为安装向导风格

---

## 十、新增文件

| 文件 | 说明 |
|------|------|
| `bin/clawshell` | 交互式安装向导 + CLI 入口 |
| `bin/clawshell-edge` | Edge 生命周期管理 |
| `edge/mcp/edge_server.py` | Edge MCP 服务器 (15 tools) |
| `edge/mcp/memory_server.py` | Memory MCP 服务器 (3 tools) |
| `edge/mcp/memos_local_bridge.py` | MemOS 本地桥接 |
| `cloud/routers/vault.py` | OSS Vault REST API |
| `cloud/brain/analyst.py` | CloudBrain LLM 分析引擎 |
| `cloud/services/vault_api.py` | Vault API 服务层 |
| `fc/fc_handler.py` + `fc/template.yml` | 阿里云 FC 函数计算 |
| `hermes_cron.py` | ECS 定时分析任务 |

---

**完整 commit 链**: P5.3 → P6.4 → P8 → P9 → P10 → P11 → P11.1 → P12 → P13 → P14 → P15 → P16 → P16.1 → P17 → P18 → P19 → P19.1 → P20 → P20.1
