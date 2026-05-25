# CLI 命令参考

GVStress 命令行接口完整参考文档。

## 总览

```bash
gvstress [OPTIONS] COMMAND [ARGS]...
```

GigE Vision 压力测试框架

### 全局选项

| 选项 | 简写 | 说明 |
|------|------|------|
| `--version` | `-v` | 显示版本号并退出 |
| `--help` | - | 显示帮助信息并退出 |

### 命令组

| 命令 | 说明 |
|------|------|
| `fakecam` | 模拟相机生命周期管理 |
| `dut` | DUT（被测设备）检查 |
| `test` | 运行压力测试场景 |
| `report` | 查看和导出测试报告 |
| `baseline` | 运行基线基准测试 |
| `dut-agent` | 远程 DUT 代理 |
| `node` | 本机 GVStress 节点健康、能力和状态命令 |
| `controller` | Controller HTTP API 服务 |
| `web` | Web 监控 UI 服务 |

### 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

---

## node 命令组

查看本机节点的健康状态、能力和完整状态。该命令组用于本机 smoke、部署验收、
以及 Web 监控节点侧信息检查。

### node health

检查本机节点健康状态。

```bash
gvstress node health [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 否 | - | 节点配置文件路径 |
| `--json` | `-j` | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
python -m gvstress node health --json
```

#### JSON 输出示例

```json
{
  "status": "ok",
  "pid": 12345,
  "uptime_seconds": 0.1
}
```

### node capabilities

显示本机节点能力，包括检测到的网络接口、pktgen 是否可用、以及是否具有
NET_ADMIN/root 权限。

```bash
gvstress node capabilities [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 否 | - | 节点配置文件路径 |
| `--json` | `-j` | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
python -m gvstress node capabilities --json
```

#### JSON 输出示例

```json
{
  "interfaces": ["en0"],
  "pktgen_available": false,
  "has_net_admin": false,
  "version": "0.1.0"
}
```

### node status

显示健康状态和能力的组合视图。

```bash
gvstress node status [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 否 | - | 节点配置文件路径 |
| `--json` | `-j` | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
python -m gvstress node status --json
```

---

## controller 命令组

运行轻量 Controller HTTP API。Controller 当前负责保存任务记录，并提供任务
列表和任务详情 API，供 Web UI 或脚本使用。

### controller serve

```bash
gvstress controller serve [OPTIONS]
```

#### 选项

| 选项 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | 否 | `localhost` | 监听地址 |
| `--port` | 否 | `8079` | 监听端口 |
| `--data-dir` | 否 | `data` | 任务状态存储目录 |

#### 示例

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

#### HTTP 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/jobs` | 列出任务 |
| POST | `/api/jobs` | 创建任务记录 |
| GET | `/api/jobs/<job-id>` | 查看任务详情 |

---

## web 命令组

运行 Web 监控 UI。Web 服务会读取 Controller 任务状态和 artifacts 报告目录，
并暴露 Prometheus 兼容的 `/metrics` 端点。

### web serve

```bash
gvstress web serve [OPTIONS]
```

#### 选项

| 选项 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | 否 | `localhost` | 监听地址 |
| `--port` | 否 | `8080` | 监听端口 |
| `--data-dir` | 否 | `data` | Controller 任务状态目录 |
| `--artifacts-dir` | 否 | `artifacts` | 测试报告和运行产物目录 |
| `--web-dir` | 否 | - | 静态 Web 资源目录；开发时可指定 `web` |

#### 示例

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

#### HTTP 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web UI 首页 |
| GET | `/api/nodes` | 节点和监控摘要 |
| GET | `/api/tasks` | Controller 任务列表 |
| POST | `/api/tasks` | 创建任务记录 |
| GET | `/api/reports` | 报告索引 |
| GET | `/api/reports/detail?path=<path>` | 报告详情 |
| GET | `/metrics` | Prometheus 文本格式指标 |

---

## fakecam 命令组

管理模拟 GigE Vision 相机的生命周期。

### fakecam up

