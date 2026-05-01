# MemPalace ONNX 模型配置最佳实践

> 本文档记录了 MemPalace + ChromaDB ONNX 向量模型配置的完整过程，包括问题排查、解决方案和验证方法。

## 问题背景

MemPalace v3.3.4 使用 ChromaDB 作为向量数据库后端，需要配置 ONNX 格式的 embedding 模型才能启用语义搜索功能。

### 常见问题

1. **HuggingFace 下载链接失效**
   - 原链接：`https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/onnx.tar.gz`
   - 状态：文件已不存在，返回 `Entry not found`

2. **代理下载缓慢且经常中断**
   - 通过代理下载 HuggingFace 文件，速度约 10-20 kiB/s
   - 470MB 的 `paraphrase-multilingual-MiniLM-L12-v2` 下载需要数小时

3. **用户手动下载的 model.onnx 格式不兼容**
   - ChromaDB 的 `ONNXMiniLM_L6_V2` 期望的是 `onnx.tar.gz` 打包格式
   - 单独的 `model.onnx` 文件虽然大小接近，但结构不同，无法被加载

## 解决方案

### 核心发现

通过分析 ChromaDB 源码（位于 `chromadb/utils/embedding_functions/onnx_mini_lm_l6_v2.py`），找到了官方 S3 下载地址：

```
https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz
```

这是 ChromaDB 官方维护的模型文件，SHA256 校验值：`913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3`

### 方案对比

| 方案 | 模型 | 大小 | 中文支持 | 稳定性 |
|------|------|------|----------|--------|
| **推荐** | all-MiniLM-L6-v2 (官方S3) | 79MB | 一般 | 稳定 |
| 备选 | paraphrase-multilingual-MiniLM-L12-v2 | 470MB | 良好 | 需手动配置 |
| 不推荐 | bge-large-zh-v1.5 (PyTorch) | 1.2GB | 优秀 | 格式不兼容 |

## 详细步骤

### 步骤 1：下载 ONNX 模型

#### 方法 A：通过 Python 脚本下载（推荐）

```python
import requests
import os

url = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
cache_dir = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2")
os.makedirs(cache_dir, exist_ok=True)
output_path = os.path.join(cache_dir, "onnx.tar.gz")

print(f"下载到: {output_path}")
r = requests.get(url, stream=True)
total = int(r.headers.get("content-length", 0))
print(f"文件大小: {total / 1024 / 1024:.1f} MB")

with open(output_path, "wb") as f:
    downloaded = 0
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
            print(f"\r下载进度: {downloaded / total * 100:.1f}%", end="", flush=True)
print("\n下载完成")
```

#### 方法 B：通过命令行下载

```bash
# 使用 curl
curl -L -o ~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx.tar.gz \
  https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz

# 使用 wget
wget -O ~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx.tar.gz \
  https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz
```

### 步骤 2：验证文件完整性

```python
import hashlib

expected_sha256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
file_path = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx.tar.gz")

sha256_hash = hashlib.sha256()
with open(file_path, "rb") as f:
    for byte_block in iter(lambda: f.read(4096), b""):
        sha256_hash.update(byte_block)

actual_hash = sha256_hash.hexdigest()
if actual_hash == expected_sha256:
    print("✅ SHA256 验证通过")
else:
    print(f"❌ SHA256 验证失败: {actual_hash}")
```

### 步骤 3：验证模型加载

```python
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
import numpy as np

# 初始化 embedding function
ef = ONNXMiniLM_L6_V2()

# 测试编码
result = ef(["这是一个中文测试句子", "hello world"])

# 验证结果
print(f"向量维度: {result[0].shape[0]}")
print(f"预期维度: 384")
assert result[0].shape[0] == 384, "向量维度不匹配"
print("✅ ONNX 模型加载成功")
```

### 步骤 4：验证 MemPalace 功能

```python
import sys
sys.path.insert(0, r"C:\Users\Aorus\.ClawShell")

from lib.bridge.mempalace_bridge import MemPalaceBridge

# 初始化 Bridge
bridge = MemPalaceBridge(palace_dir=r"C:\Users\Aorus\.mempalace\clawshell")
ok = bridge.init()

print(f"Bridge 初始化: {'成功' if ok else '失败'}")
print(f"is_ready: {bridge.is_ready()}")

# 健康检查
health = bridge.health_check()
print(f"健康状态: {health}")
```

## 验证命令汇总

快速验证 MemPalace 配置的完整命令：

```powershell
C:\path\to\python.exe -c "
import sys
sys.path.insert(0, r'C:\Users\Aorus\.ClawShell')

# 1. ONNX 模型
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
ef = ONNXMiniLM_L6_V2()
r = ef(['test'])
print('ONNX OK, dim=', r[0].shape[0])

# 2. MemPalace Bridge
from lib.bridge.mempalace_bridge import MemPalaceBridge
b = MemPalaceBridge()
b.init()
print('Bridge ready:', b.is_ready())
h = b.health_check()
print('Health:', h)
"
```

## 文件路径参考

| 用途 | 路径 |
|------|------|
| ONNX 模型缓存 | `C:\Users\<用户名>\.cache\chroma\onnx_models\all-MiniLM-L6-v2\` |
| 模型压缩包 | `C:\Users\<用户名>\.cache\chroma\onnx_models\all-MiniLM-L6-v2\onnx.tar.gz` |
| 解压后模型 | `C:\Users\<用户名>\.cache\chroma\onnx_models\all-MiniLM-L6-v2\onnx\model.onnx` |
| MemPalace 数据 | `C:\Users\<用户名>\.mempalace\clawshell\` |
| 知识图谱 | `C:\Users\<用户名>\.mempalace\clawshell\knowledge_graph.sqlite3` |
| ChromaDB 数据 | `C:\Users\<用户名>\.mempalace\clawshell\chroma.sqlite3` |

## 已知限制

1. **中文语义效果一般**
   - `all-MiniLM-L6-v2` 主要优化英文，对中文支持有限
   - 如需更好中文效果，可考虑 `paraphrase-multilingual-MiniLM-L12-v2`（需手动配置）

2. **Genome 模块导入问题**
   - ClawShell 核心模块 `lib.core.genome.Genome` 可能导入失败
   - 不影响 MemPalace 核心功能，仅 Bridge 的 Genome 同步不可用

## 故障排查

### 问题：ONNXMiniLM_L6_V2 初始化超时

**原因**：正在尝试从网络下载模型文件

**解决**：
1. 确认 `onnx.tar.gz` 文件存在于正确路径
2. 验证文件大小（约 79.3MB）
3. 检查 SHA256 校验值

### 问题：向量维度不匹配

**原因**：使用了错误的模型文件

**解决**：
1. 删除不完整的缓存文件
2. 重新下载 `onnx.tar.gz`
3. 删除 `onnx` 子目录（如果存在），让 ChromaDB 重新解压

### 问题：MemPalace Bridge 初始化失败

**原因**：Palace 目录不存在或无权限

**解决**：
1. 确认目录存在：`C:\Users\<用户名>\.mempalace\clawshell\`
2. 检查写入权限
3. 手动创建目录

## 相关文档

- [MemPalace 官方文档](https://github.com/MemPalace/mempalace)
- [ChromaDB ONNX Models](https://docs.trychroma.com/guides/onnx)
- [Sentence Transformers](https://www.sbert.net/)

## 更新日志

- **2026-05-02**: 初版创建，记录 all-MiniLM-L6-v2 配置过程
