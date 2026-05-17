# ClawShell v2.1.1 — MemPalace 混合搜索集成

> 📅 2026-05-17 | 🏷️ 类型: PATCH | 🔖 基于 v2.1.0

本版本将 MemPalace 的 BM25 + Vector 混合搜索能力集成到端脑记忆系统，提升中文搜索精度和检索质量。

---

## 🔧 改进清单

### 1. 端脑 MemPalace 桥接模块 (新增)

`edge/mcp/mempalace_bridge.py` — 将 MemPalace 混合搜索能力集成到 ClawShell 端脑。

**架构**:
```
ClawShell Edge (端脑)
  └── memory_server.py (MCP STDIO)
      └── mempalace_bridge.py (桥接)
          └── mempalace package (pip)
              ├── searcher.py — BM25 + hybrid rank
              ├── layers.py — 4-layer memory stack
              └── config.py — configurable weights
```

**三种搜索模式**:
- `search_hybrid()` — BM25 + Vector 混合排序
- `search_context()` — 上下文注入 (wake-up / L3 search)
- `get_stats()` — 包含搜索引擎类型和权重配置

**向后兼容**: MemPalace 未安装时自动回退到 SQLite LIKE 搜索。

### 2. memory_server.py 升级

- `search_mempalace()`: 从 SQLite LIKE 升级到 BM25 + Vector 混合搜索
- `tool_memory_stats()`: 返回搜索引擎类型 (hybrid/sqlite_like) 和权重配置
- 版本号: v1.12.0 → v2.1.1

### 3. MemPalace 搜索优化 (上游)

在 `~/workspace/mempalace-dev` 中实现并部署到本地:

| 文件 | 改动 | 效果 |
|------|------|------|
| `searcher.py` | CJK bigram 分词 | 中文搜索精确匹配 |
| `layers.py` | Layer3 集成 `_hybrid_rank` | 深度搜索 BM25+Vector |
| `config.py` | 可配置权重 | env/config.json 调优 |

**CJK 分词效果**:
```
"系统架构" → ["系统架构", "系统", "统架", "架构"]
"Python系统架构" → ["python", "系统架构", "系统", "统架", "架构"]
```

---

## 📊 搜索质量对比

| 查询类型 | v2.1.0 (SQLite LIKE) | v2.1.1 (Hybrid) |
|----------|----------------------|-----------------|
| 英文精确匹配 | ❌ 无法匹配 | ✅ BM25 精确匹配 |
| 中文关键词 | ❌ LIKE 全文扫描 | ✅ CJK bigram 索引 |
| 语义相似 | ⚠️ 仅知识图谱 | ✅ Vector 语义搜索 |
| 混合查询 | ❌ 单一路径 | ✅ BM25 + Vector 融合 |

---

## 📁 变更文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `edge/mcp/mempalace_bridge.py` | 新增 | MemPalace 混合搜索桥接 |
| `edge/mcp/memory_server.py` | 修改 | 集成桥接模块 |
| `CLAWSHELL_VERSION` | 修改 | v2.1.0 → v2.1.1 |

---

## ⬆️ 升级指南

```bash
# 更新 ClawShell
git pull origin main

# 确保 MemPalace 已安装并优化
pip install mempalace
# 优化版本位于 ~/workspace/mempalace-dev
```

无配置变更，无破坏性修改。MemPalace 未安装时自动回退。
