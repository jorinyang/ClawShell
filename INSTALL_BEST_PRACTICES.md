# ClawShell 本地安装最佳实践

> 版本: v1.12.0 | 最后更新: 2026-05-15

---

## 架构概览

```
本机 (Windows + WSL)
├── Wukong (Windows) ──→ MCP STDIO ──→ edge_server.py ──→ CloudHub
├── Hermes (WSL)     ──→ Skill/CLI  ──→ edge/ modules  ──→ CloudHub
│
├── ~/.clawshell/              ← 核心仓库 (v1.12.0)
├── ~/.clawshell-edge/         ← Edge配置
├── ~/.mempalace → Windows     ← symlink (关键!)
└── ~/.hermes/skills/clawshell/ ← Hermes技能
```

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
cd ~/.clawshell
pip3 install --break-system-packages psutil requests pyyaml aiohttp
```

### 2. Edge配置

```bash
mkdir -p ~/.clawshell-edge
cat > ~/.clawshell-edge/config.json << 'EOF'
{
  "cloud_url": "http://47.239.71.174",
  "node_id": "edge-wsl-e62505bb",
  "node_name": "Aorus-WSL-Edge",
  "sync_interval": 5,
  "auto_register": true,
  "ecosystem_components": ["hermes", "wukong"],
  "adapters": {
    "hermes": {"enabled": true, "home": "/home/aorus/.hermes"},
    "wukong": {"enabled": true, "home": "/mnt/c/Users/Aorus/.wukong"}
  }
}
EOF
```

### 3. MemPalace symlink (关键!)

Wukong通过`wsl` spawn MCP进程时env变量传递不可靠，必须创建symlink确保回退路径有效：

```bash
ln -sf /mnt/c/Users/Aorus/.mempalace ~/.mempalace
```

### 4. MemOS Local Bridge

```bash
python3 ~/.clawshell/edge/mcp/memos_local_bridge.py &
```
端口18800，提供本地记忆HTTP API。

### 5. Wukong MCP配置

配置文件: `C:\Users\Aorus\.real\users\{user-id}\.mcp\mcpServerConfig.json`

```json
{
  "clawshell-edge": {
    "isActive": true,
    "name": "ClawShell边缘端脑",
    "type": "stdio",
    "timeout": 120,
    "command": "wsl",
    "args": ["-d","Ubuntu","--","bash","-c",
             "cd /home/aorus/.clawshell && python3 -m edge.mcp.edge_server"],
    "env": {
      "CLAWSHELL_CLOUD_URL": "http://47.239.71.174",
      "CLAWSHELL_EDGE_HOME": "/home/aorus/.clawshell-edge",
      "CLAWSHELL_REPO": "/home/aorus/.clawshell",
      "CLAWSHELL_NODE_ID": "edge-wsl-e62505bb"
    }
  },
  "clawshell-memory": {
    "isActive": true,
    "name": "统一记忆系统",
    "type": "stdio",
    "timeout": 60,
    "command": "wsl",
    "args": ["-d","Ubuntu","--","bash","-c",
             "cd /home/aorus/.clawshell && PYTHONPATH=/home/aorus/.clawshell python3 -m edge.mcp.memory_server"],
    "env": {
      "MEMPALACE_PATH": "/mnt/c/Users/Aorus/.mempalace",
      "PYTHONPATH": "/home/aorus/.clawshell",
      "MEMOS_CLOUD_URL": "https://memos.memtensor.cn/api/openmem/v1",
      "MEMOS_CLOUD_USER_ID": "1062695814-580275369",
      "MEMOS_CLOUD_API_KEY": "mpg-Mr09NiR01Am1nBcXML21S5Kirm6dVYGsVSTxuNEQ",
      "MEMOS_LOCAL_URL": "http://127.0.0.1:18800"
    }
  }
}
```

### 6. Hermes集成

```bash
# 自动注入 (由adapter完成)
python3 -c "
import sys, json
sys.path.insert(0, '/home/aorus/.clawshell')
from edge.adapters.hermes_adapter import HermesAdapter
cfg = json.load(open('/home/aorus/.clawshell-edge/config.json'))
HermesAdapter(config_path='/home/aorus/.hermes').inject(config=cfg)
"
```

### 7. CLI工具

```bash
ln -sf ~/.clawshell/bin/clawshell-edge ~/.local/bin/clawshell-edge
clawshell-edge status
```

## 验证清单

| 检查项 | 命令 | 预期 |
|--------|------|------|
| Edge MCP init | `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \| python3 ~/.clawshell/edge/mcp/edge_server.py` | serverInfo: clawshell-edge v1.12.0 |
| MemOS Local | `curl http://127.0.0.1:18800/health` | healthy, uptime > 0 |
| Wukong MCP | 重启Wukong→对话中调用clawshell_cloud_health | 12 engines active |
| Hermes adapter | `python3 -c "from edge.adapters.hermes_adapter import HermesAdapter; print(HermesAdapter().detect())"` | True |
| CloudHub | `curl http://47.239.71.174/health` | healthy, 12 engines |

## 常见问题

### MCP工具不可见
Wukong必须**完全退出并重新启动**才能加载新MCP配置。检查任务管理器中wukong进程。

### 记忆存储返回stored_to: []
`~/.mempalace` symlink丢失或指向错误。运行:
```bash
ls -la ~/.mempalace
# 应显示: /home/aorus/.mempalace -> /mnt/c/Users/Aorus/.mempalace
```

### STDIO timeout
增大Wukong MCP配置中的timeout到120s。wsl冷启动约需500ms。

### edges_online = 0
MCP按需模式无长驻心跳，节点在Wukong调用时自动注册。需持续在线则启动edge daemon:
```bash
clawshell-edge start
```
