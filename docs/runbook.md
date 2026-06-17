# Runbook

本文件记录 min-agent-demo 的运行、验证和排查方式。

## 当前阶段

项目已初始化规则和基础目录，但还没有实现完整 Agent Loop。

## 验证命令

```bash
python3 -m unittest discover -s tests
```

## 占位 CLI

```bash
PYTHONPATH=src python3 -m min_agent.cli "请读取 notes.md 并总结" --workspace examples/workspace
```

## 后续实现顺序

1. FakeLLM 决策规则
2. Agent Loop
3. Tool Registry
4. Workspace read_file 工具
5. Trace Recorder
6. Trace Server
7. Trace Viewer 实时展示
8. 运行记录保存
9. 错误处理和边界测试
