# ClawShell 安装指南

> v1.12.0 | 一云多端云边协同分布式神经系统

## 一键安装

```bash
git clone https://github.com/jorinyang/ClawShell.git ~/.clawshell
cd ~/.clawshell
python3 bin/clawshell install
```

安装向导会交互式引导完成全部配置：

```
  ╔══════════════════════════════════════╗
  ║     ClawShell v1.12.0 Installer     ║
  ╚══════════════════════════════════════╝

  Step 1/5: 自动检测系统 (OS/WSL/Python)
  Step 2/5: 自动发现框架 (Hermes/Wukong/OpenClaw)
  Step 3/5: 配置云枢连接 (URL + 连通性测试)
  Step 4/5: 配置记忆系统 (MemPalace/MemOS)
  Step 5/5: 注入到框架 (MCP配置+Adapter自动注入)
```

## 快速安装（非交互）

```bash
python3 bin/clawshell install --quick
```

使用默认值跳过所有交互提示。

## 预览模式

```bash
python3 bin/clawshell install --dry-run
```

## 安装后

```bash
clawshell status    # 查看Edge+CloudHub状态
```

### Wukong用户
重启Wukong后，对话中直接调用18个clawshell_*工具。

### Hermes用户
对话中直接使用clawshell指令，Skill自动加载。

## 手动配置（高级）

如需手动配置Wukong MCP，参考 `docs/WUKONG_INTEGRATION.md`。
