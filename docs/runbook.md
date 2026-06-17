# Runbook

本文件记录 min-agent-demo 的运行、验证和排查方式。

## 正常运行

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

默认行为：

- 启动本地 Trace Viewer
- 尝试打开浏览器
- 运行 AgentLoop
- 保存 JSON 运行记录到 `runs/`
- 完成后保留 viewer server 5 秒

## 无浏览器运行

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

这个模式适合自动测试和快速验证。

## 验证命令

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
PYTHONPATH=src python3 -m min_agent.cli "请读取 missing.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

预期：

- 单元测试通过
- 成功任务输出 `notes.md` 的摘要
- 缺失文件任务输出 `读取文件失败`
- 两种 CLI 运行都会保存 JSON 记录

## 常见问题

### workspace 不存在

现象：

```text
Error: workspace does not exist: ...
```

处理：

- 检查 `--workspace` 路径是否正确
- 默认从当前命令执行目录解析相对路径

这属于启动配置错误，CLI 返回 `2`。

### workspace 是文件

现象：

```text
Error: workspace is not a directory: ...
```

处理：

- `--workspace` 必须指向目录

这属于启动配置错误，CLI 返回 `2`。

### 文件不存在

命令示例：

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 missing.md 并总结" --workspace examples/workspace --no-viewer --no-browser --step-delay 0
```

预期：

- 程序不崩溃
- 输出包含 `读取文件失败`
- 最新 run record 的 `status` 是 `failed`
- CLI 返回 `0`

缺失文件是 Agent 任务失败，不是程序启动失败。

### 端口被占用

默认 viewer 端口从 `8765` 开始尝试，最多向后尝试 20 个端口。

也可以手动指定：

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace --port 0
```

`--port 0` 表示让操作系统选择空闲端口。

### 浏览器没有自动打开

CLI 会打印 viewer URL：

```text
Trace viewer: http://127.0.0.1:<port>/
```

手动复制这个 URL 到浏览器即可。

### 不想启动 Viewer

使用：

```bash
--no-viewer --no-browser
```

这样不会启动本地 Trace Server，也不会打开浏览器。

## 运行记录

运行记录保存在：

```text
runs/*.json
```

每个记录包含：

- `run_id`
- `status`
- `user_goal`
- `workspace`
- `started_at`
- `ended_at`
- `events`

`events` 中的事件结构与 Trace Viewer 通过 SSE 收到的事件结构一致。

## Workspace 安全边界

文件工具只能读取指定 workspace 内的文件。

会被拒绝的情况包括：

- `../secret.md`
- workspace 外绝对路径
- 指向 workspace 外文件的 symlink
- 目录路径
- 非 UTF-8 文件
