# ClawShell v1.11.0 Release Notes

> **一云多端云边协同分布式神经系统**
> 版本: v1.11.0 | 测试: 573/573 passed | 模块: 109 Python files
> 仓库: github.com/jorinyang/ClawShell

---

## 版本演进总览

```
v1.8.1 → v1.9.0 → v1.10.0 → v1.11.0
 (基线)   (设计)    (功能)    (架构)

+28 files changed, +3,159 LOC
573 comprehensive tests, 0 failures (22 categories)
```

---

## v1.9.0 — 设计基础夯实

### Pydantic v2 类型体系 (`shared/models.py`)
- 16+ Pydantic v2 模型: NodeInfo, EventMessage, Insight, Task, Knowledge, Memory, Plugin, HealthReport, RepairAction, SwarmNode 等
- 10 个枚举类: Strategy, HealthStatus, RepairLayer, TrustLevel, EventCategory, EventPriority, TaskStatus, CapabilityDomain, PerceptionDimension, OpenClawVariant
- 所有模型提供 `to_legacy_dict()` 向后兼容方法
- 来源: DEEP 设计 + MacOS v2.1 适配参考

### InsightEngine 洞察引擎 (`cloud/engines/insight.py`)
- 实时事件流分析: 错误风暴检测 (5+ errors → alert)
- 周期性摘要: 每 5 分钟自动生成事件统计
- 模式分析: 3+ 节点离线 → 异常告警
- 知识提取: actionable insights → Knowledge 条目
- 与 EvolutionEngine 协同: Insight(实时) → PatternMiner(中期) → AutoSkillPublisher(长期)
- 来源: DEEP InsightEngine → MacOS v2.1 InsightDomain → Main cloud engine

### PluginManager 插件管理 (`edge/ecosystem/plugin_manager.py`)
- 5 内置插件: N8N, MemOS, ComfyUI, Ollama, OpenClaw Skills
- YAML 自定义插件发现 (`plugin.yaml`)
- HTTP/TCP 健康检查
- 启用/禁用/查询 API
- 来源: DEEP PluginManager → MacOS v2.1 PluginDomain → Main edge/ecosystem

### PID 反馈控制回路 (`exoskeleton/layer2/feedback_loop.py`)
- 控制论 PID: kp=0.5, ki=0.1, tolerance=0.1
- 收敛检测: 连续 3 次偏差在容忍范围 → is_stable
- PI 控制器公式: signal = kp*deviation + ki*deviation*min(iterations,10)
- 输出范围: [-1.0, 1.0]
- 来源: DEEP FeedbackControlLoop → Main threading 模型适配

### StrategySwitcher 状态机 (`exoskeleton/layer2/strategy.py`)
- 5 策略: DEFAULT, EMERGENCY, ECONOMY, AGGRESSIVE, CONSERVATIVE
- TRANSITIONS 转移表: 定义合法状态转移
- auto_evaluate(health_score, resource_pressure) → 自动触发策略切换
- 触发规则: health<0.3→EMERGENCY, pressure>0.8→ECONOMY, recovery→DEFAULT
- 来源: DEEP StrategySwitcher → Main L2 自适应层

### PriorityHeap EventBus 升级 (`cloud/engines/eventbus.py`)
- heapq 优先级堆: CRITICAL(100) > HIGH(80) > NORMAL(50) > LOW(0)
- 3 级 Pub/Sub 路由: event_type → category.* → *
- 显式 TTL 过期检查
- subscribe()/publish()/pop_priority() 新 API
- runtime_stats 属性: queue_size, processed, dropped, subscribers
- 完全向后兼容: 现有 ingest/query API 不变

---

## v1.10.0 — 功能矩阵完善

### SemanticSearch 语义搜索 (`cloud/services/semantic_search.py`)
- 关键词评分搜索: title 权重 > content
- KnowledgeGraph 实体关联增强
- 搜索结果带 score 排序
- 来源: MacOS v2.0 semantic_search.py

### RelationEngine 关系引擎 (`cloud/services/relation_engine.py`)
- 实体关系管理: add_relation(source, target, type, weight)
- BFS 遍历: find_related(max_depth=2, min_weight=0.3)
- 反向关系查询: get_reverse_relations()
- 共现推断: infer_co_occurrence(shared tags/category)
- 来源: MacOS v2.0 relation_engine.py