启动模拟相机。

```bash
gvstress fakecam up [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--json` | | 否 | false | 输出 JSON 格式 |
| `--out` | | 否 | `artifacts/fakecam-up` | 运行时状态目录 |

#### 示例

```bash
# 启动 4 个模拟相机
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 以 JSON 格式输出状态
python -m gvstress fakecam up --config examples/fakecam_4p.yaml --json

# 指定自定义状态目录
python -m gvstress fakecam up --config examples/fakecam_4p.yaml --out /tmp/fakecam-state
```

#### JSON 输出示例

```json
{
  "status": "running",
  "cameras": [
    {
      "serial": "GV-001",
      "ip": "192.168.10.11",
      "interface": "eno1",
      "pid": 12345,
      "health": "ok"
    },
    {
      "serial": "GV-002",
      "ip": "192.168.11.11",
      "interface": "eno2",
      "pid": 12346,
      "health": "ok"
    }
  ],
  "artifacts_root": "artifacts/fakecam-up"
}
```

---

### fakecam status

查看模拟相机状态。

```bash
gvstress fakecam status [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--json` | | 否 | false | 输出 JSON 格式 |
| `--out` | | 否 | `artifacts/fakecam-up` | 运行时状态目录 |

#### 示例

```bash
# 查看状态
python -m gvstress fakecam status --config examples/fakecam_4p.yaml

# JSON 格式详细状态
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json | jq .
```

#### JSON 输出示例

```json
{
  "status": "running",
  "cameras": [
    {
      "serial": "GV-001",
      "ip": "192.168.10.11",
      "interface": "eno1",
      "pid": 12345,
      "health": "ok",
      "frames_transmitted": 50000,
      "bytes_transmitted": 75000000
    }
  ],
  "runtime_dir": "artifacts/fakecam-up"
}
```

---

### fakecam down

停止模拟相机。

```bash
gvstress fakecam down [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--json` | | 否 | false | 输出 JSON 格式 |
| `--out` | | 否 | `artifacts/fakecam-up` | 运行时状态目录 |

#### 示例

```bash
# 停止所有模拟相机
python -m gvstress fakecam down --config examples/fakecam_4p.yaml

# JSON 格式输出
python -m gvstress fakecam down --config examples/fakecam_4p.yaml --json
```

#### JSON 输出示例

```json
{
  "status": "stopped",
  "cameras_stopped": 4,
  "artifacts_root": "artifacts/fakecam-up"
}
```

---

## dut 命令组

DUT（被测设备）环境检查。

### dut inspect

检查 DUT 环境就绪状态。

```bash
gvstress dut inspect [OPTIONS]
```

#### 选项

| 选项 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | 是 | - | DUT SSH 主机名或 IP |
| `--ifaces` | 是 | - | DUT 网络接口，逗号分隔 |
| `--user` | 否 | 当前用户 | DUT SSH 用户名 |
| `--port` | 否 | 22 | DUT SSH 端口 |
| `--ssh-python-bin` | 否 | `python3` | DUT 上的 Python 可执行文件路径 |
| `--json` | 否 | false | 输出 JSON 格式 |
| `--out` | 否 | `artifacts/preflight` | 快照输出目录 |

#### 示例

```bash
# 基本检查
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2,eno3,eno4

# 指定 SSH 用户
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2 \
    --user admin

# JSON 格式输出
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2,eno3,eno4 \
    --json | jq .

# 指定 Python 路径
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2 \
    --ssh-python-bin /usr/bin/python3.10
```

#### JSON 输出示例

**成功情况：**
```json
{
  "run_validity": "valid",
  "preflight_result": "pass",
  "dut": {
    "host": "192.168.10.11",
    "interfaces": ["eno1", "eno2", "eno3", "eno4"]
  },
  "artifacts_root": "artifacts/preflight"
}
```

