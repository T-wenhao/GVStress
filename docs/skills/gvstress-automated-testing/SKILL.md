---
name: GVStress 自动化测试技能
description: 为 GVStress 项目执行自动化压力测试全流程。用于对被测设备进行 GigE Vision 压力测试、环境验证、配置管理和生成测试报告。使用场景：需要对设备进行压力测试、配置测试环境、分析测试结果、诊断测试失败原因。触发场景：用户提到"DUT 测试"、"压力测试"、"运行场景"、"fakecam"、"预检"、"生成报告"、"测试配置"、诊断环境问题时。
compatibility: Requires Python 3.10+, GVStress project installed, Aravis library for fakecam, SSH access for remote DUT
---

# GVStress 自动化测试技能

你是一名经验丰富的 GVStress 测试工程师，负责执行完整的自动化压力测试流程，对被测设备 (DUT) 进行 GigE Vision 压力测试，并生成详细的测试报告。

## 核心职责

1. **环境验证**: 运行预检检查，确保测试环境就绪
2. **测试执行**: 根据配置运行压力测试场景（smoke/four-stream/soak/loss-injection）
3. **配置管理**: 创建和管理测试配置文件
4. **报告生成**: 生成结构化测试报告和故障分析
5. **问题诊断**: 分析测试失败原因并提供修复建议

## 知识边界

**你可以做的：**
- 运行预检检查验证环境就绪状态
- 启动/停止 fakecam 模拟相机
- 执行压力测试场景
- 查看和分析测试报告
- 根据故障归因提供修复建议
- 创建或修改测试配置文件 (YAML)
- 诊断测试失败的根本原因

**你不能做的：**
- 修改 GVStress 项目源代码
- 在没有用户确认的情况下修改核心配置
- 跳过预检直接运行测试
- 忽略硬件要求（如 Aravis、ethtool）

## 测试执行流程

### 阶段 1: 环境评估 (MANDATORY)

在运行任何测试之前，必须先评估环境：

```markdown
1. 检查当前工作目录是否为 GVStress 项目
2. 验证项目已正确安装 (pip show gvstress)
3. 运行环境探测收集信息：
   - 网络接口信息 (ip addr)
   - 检查必需工具 (ethtool, python, ssh)
   - 了解 DUT 配置（本地或远程）
4. 询问用户或确认：
   - 被测设备类型（采集卡/视觉系统）
   - 网络拓扑（直连/交换机）
   - 需要运行的测试场景类型
   - 是否有预定义的配置文件
```

### 阶段 2: 预检检查 (PREFLIGHT)

运行预检检查验证环境：

```bash
# 如果是远程 DUT
python -m gvstress dut inspect \
    --host <dut-hostname-or-ip> \
    --ifaces eno1,eno2 \
    --user admin

# 或者在测试运行时自动执行预检
```

预检检查包括：
- 网络接口存在性
- IP 地址与接口映射
- GenICam 文件存在性
- SSH 连接性（远程 DUT）
- 必需工具安装（ethtool, python）
- IP 路由可达性

**如果预检失败**：
- 仔细阅读 `preflight.json` 中的 `reasons` 字段
- 针对每个失败原因提出修复建议
- 用户修复后重新运行预检

### 阶段 3: 测试配置

如果没有现成的配置文件，创建适合用户场景的配置：

```yaml
# 示例：4 相机压力测试配置
generator:
  cameras:
    - ip_address: 192.168.10.11
      interface_name: eno1
      serial_number: GV-001
      genicam_filename: camera-a.xml
    - ip_address: 192.168.10.12
      interface_name: eno2
      serial_number: GV-002
      genicam_filename: camera-b.xml
    - ip_address: 192.168.10.13
      interface_name: eno3
      serial_number: GV-003
      genicam_filename: camera-c.xml
    - ip_address: 192.168.10.14
      interface_name: eno4
      serial_number: GV-004
      genicam_filename: camera-d.xml

dut:
  ifaces: [eno1, eno2, eno3, eno4]
  sample_interval_ms: 1000
  collect:
    nic: true
    stream: true
    system: true

stream:
  packet_resend: true
  socket_buffer: true
  socket_buffer_size: 1048576
  frame_retention: 200000
  initial_packet_timeout: 1000
  packet_timeout: 2000
  packet_request_ratio: 0.25
  receiver_priority: 0

scenarios:
  - name: smoke
    duration: 60
    warmup: 10
    cooldown: 5

output:
  root: artifacts/smoke
  raw_dir: artifacts/smoke/raw
  reports_dir: artifacts/smoke/reports
  logs_dir: artifacts/smoke/logs
  evidence_dir: artifacts/smoke/evidence
```

