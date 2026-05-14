# ClawShell Wukong 接入配置文档

> 版本: v1.12.0 | 日期: 2026-05-14

---

## 一、MCP 服务器配置 (clawshell-edge)

### 基本信息

| 项目 | 值 |
|------|-----|
| **名称** | ClawShell边缘端脑 |
| **MCP Key** | `clawshell-edge` |
| **传输类型** | **STDIO** (标准输入输出) |
| **命令** | `wsl` |
| **超时** | 120s |

### 为什么用 STDIO 而非 streamableHttp？

`streamableHttp` 需要预先运行一个守护进程（端口17655），重启后可能丢失。**STDIO** 由 Wukong 按需启动进程，无需守护进程，更稳定可靠。

### Wukong MCP 配置文件路径

```
C:\Users\Aorus\.real\users\{user-id}\.mcp\mcpServerConfig.json
```

### 完整配置内容

```json
{
  "clawshell-edge": {
    "isActive": true,
    "name": "ClawShell边缘端脑",
    "type": "stdio",
    "timeout": 120,
    "isBuiltin": false,
    "isRemovable": true,
    "command": "wsl",
    "args": [
      "-d", "Ubuntu", "--", "bash", "-c",
      "cd /home/aorus/.clawshell && python3 -m edge.mcp.edge_server"
    ],
    "env": {
      "CLAWSHELL_CLOUD_URL": "http://47.239.71.174",
      "CLAWSHELL_EDGE_HOME": "/home/aorus/.clawshell-edge",
      "CLAWSHELL_REPO": "/home/aorus/.clawshell",
      "CLAWSHELL_NODE_ID": "edge-wsl-e62505bb"
    }
  }
}
```

### 提供的 Tools (8个)

| Tool 名称 | 功能 |
|-----------|------|
| `clawshell_eventbus_publish` | 发布事件到 CloudHub EventBus |
| `clawshell_eventbus_query` | 查询事件(按类型/来源/时间过滤) |
| `clawshell_eventbus_stats` | EventBus 统计(总数/类型分布/来源分布) |
| `clawshell_sync_push` | 推送本地 Obsidian Vault → 阿里云 OSS |
| `clawshell_sync_pull` | 从 OSS 拉取 Vault → 本地 |
| `clawshell_edge_status` | Edge 端脑状态 |
| `clawshell_cloud_health` | CloudHub 云枢健康检查 |
| `clawshell_vault_search` | 全文搜索 Obsidian 知识库 |

---

## 二、MCP 服务器配置 (clawshell-memory)

### 基本信息

| 项目 | 值 |
|------|-----|
| **名称** | 统一记忆系统 |
| **MCP Key** | `clawshell-memory` |
| **传输类型** | **STDIO** |
| **命令** | `wsl` |
| **超时** | 60s |

### 完整配置内容

```json
{
  "clawshell-memory": {
    "isActive": true,
    "name": "统一记忆系统",
    "type": "stdio",
    "timeout": 60,
    "isBuiltin": false,
    "isRemovable": true,
    "command": "wsl",
    "args": [
      "-d", "Ubuntu", "--", "bash", "-c",
      "cd /home/aorus/.clawshell && PYTHONPATH=/home/aorus/.clawshell python3 -m edge.mcp.memory_server"
    ],
    "env": {
      "MEMPALACE_PATH": "/mnt/c/Users/Aorus/.mempalace",
      "MEMOS_CLOUD_URL": "https://memos.memtensor.cn/api/openmem/v1",
      "MEMOS_CLOUD_USER_ID": "1062695814-580275369",
      "MEMOS_CLOUD_API_KEY": "mpg-Mr09NiR01Am1nBcXML21S5Kirm6dVYGsVSTxuNEQ",
      "MEMOS_LOCAL_URL": "http://127.0.0.1:18800",
      "PYTHONPATH": "/home/aorus/.clawshell"
    }
  }
}
```

### 提供的 Tools (3个)

| Tool 名称 | 功能 |
|-----------|------|
| `clawshell_memory_search` | 跨三层记忆搜索(MemPalace→MemOS Local→MemOS Cloud) |
| `clawshell_memory_store` | 存储记忆到 MemPalace + MemOS Cloud |
| `clawshell_memory_stats` | 三层记忆系统统计 |

---

## 三、生效方式

1. 修改 `mcpServerConfig.json` 后
2. **完全关闭并重启 Wukong**
3. 在 Wukong 对话中验证: 工具列表应出现 `clawshell_*` 系列工具

### 验证命令 (在 Wukong 中)

```
使用 clawshell_cloud_health 检查 CloudHub 状态
使用 clawshell_edge_status 查看 Edge 状态
使用 clawshell_eventbus_stats 查看事件统计
使用 clawshell_memory_search 搜索记忆中的关键词 "ClawShell"
```

---

## 四、故障排除

| 问题 | 原因 | 解决 |
|------|------|------|
| Wukong 看不到 clawshell 工具 | 重启不完整 | 完全退出Wukong进程后重新启动 |
| STDIO timeout | wsl 启动慢 | 增大 timeout 到 120s |
| MemPalace 无结果 | 路径错误 | 确认 MEMPALACE_PATH 为 `/mnt/c/Users/Aorus/.mempalace` |
| CloudHub 不可达 | ECS 关闭 | 检查 `http://47.239.71.174/health` |