### MemoryStore 时间衰减 (`storage/memory_store.py`)
- 重要性加权召回: score = importance*10 + query_match*5 + category*3 + tag*2
- 30 天衰减公式: score *= max(0.1, 1.0 - age_hours / (24*30))
- JSON 文件持久化 + LRU 淘汰 (MAX=5000)
- 访问计数追踪 + TTL 支持
- 来源: DEEP MemoryStore

### RepairEscalation 3 层修复升级 (`exoskeleton/layer2/repair_escalation.py`)
- 升级链: SELF_HEALING(3次失败) → AUTO_REPAIR(2次失败) → MANUAL
- 默认修复动作: memory_high→clear_cache, cpu_high→reduce_load, disk_full→clean_temp
- 成功重置计数器
- 来源: DEEP repair escalation

### SharedConfig 3 级配置 (`shared/config.py`)
- 优先级: ENV > YAML file > defaults
- 密钥自动脱敏 (token/key/secret/password → ***)
- 来源: MacOS v2.1 shared/config.py

### loguru 日志体系 (`shared/logging_setup.py`)
- loguru 主日志 + 标准 logging 桥接
- 彩色控制台输出: 时间 | 级别 | 模块:函数 - 消息
- 来源: MacOS v2.1 loguru_setup.py

---

## v1.11.0 — 架构升级 + 部署增强

### PubSubManager 实时推送 (`cloud/pubsub/manager.py`)
- WebSocket 实时事件广播 (替代 HTTP 轮询)
- 离线队列: 断线节点事件缓存 + reconnect 后 flush
- 心跳检测: 30s interval, 90s timeout 自动清理
- fnmatch 模式订阅: task.*, error.*, *
- 来源: MacOS v2.0 PubSubManager

### NicheMatcher 生态位匹配 (`exoskeleton/layer4/niche_matcher.py`)
- 三维评分: capability*0.4 + load*0.3 + trust*0.3
- find_best_node(): 多节点最优匹配
- NicheMatcher.match(): 排序结果列表
- 可自定义权重
- 来源: DEEP 生态位匹配算法

### MetadataIndex 元数据索引 (`cloud/eventing/metadata_index.py`)
- 时间桶索引: 按小时分桶，支持时间范围快速查询
- 分类索引: category → [event_ids]
- 来源索引: source → [event_ids]
- 7 天自动清理
- 来源: MacOS v2.0 metadata_index.py

### GitHub Adapter (`cloud/adapters/github.py`)
- GitHub API 集成: 文件读写、Issue 管理
- suggest_optimizations(): 大文件/TODO 检测
- Bearer Token 认证
- 来源: DEEP GitHub adapter

### FC 函数计算部署 (`deploy/cloud/fc/template.yml`)
- 阿里云 ROS 模板: InsightGenerator + EventBatchProcessor
- Serverless 部署: 零闲置成本，自动扩缩

### CI/CD 配置 (`.github/workflows/ci.yml`)
- ruff 代码检查 + mypy 类型检查
- Python 3.10/3.11/3.12 矩阵测试
- 综合测试 + pytest

---

## 最终统计

| 指标 | v1.8.1 | v1.11.0 | 增量 |
|------|:---:|:---:|:---:|
| Python 文件 | 91 | 109 | +18 |
| 代码行数 | 7,888 | ~11,047 | +3,159 |
| 测试用例 | 412 | 573 | +161 |
| 测试类别 | 12 | 22 | +10 |
| 云引擎 | 12 | 13 | +InsightEngine |
| CloudHub 端点 | 14+ | 14+ | 不变 |
| 外部集成 | 3 | 4 | +GitHub |

---

## 部署检查清单

- [x] 573/573 全量测试通过
- [x] main 分支合并完成
- [ ] GitHub push + Release 创建
- [ ] Docker 镜像构建 (deploy/cloud/Dockerfile)
- [ ] FC 函数部署 (deploy/cloud/fc/template.yml)
- [ ] 阿里云 ECS 更新 (Terraform apply)
- [ ] 端侧更新 (install.sh)