**失败情况：**
```json
{
  "run_validity": "invalid_environment",
  "preflight_result": "fail",
  "reasons": [
    "SSH connection failed: Connection timeout",
    "Interface 'eno3' does not exist on DUT"
  ],
  "dut": {
    "host": "192.168.10.11",
    "interfaces": ["eno1", "eno2", "eno3", "eno4"]
  }
}
```

---

## test 命令组

运行压力测试场景。

### 支持的场景类型

| 场景 | 命令 | 持续时间 | 说明 |
|------|------|----------|------|
| smoke | `test smoke` | 60s | 快速冒烟测试 |
| four-stream | `test four-stream` | 300s | 四流并行测试 |
| soak | `test soak` | 1800s | 长时间稳定性测试 |
| loss-injection | `test loss-injection` | 300s | 丢包注入测试 |

---

### test smoke

运行冒烟测试（快速验证）。

```bash
gvstress test smoke [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--output` | `-o` | 否 | `artifacts` | 输出目录 |
| `--json` | | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
# 运行冒烟测试
python -m gvstress test smoke --config examples/scenario_smoke.yaml

# 指定输出目录
python -m gvstress test smoke \
    --config examples/scenario_smoke.yaml \
    --output artifacts/smoke_test

# JSON 格式输出
python -m gvstress test smoke \
    --config examples/scenario_smoke.yaml \
    --json