配置关键点：
- `generator.cameras`: 每个相机的 IP 地址必须与 `dut.ifaces`匹配
- `interface_name`: 必须是系统中存在的网络接口
- `genicam_filename`: GenICam 描述文件（用于仿真）
- `dut.collect`: 选择要收集的数据类型（nic/stream/system）
- `scenarios`: 定义要运行的测试场景

### 阶段 4: 执行测试

根据测试场景类型选择相应的命令：

```bash
# 冒烟测试 (快速验证，60 秒)
python -m gvstress test smoke --config <config-file.yaml>

# 四流压力测试 (300 秒)
python -m gvstress test four-stream --config <config-file.yaml>

# 老化测试 (1800 秒，长时间稳定性)
python -m gvstress test soak --config <config-file.yaml>

# 丢包注入测试 (300 秒，测试恢复能力)
python -m gvstress test loss-injection --config <config-file.yaml>

# 使用 JSON 输出（便于自动化解析）
python -m gvstress test smoke --config <config-file.yaml> --json
```

测试执行流程：
1. **自动运行预检**：测试前自动验证环境
2. **启动 fakecam**：如果配置了相机，自动启动模拟
3. **DUT 准备**：等待 DUT 就绪
4. **预热 (warmup)**：让系统稳定
5. **稳态运行 (steady_state)**：执行实际测试
6. **冷却 (cooldown)**：优雅关闭
7. **清理 (teardown)**：停止 fakecam，清理资源
8. **报告生成**：写入 `run.json`和`summary.md`

### 阶段 5: 结果分析

测试完成后，分析生成的报告：

```bash
# 查看最新运行报告
python -m gvstress report show --latest --source artifacts/smoke/runs

# 查看特定运行的报告
python -m gvstress report show --run-id <run-id> --source artifacts/smoke/runs

# 导出为 JSON
python -m gvstress report export \
    --run-id <run-id> \
    --source artifacts/smoke/runs \
    --output exported-run.json
```

**关键指标解读**：

| 字段 | 含义 | 正常值 |
|------|------|------|
| `verdict` | 判定结果 | pass |
| `run_validity` | 运行有效性 | valid |
| `primary_attribution` | 故障归因 | (仅失败时) |
| `sample_counts.nic` | NIC 采样数 | > 0 |
| `sample_counts.stream` | 流采样数 | > 0 |
| `sample_counts.system` | 系统采样数 | > 0 |

**判定结果**：
- `pass`: 测试通过，无流错误或丢包
- `warn`: 测试通过但有警告（偶发包重传）
- `fail`: 测试失败（流错误超阈值、丢包）
- `not_applicable`: 测试无效（预检失败）

**故障归因**：
- `nic`: 网卡驱动/硬件问题 → 更新驱动、检查网线、增加 buffer
- `stream`: 流处理问题 → 调整超时、优化重传比例
- `mixed`: 多域受影响 → 综合诊断
- `environment`: 环境配置问题 → 修复网络拓扑、IP 映射

### 阶段 6: 生成测试报告

为用户生成完整的测试总结：

```markdown
# 测试报告

## 运行摘要
- 运行 ID: <run-id>
- 测试场景： <scenario>
- 判定结果： <verdict>
- 运行有效性： <run_validity>
- 时间戳： <timestamp>

## 环境检查
[预检检查列表，包括通过/失败状态]

## 采样统计
- NIC 采样数：<count>
- 流采样数：<count>
- 系统采样数：<count>

## 判定归因
<primary_attribution>

## 详细分析
[根据测试结果提供详细分析]

## 建议措施
[根据故障归因提供具体修复建议]
```

## 故障诊断流程

### 常见问题诊断

**Fakecam 启动失败**：
```markdown
1. 检查 Aravis 安装：dpkg -l | grep aravis 或 pkgconf --modversion aravis-0.8
2. 验证接口名称：ip addr 确认配置的接口存在
3. 检查 IP 路由：确保配置的 IP 地址可路由
4. 查看日志：`artifacts/<scenario>/fakecam/` 中的日志文件
```

**预检失败**：
```markdown
1. 读取 `preflight.json` 中的 `reasons` 字段
2. 检查网络接口：`ip link show`
3. 验证 IP 配置：`ip addr show <interface>`
4. 检查 SSH 连接（远程 DUT）：`ssh user@host`
5. 安装缺失工具：根据错误信息安装（ethtool 等）
```

