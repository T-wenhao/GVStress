# GVStress

GigE Vision 压力测试与监控框架，用于验证相机流在负载下的稳定性。

## 概述

GVStress 已从单纯的 CLI 压测工具扩展为轻量 Web 监控平台。它可以模拟
GigE Vision 相机流、检查被测设备 (DUT)、运行 smoke/soak/baseline 场景、
暴露 GVStress 自定义指标，并浏览结构化测试报告。

它包含：

- **Fakecam 工作进程**：使用 Aravis 生成合成 GigE Vision 视频流
- **DUT 探针**：采集 NIC 统计、系统指标和流健康状态
- **Node 命令**：查看本机节点健康状态、能力和完整状态
- **Controller 服务**：保存任务状态，并提供轻量 HTTP API
- **Web 监控 UI**：查看节点、任务、报告，并提供 Prometheus 兼容的
  `/metrics` 端点
- **结构化报告**：保存运行产物、摘要报告和判定归因
- **部署资产**：支持 native/systemd 运行，以及 Docker Compose 下的
  Prometheus/Grafana 监控栈
- **远程 DUT 支持**：通过 SSH 支持真实单节点、双节点和多节点拓扑

## 安装

```bash
pip install -e .
```

### 依赖项

- Python 3.10+
- Aravis 库（用于 fakecam 工作进程）
- ethtool（用于 NIC 预检）
- DUT 节点 SSH 访问权限（用于远程场景）
- Linux pktgen、root 或 CAP_NET_ADMIN（用于 pktgen 硬件验证）
- Docker Compose、Prometheus、Grafana、node_exporter（用于可选监控栈）

`ruff`、`mypy` 等质量工具属于可选开发依赖。需要运行时，请优先使用隔离的
conda、virtualenv 或容器环境，不要直接安装到系统 Python。

## 快速开始

### 1. 验证本地服务命令

```bash
python -m gvstress --help
python -m gvstress node health --json
python -m gvstress node capabilities --json
```

### 2. 配置 Fakecam

启动模拟相机：

```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

检查状态：

```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

### 3. 验证 DUT 就绪状态

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### 4. 运行测试场景

冒烟测试：

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

老化测试：

```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

### 5. 查看报告

查看最近一次运行：

```bash
python -m gvstress report show --latest --source artifacts/smoke/runs
```

导出运行数据：

```bash
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output exported-run.json
```

### 6. 启动 Controller 和 Web UI

启动控制 API：

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

启动 Web 监控 UI：

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

常用本地端点：

- `http://localhost:8079/health`
- `http://localhost:8079/api/jobs`
- `http://localhost:8080/`
- `http://localhost:8080/api/nodes`
- `http://localhost:8080/api/tasks`
- `http://localhost:8080/api/reports`
- `http://localhost:8080/metrics`

## CLI 命令一览

| 命令 | 说明 |
|---|---|
| `gvstress fakecam` | 模拟相机生命周期管理 |
| `gvstress dut` | DUT（被测设备）检查 |
| `gvstress test` | 运行 smoke、soak、four-stream、loss-injection 场景 |
| `gvstress report` | 查看和导出结构化测试报告 |
| `gvstress baseline` | 运行 pktgen 基线基准测试 |
| `gvstress dut-agent` | 远程 DUT 辅助命令 |
| `gvstress node` | 本机节点健康、能力和状态命令 |
| `gvstress controller` | Controller HTTP API 服务 |
| `gvstress web` | Web 监控 UI 服务 |

## 项目结构

```text
src/gvstress/
├── cli/          # Typer CLI 入口与命令注册
├── controller/   # 任务状态存储和 Controller 服务
├── node/         # 本机节点健康、能力和状态逻辑
├── web/          # Web UI HTTP 服务和 API handler
├── core/         # 编排器、场景引擎、判定和预检
├── dut/          # NIC、stream、system 探针
├── fakecam/      # 模拟相机管理和 worker
├── report/       # 报告模型、写入、渲染和索引
├── baseline/     # pktgen 基线测试
└── config/       # Pydantic 配置模型和 YAML 加载
```

## 产物布局

```text
artifacts/
├── <scenario-name>/     # 场景输出，如 smoke、soak
│   ├── preflight/       # 预检结果
│   ├── fakecam/         # Fakecam 状态（如适用）
│   └── runs/
│       └── <run-id>/
│           ├── raw/      # JSON Lines 原始采样数据
│           ├── reports/  # run.json、summary.md
│           └── logs/     # worker 日志
└── pktgen/              # 基线基准测试
```

Controller 任务状态默认保存在 `data/`。Web UI 会扫描配置的 `artifacts/`
目录，用于报告浏览。

## 部署模式

GVStress 将控制平面和数据平面分离：

| 模式 | 数据平面 | 控制平面 | 使用场景 |
|---|---|---|---|
| Full native | native/systemd | native | 硬件验收和性能基准 |
| Hybrid | 远程节点原生运行 | Docker Compose 或 native | 监控栈容器化，流量保持裸机 |
| Full Compose | 容器 | Docker Compose | UI/API 开发和演示 |

性能敏感的 pktgen 流量不要走 Docker bridge。硬件验收优先使用 native/systemd；
只有在操作指南明确说明适合时，才使用 host-network privileged 容器。

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

## 文档

- [快速入门指南](docs/quickstart-zh.md)
- [CLI 命令参考](docs/cli-reference-zh.md)
- [测试指南（中文）](docs/testing-zh.md)
- [部署指南（中文）](docs/deployment-zh.md)
- [部署架构决策](docs/deployment-architecture-zh.md)
- [Web 监控操作指南](docs/web-monitoring-operator-guide-zh.md)
- [Prometheus 指标合同](docs/metrics-contract-zh.md)
- [Web 监控验收 TODO](docs/web-monitoring-validation-todos.md)
- [文档索引](docs/INDEX.md)

英文文档：

- [Testing Guide](docs/testing.md)
- [Deployment Guide](docs/deployment.md)
- [Deployment Architecture ADR](docs/deployment-architecture.md)
- [Web Monitoring Operator Guide](docs/web-monitoring-operator-guide.md)
- [Prometheus Metrics Contract](docs/metrics-contract.md)
- [Migration from Ad Hoc Soak Test Script](docs/migration-from-soak-test.md)

## 许可证

MIT License