```

---

### test four-stream

运行四流压力测试。

```bash
gvstress test four-stream [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--output` | `-o` | 否 | `artifacts` | 输出目录 |
| `--json` | | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
# 运行四流测试
python -m gvstress test four-stream --config examples/scenario_4stream.yaml

# 带 JSON 输出
python -m gvstress test four-stream \
    --config examples/scenario_4stream.yaml \
    --json | jq .
```

---

### test soak

运行老化测试（长时间稳定性）。

```bash
gvstress test soak [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--output` | `-o` | 否 | `artifacts` | 输出目录 |
| `--json` | | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
# 运行 30 分钟老化测试
python -m gvstress test soak --config examples/scenario_soak.yaml

# 监控进度（需要另一个终端）
watch -n 10 'python -m gvstress report show --latest --source artifacts/soak/runs'
```

---

### test loss-injection

运行丢包注入测试。

```bash
gvstress test loss-injection [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--output` | `-o` | 否 | `artifacts` | 输出目录 |
| `--json` | | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
# 运行丢包测试
python -m gvstress test loss-injection --config examples/scenario_loss.yaml
```

---

### test 命令 JSON 输出结构

所有 test 命令的 JSON 输出遵循相同结构：

```json
{
  "run_id": "abc123def",
  "scenario": "smoke",
  "run_validity": "valid",
  "aborted": false,
  "abort_reason": null,
  "sample_counts": {
    "nic": 60,
    "stream": 60,
    "system": 60,
    "events": 5
  },
  "artifacts_root": "artifacts/smoke/runs/abc123def",
  "transitions": []
}
```

**字段说明：**
- `run_id`: 唯一运行标识符
- `scenario`: 场景类型
- `run_validity`: 运行有效性 (valid/invalid_environment/invalid_prereq/interrupted)
- `aborted`: 是否被中止
- `abort_reason`: 中止原因
- `sample_counts`: 各类型采样数量
- `artifacts_root`: 产物根目录路径
- `transitions`: 状态转换列表

**注意**: `test` 命令的 JSON 输出**不包含** `verdict` 和 `primary_attribution` 字段。
要获取这些信息，请使用 `report show` 命令查看运行报告：

```bash
python -m gvstress report show --run-id abc123 --source artifacts/smoke/runs --json | jq '.verdict'
```

---

## report 命令组

查看和导出测试报告。

### report show

显示测试报告。

```bash
gvstress report show [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--latest` | | 否¹ | - | 显示最新运行报告 |
| `--run-id` | | 否¹ | - | 指定运行 ID |
| `--json` | | 否 | false | 输出 JSON 格式 |
| `--source` | `-s` | 否 | `artifacts` | 报告根目录 |

**注意**: `--latest` 或 `--run-id` 必须指定一个。

#### 示例

```bash
# 查看最新运行报告
python -m gvstress report show --latest --source artifacts/smoke/runs

# 查看指定运行
python -m gvstress report show \
    --run-id abc123 \
    --source artifacts/smoke/runs

# JSON 格式
python -m gvstress report show \
    --latest \
    --source artifacts/smoke/runs \
    --json | jq .
```

---

### report export

导出测试报告。

```bash
gvstress report export [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--run-id` | | 是 | - | 运行 ID |
| `--output` | `-o` | 是 | - | 导出文件路径 |
| `--format` | | 否 | `json` | 导出格式 (json) |
| `--source` | `-s` | 否 | `artifacts` | 报告根目录 |

#### 示例

```bash
# 导出为 JSON
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output run_data.json

# 导出到指定路径
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output /tmp/reports/run_abc123.json
```

---

## baseline 命令组

运行基线基准测试。

### baseline pktgen

运行 pktgen 基线测试。

```bash
gvstress baseline pktgen [OPTIONS]
```

#### 选项

| 选项 | 简写 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--config` | `-c` | 是 | - | 配置文件路径 (YAML) |
| `--output` | `-o` | 否 | `artifacts` | 输出目录 |
| `--json` | | 否 | false | 输出 JSON 格式 |

#### 示例

```bash
# 运行 pktgen 基线
python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml

# 指定输出目录
python -m gvstress baseline pktgen \
    --config examples/pktgen_4p.yaml \
    --output artifacts/baseline

# JSON 输出
python -m gvstress baseline pktgen \
    --config examples/pktgen_4p.yaml \
    --json | jq .
```

---

## dut-agent 命令组

远程 DUT 代理命令（通过 SSH 调用）。

**注意**: 此命令组主要在 DUT 上通过 SSH 调用。

### dut-agent ping

连通性测试。

```bash
gvstress dut-agent ping [OPTIONS]
```

#### 选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出 JSON 格式 |

#### 示例

```bash
# 本地调用（测试代理）
python -m gvstress.cli.dut_agent ping

# 通过 SSH 远程调用
ssh user@dut "python -m gvstress.cli.dut_agent ping"
```

#### JSON 输出

```json
{
  "status": "ok",
  "message": "pong"
}
```

---

### dut-agent inspect

收集本地环境快照。

```bash
gvstress dut-agent inspect [OPTIONS]
```

#### 选项

| 选项 | 说明 |
|------|------|
| `--ifaces` | 网络接口，逗号分隔 |
| `--json` | 输出 JSON 格式 |

#### 示例

```bash
# 检查本地接口
python -m gvstress.cli.dut_agent inspect --ifaces eno1,eno2

# 远程调用
ssh user@dut "python -m gvstress.cli.dut_agent inspect --ifaces eno1,eno2 --json"
```

---

### dut-agent stream-runner

流采集代理。

```bash
gvstress dut-agent stream-runner [OPTIONS]
```

#### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--camera` | - | 相机选择器 (格式：SERIAL@IP，可重复) |
| `--sample-interval-ms` | 1000 | 采样间隔（毫秒） |
| `--duration` | - | 运行时长（秒） |
| `--packet-resend/--no-packet-resend` | 启用 | 启用/禁用包重传 |
| `--socket-buffer/--no-socket-buffer` | 启用 | 启用/禁用 socket 缓冲 |
| `--socket-buffer-size` | 1048576 | Socket 缓冲大小 |
| `--frame-retention` | 200000 | 帧保留设置 |
| `--initial-packet-timeout` | 1000 | 初始包超时 |
| `--packet-timeout` | 2000 | 包超时 |
| `--packet-request-ratio` | 0.25 | 包请求比例 |
| `--receiver-priority` | 0 | 接收器优先级 |
| `--buffer-count` | 16 | 预分配缓冲数 |
| `--json` | - | 输出 JSON 格式 |

#### 示例

```bash
# 启动流采集
python -m gvstress.cli.dut_agent stream-runner \
    --camera GV-001@192.168.10.11 \
    --camera GV-002@192.168.11.11 \
    --sample-interval-ms 1000 \
    --duration 60

# 自定义流参数
python -m gvstress.cli.dut_agent stream-runner \
    --camera GV-001@192.168.10.11 \
    --packet-timeout 3000 \
    --packet-request-ratio 0.3 \
    --socket-buffer-size 2097152
```

---

## 配置参数参考

### 流配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `packet_resend` | true | 是否启用包重传 |
| `socket_buffer` | true | 是否启用 socket 缓冲 |
| `socket_buffer_size` | 1048576 | Socket 缓冲区大小（字节） |
| `frame_retention` | 200000 | 帧保留数 |
| `initial_packet_timeout` | 1000 | 初始包超时（毫秒） |
| `packet_timeout` | 2000 | 包超时（毫秒） |
| `packet_request_ratio` | 0.25 | 包请求比例 |
| `receiver_priority` | 0 | 接收器优先级 |
| `buffer_count` | 16 | 预分配缓冲区数 |

### 场景配置参数

| 参数 | 说明 |
|------|------|
| `scenario` | 场景类型 (smoke/four_stream/soak/loss_injection/pktgen_baseline) |
| `dut.host` | DUT SSH 主机名 |
| `dut.interfaces` | DUT 网络接口列表 |
| `generator.cameras` | 相机配置列表 |

### 相机配置参数

| 参数 | 说明 |
|------|------|
| `serial` | 相机序列号 |
| `ip` | 相机 IP 地址 |
| `interface` | 生成器上的网络接口 |

---

## 使用技巧

### 组合命令

**完整测试流程：**
```bash
# 1. 预检
python -m gvstress dut inspect --host dut --ifaces eno1,eno2 --json && \
# 2. 启动相机
python -m gvstress fakecam up --config fakecam.yaml --json && \
# 3. 运行测试
python -m gvstress test smoke --config scenario.yaml --json && \
# 4. 停止相机
python -m gvstress fakecam down --config fakecam.yaml
```

### JSON 处理

**提取运行 ID：**
```bash
RUN_ID=$(python -m gvstress test smoke --config scenario.yaml --json | jq -r .run_id)
```

**检查测试结果：**
```bash
python -m gvstress report show --run-id $RUN_ID --source artifacts/smoke/runs --json | jq -r .verdict
```

**提取采样计数：**
```bash
python -m gvstress report show --latest --source artifacts/smoke/runs --json | \
    jq .sample_counts
```

### 自动化脚本

```bash
#!/bin/bash
# run_smoke_test.sh

set -e

CONFIG=$1
OUTPUT_DIR=$2

echo "运行冒烟测试..."

# 运行测试并获取 run_id
RESULT=$(python -m gvstress test smoke --config $CONFIG --output $OUTPUT_DIR --json)
RUN_ID=$(echo $RESULT | jq -r .run_id)

echo "运行 ID: $RUN_ID"

# 通过 report 命令获取 verdict
VERDICT=$(python -m gvstress report show --run-id $RUN_ID --source $OUTPUT_DIR/runs --json | jq -r .verdict)
echo "判定：$VERDICT"

if [ "$VERDICT" != "pass" ]; then
    echo "测试失败！"
    python -m gvstress report show --run-id $RUN_ID --source $OUTPUT_DIR/runs
    exit 1
fi

echo "测试通过 ✓"
```

---

## 故障排除

### 命令找不到

**问题**: `gvstress: command not found`

**解决**: 确保已安装包或激活虚拟环境
```bash
pip install -e .
# 或
python -m gvstress --help
```

### 配置文件错误

**问题**: YAML 配置解析失败

**解决**: 验证 YAML 语法
```bash
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### SSH 连接失败

**问题**: dut inspect 返回 SSH 连接错误

**解决**:
```bash
# 测试 SSH 连接
ssh -v user@dut "hostname"

# 检查 SSH 密钥
ls -la ~/.ssh/gvstress
chmod 600 ~/.ssh/gvstress
```