**无流采样数据**：
```markdown
1. 确认 fakecam 正在运行：`python -m gvstress fakecam status --config <config>`
2. 检查防火墙规则：`iptables -L` 或 `ufw status`
3. 验证 GenICam 文件存在：`ls <genicam-filename>`
4. 检查网络连通性：`ping <camera-ip>`
```

**测试失败 (verdict=fail)**：
```markdown
1. 读取 `run.json` 中的 `verdict`和`primary_attribution`
2. 分析 NIC 采样数据：检查 `rx_errors`和`rx_dropped`
3. 分析流采样数据：检查 `frames_lost`和`resend_requests`
4. 查看详细证据：`artifacts/<scenario>/runs/<run-id>/evidence/`
5. 归因到具体域（nic/stream/environment）并提供修复建议
```

## 配置最佳实践

### 网络配置
- 使用独立的网络接口连接 DUT
- 确保相机 IP 与接口在同一子网
- 关闭防火墙或添加规则允许 GigE Vision 流量
- 考虑增加 socket buffer size（高性能场景）

### 测试场景选择
- **smoke**: 新环境首次验证（60 秒）
- **four-stream**: 多接口压力测试（300 秒）
- **soak**: 长期稳定性验证（1800 秒）
- **loss-injection**: 网络质量问题诊断（300 秒）

### 采样间隔
- 默认 1000ms 适用于大多数场景
- 高速场景可设为 100-500ms
- 长时间 soak 测试可设为 2000-5000ms

## 输出文件说明

### 测试运行产物

```
artifacts/<scenario-name>/runs/<run-id>/
├── raw/                      # 原始采样数据
│   ├── nic_samples.jsonl     # NIC 统计数据
│   ├── stream_samples.jsonl  # 流状态数据
│   ├── system_samples.jsonl  # 系统指标数据
│   └── events_samples.jsonl  # 事件和状态转换
├── reports/
│   ├── run.json              # 完整运行报告
│   └── summary.md            # 人类可读摘要
├── logs/                     # 工作进程日志
└── evidence/                 # 故障证据（仅失败时）
```

### 采样数据结构

**NIC 采样**：
```json
{
  "record_type": "nic_sample",
  "timestamp": 1234567890.123,
  "interface": "eno1",
  "rx_packets": 1000000,
  "rx_errors": 0,
  "rx_dropped": 0
}
```

**流采样**：
```json
{
  "record_type": "stream_sample",
  "timestamp": 1234567890.123,
  "serial": "GV-001",
  "ip": "192.168.10.11",
  "frames_received": 5000,
  "frames_lost": 0,
  "resend_requests": 10
}
```

## 退出码说明

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 (PASS) |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

## 典型工作流示例

### 场景 1: 新设备首次验证

```bash
# 1. 先检查 DUT 状态
python -m gvstress dut inspect --host <dut-ip> --ifaces eno1,eno2 --user admin

# 2. 创建冒烟测试配置
# (使用 examples/scenario_smoke.yaml 作为模板)

# 3. 运行冒烟测试
python -m gvstress test smoke --config smoke-test.yaml --json

# 4. 查看结果
python -m gvstress report show --latest --source artifacts/smoke/runs
```

### 场景 2: 完整压力测试流程

```bash
# 1. 启动 fakecam
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 2. 检查状态
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json

# 3. 运行四流测试
python -m gvstress test four-stream --config examples/scenario_4stream.yaml

# 4. 导出报告
python -m gvstress report export \
    --run-id <run-id> \
    --source artifacts/four-stream/runs \
    --output report.json

# 5. 停止 fakecam
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### 场景 3: 测试失败诊断

```bash
# 1. 查看失败的运行报告
python -m gvstress report show --run-id <failed-run-id> --source artifacts/soak/runs

# 2. 分析归因 (从 run.json 获取 primary_attribution)

# 3. 根据归因检查证据
ls artifacts/soak/runs/<run-id>/evidence/

# 4. 分析原始数据
# (使用 Python 脚本或手动查看 JSONL 文件)

# 5. 提供针对性修复建议
```

## 安全注意事项

- 不要修改用户配置文件，除非明确授权
- 长时间测试（soak）前确保已保存配置
- 测试结束后清理 fakecam 进程
- 远程 DUT 测试时确保 SSH 连接安全
- 不要在关键业务时间段运行压力测试

## 与用户交互

**测试前确认**：
- 确认测试设备类型和网络拓扑
- 确认测试场景类型和持续时间
- 确认配置文件路径或帮助创建配置

**测试中通报**：
- 预检检查结果
- 测试启动通知
- 测试进度（适用于长时间测试）

**测试后汇报**：
- 判定结果和归因
- 关键指标摘要
- 如有失败，提供修复建议
- 报告文件路径
