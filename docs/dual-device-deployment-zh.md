# 双设备部署指南

本指南详细说明如何在**控制主机 + 生成器 + 被测设备 (DUT)** 三角色架构中部署和运行 GVStress，实现真实的网络环境压力测试。

## 目录

- [架构概述](#架构概述)
- [部署场景](#部署场景)
- [网络拓扑](#网络拓扑)
- [完整部署流程](#完整部署流程)
  - [第一步：在 DUT 上部署代理](#第一步在-dut-上部署代理)
  - [第二步：配置控制主机](#第二步配置控制主机)
  - [第三步：创建双设备配置](#第三步创建双设备配置)
  - [第四步：运行测试](#第四步运行测试)
- [数据流向详解](#数据流向详解)
- [配置参数说明](#配置参数说明)
- [部署检查清单](#部署检查清单)
- [常见问题](#常见问题)

---

## 架构概述

GVStress 是一个**分布式测试系统**，包含三个逻辑角色：

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   控制主机       │         │   生成器         │         │   DUT (被测设备) │
│  Control Host   │         │   Generator     │         │   Device Under  │
│                 │         │                 │         │   Test          │
│ - 运行 CLI 命令   │ SSH     │ - 运行 Fakecam  │ 网络流   │ - 接收相机流    │
│ - 编排测试       │────────>│ - 生成视频流     │────────>│ - 网卡统计      │
│ - 收集报告       │<───────>│ - 采集探针数据   │<───────>│ - 流健康状态    │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 三个角色说明

| 角色 | 职责 | 典型设备 |
|------|------|----------|
| **控制主机** | 运行 CLI 命令、编排测试、收集报告 | 工程师笔记本、工作站 |
| **生成器** | 运行 Fakecam、生成 GigE Vision 视频流 | 高性能 PC、服务器 |
| **DUT** | 接收视频流、提供 NIC 统计、流健康数据 | 工控机、嵌入式设备、视觉系统 |

### 典型部署方式

**最常见配置：控制主机 + 生成器 = 同一台机器**

```
您的笔记本 (控制主机 + 生成器)          远程服务器/工控机 (DUT)
192.168.1.100                         192.168.10.100
├── 运行 gvstress CLI                 ├── 接收 Fakecam 视频流
├── 运行 fakecam 进程                  ├── 运行 SSH 代理
├── 采集本地 NIC 统计                   ├── 采集 NIC 统计
└── 生成报告                          └── 返回流健康数据
```

---

## 部署场景

### 场景 1: 单机测试（开发调试）

**所有角色在同一台机器上**

```bash
[localhost]
├── 控制主机
├── 生成器 (Fakecam)
└── DUT (通过 localhost SSH)
```

**用途**: 
- 开发调试
- 功能验证
- 快速测试 CLI 命令

**不推荐用于生产验证**（无法测试真实网络环境）

---

### 场景 2: 双设备测试（标准生产环境）

**控制主机 + 生成器 vs DUT**

```
[控制主机/生成器]                  [DUT]
192.168.10.1                      192.168.10.100
├── 运行测试 CLI                   ├── 接收视频流
├── 生成 4 路视频流                  ├── 采集 NIC 统计
└── 收集报告                       └── 返回探针数据
```

**用途**:
- 真实网络拓扑测试
- 网卡/交换机性能验证
- 长距离传输稳定性
- 生产环境验证

**本文档重点讲解此场景**

---

### 场景 3: 三设备分离（大规模测试）

**控制主机、生成器、DUT 各自独立**

```
[控制主机]     SSH     [生成器]     网络流     [DUT]
192.168.1.50  ──────>  192.168.10.1  ──────>  192.168.10.100
                SSH              网络流
```

**用途**:
- 多生成器并行测试
- 大规模相机阵列
- 复杂网络拓扑

---

## 网络拓扑

### 典型直连拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                    交换机 (可选)                             │
│  ┌──────────────┐              ┌──────────────┐            │
│  │ 控制主机/生成器│              │     DUT      │            │
│  │ 192.168.10.1 │              │ 192.168.10.100│            │
│  │              │              │              │            │
│  │ eno1:10.1   ├──────┐  ┌─────┤ eno1:10.100  │            │
│  │ eno2:11.1   ├──────┼──┼─────┤ eno2:11.100  │            │
│  │ eno3:12.1   ├──────┤  ├─────┤ eno3:12.100  │            │
│  │ eno4:13.1   ├──────┘  └─────┤ eno4:13.100  │            │
│  └──────────────┘              └──────────────┘            │
│                                                              │
│  每台设备 4 个网口，共 4 路独立视频流                         │
└─────────────────────────────────────────────────────────────┘
```

### 直接点对点连接（无交换机）

```
[控制主机/生成器]                [DUT]
192.168.10.1                    192.168.10.100
  eno1 ──────────────────────────── eno1
  (192.168.10.1/24)   网线   (192.168.10.100/24)

  eno2 ──────────────────────────── eno2
  (192.168.11.1/24)   网线   (192.168.11.100/24)
```

**注意**: 使用直通网线（ crossover cable）或现代网卡的自动翻转功能

---

## 完整部署流程

### 第一步：在 DUT 上部署代理

**DUT 通常是一台远程 Linux 设备（工控机、服务器等）**

#### 1.1 SSH 登录 DUT

```bash
ssh user@192.168.10.100
```

#### 1.2 在 DUT 上安装 Python

```bash
# 更新包列表
sudo apt update

# 安装 Python 3.10+
sudo apt install -y python3 python3-pip python3-venv

# 验证安装
python3 --version
# 应输出：Python 3.10.x 或更高
```

#### 1.3 创建 GVStress 目录

```bash
# 创建目录
sudo mkdir -p /opt/gvstress
sudo chown user:user /opt/gvstress
cd /opt/gvstress
```

#### 1.4 从控制主机复制代码

**在控制主机上执行**：

```bash
# 复制 GVStress 源码到 DUT
scp -r src/gvstress user@192.168.10.100:/opt/gvstress/

# 或使用 rsync（更快）
rsync -avz src/gvstress user@192.168.10.100:/opt/gvstress/
```

#### 1.5 在 DUT 上安装依赖

```bash
# SSH 到 DUT 执行
ssh user@192.168.10.100 "cd /opt/gvstress && pip3 install pydantic typer"

# 或登录 DUT 后执行
ssh user@192.168.10.100
cd /opt/gvstress
pip3 install pydantic typer
```

#### 1.6 验证 DUT 代理

```bash
# 测试 DUT 代理连通性
ssh user@192.168.10.100 "python3 -m gvstress.cli.dut_agent ping"

# 预期输出
{"status":"ok"}
```

#### 1.7 配置 DUT SSH 无密码访问

**在控制主机上执行**：

```bash
# 生成 SSH 密钥（如已有可跳过）
ssh-keygen -t ed25519 -f ~/.ssh/gvstress -N ""

# 复制密钥到 DUT
ssh-copy-id -i ~/.ssh/gvstress user@192.168.10.100

# 测试无密码登录
ssh -i ~/.ssh/gvstress user@192.168.10.100 "hostname"
# 应直接返回 DUT 主机名，无需输入密码
```

---

### 第二步：配置控制主机

#### 2.1 配置网络接口静态 IP

**以 Ubuntu/Debian 为例**：

```bash
# 方法 1: 使用 nmcli（NetworkManager）
sudo nmcli con mod eno1 ipv4.addresses "192.168.10.1/24"
sudo nmcli con mod eno1 ipv4.gateway "192.168.10.254"
sudo nmcli con mod eno1 ipv4.method manual
sudo nmcli con up eno1

sudo nmcli con mod eno2 ipv4.addresses "192.168.11.1/24"
sudo nmcli con mod eno2 ipv4.gateway "192.168.11.254"
sudo nmcli con mod eno2 ipv4.method manual
sudo nmcli con up eno2

# 方法 2: 使用 netplan（Ubuntu 18.04+）
# 编辑 /etc/netplan/01-netcfg.yaml
sudo vim /etc/netplan/01-netcfg.yaml
```

**netplan 配置示例**：

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eno1:
      addresses:
        - 192.168.10.1/24
      routes:
        - to: default
          via: 192.168.10.254
    eno2:
      addresses:
        - 192.168.11.1/24
      routes:
        - to: default
          via: 192.168.11.254
```

应用配置：

```bash
sudo netplan apply
```

#### 2.2 验证 IP 配置

```bash
# 查看接口 IP
ip addr show eno1
ip addr show eno2

# 预期输出：
# inet 192.168.10.1/24 brd 192.168.10.255 scope global eno1
# inet 192.168.11.1/24 brd 192.168.11.255 scope global eno2
```

#### 2.3 测试到 DUT 的连通性

```bash
# 测试所有接口到 DUT 的连通性
ping -c 3 -I eno1 192.168.10.100
ping -c 3 -I eno2 192.168.11.100
ping -c 3 -I eno3 192.168.12.100
ping -c 3 -I eno4 192.168.13.100

# 所有 ping 应该都能收到回复
```

#### 2.4 安装控制主机依赖

```bash
# 安装基础工具
sudo apt update
sudo apt install -y ethtool

# 如果使用 Fakecam，安装 Aravis
sudo apt install -y libaravis-0.8-dev

# 验证安装
ethtool --version
```

#### 2.5 安装 GVStress（如未安装）

```bash
# 克隆仓库
cd ~
git clone <repository-url> GVStress
cd GVStress

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装
pip install -e .

# 验证
python -m gvstress --version
```

---

### 第三步：创建双设备配置

#### 3.1 配置文件结构

创建配置文件 `dual_device_test.yaml`：

```yaml
# ============================================================
# 生成器配置（控制主机本地）
# ============================================================
generator:
  cameras:
    - serial_number: "GV-001"
      ip_address: "192.168.10.100"  # ← DUT 的 IP（相机"看到"的对面）
      interface_name: "eno1"         # ← 控制主机的接口
      genicam_filename: camera-a.xml
      gvsp_lost_ratio: 0.0
    - serial_number: "GV-002"
      ip_address: "192.168.11.100"
      interface_name: "eno2"
      genicam_filename: camera-b.xml
      gvsp_lost_ratio: 0.0
    - serial_number: "GV-003"
      ip_address: "192.168.12.100"
      interface_name: "eno3"
      genicam_filename: camera-c.xml
      gvsp_lost_ratio: 0.0
    - serial_number: "GV-004"
      ip_address: "192.168.13.100"
      interface_name: "eno4"
      genicam_filename: camera-d.xml
      gvsp_lost_ratio: 0.0

# ============================================================
# DUT 配置（远程设备）
# ============================================================
dut:
  host: "192.168.10.100"            # ← DUT 的 SSH 地址
  user: "user"                       # ← SSH 用户名（可选，默认当前用户）
  port: 22                          # ← SSH 端口（可选，默认 22）
  ifaces: ["eno1", "eno2", "eno3", "eno4"]  # ← DUT 上的接口
  ssh_python_bin: "python3"         # ← DUT 上的 Python 路径
  sample_interval_ms: 1000          # ← 采样间隔（毫秒）
  collect:
    nic: true                       # ← 采集 NIC 统计
    stream: true                    # ← 采集流状态
    system: true                    # ← 采集系统指标

# ============================================================
# 流配置（ GigE Vision 参数）
# ============================================================
stream:
  packet_resend: true               # 启用包重传
  socket_buffer: true               # 启用 socket 缓冲
  socket_buffer_size: 1048576       # 缓冲大小（字节）
  frame_retention: 200000           # 帧保留数
  initial_packet_timeout: 1000      # 初始包超时（毫秒）
  packet_timeout: 2000              # 包超时（毫秒）
  packet_request_ratio: 0.25        # 重传请求比例
  receiver_priority: 0              # 接收器优先级

# ============================================================
# 测试场景定义
# ============================================================
scenarios:
  - name: smoke                     # 冒烟测试
    duration: 60                    # 持续时间（秒）
    warmup: 10                      # 预热时间（秒）
    cooldown: 5                     # 冷却时间（秒）
  - name: four_stream               # 四流测试
    duration: 300
    warmup: 10
    cooldown: 5
  - name: soak                      # 老化测试
    duration: 1800
    warmup: 10
    cooldown: 5

# ============================================================
# 输出配置
# ============================================================
output:
  root: artifacts/dual_test         # ← 输出目录根路径
  raw_dir: artifacts/dual_test/raw  # ← 原始数据目录
```

#### 3.2 配置文件说明

**关键字段解释**：

| 字段 | 含义 | 注意事项 |
|------|------|----------|
| `generator.cameras[].ip_address` | 相机目标 IP | **这是 DUT 的 IP**，相机"看到"的接收端 |
| `generator.cameras[].interface_name` | 发送接口 | 控制主机上用于发送流的网口 |
| `dut.host` | DUT SSH 地址 | 用于 SSH 连接执行探针采集 |
| `dut.ifaces` | DUT 接口列表 | 与 `generator.cameras[].ip_address` 对应 |
| `output.root` | 输出目录 | 测试报告存储位置 |

**重要概念**：

- **IP 地址方向**: `generator.cameras[].ip_address` 是 DUT 的 IP，因为 Fakecam "模拟相机"向 DUT 发送视频流
- **接口对应**: 控制主机的 `interface_name` 连接到 DUT 的 `ifaces` 中的对应接口

#### 3.3 根据实际环境修改

```bash
# 1. 查看控制主机的网络接口
ip link show

# 2. 记录 DUT 的 SSH 地址
# 例如：192.168.10.100

# 3. 查看 DUT 的网络接口（通过 SSH）
ssh user@192.168.10.100 "ip link show"

# 4. 复制示例配置
cp examples/fakecam_4p.yaml dual_device_test.yaml
cp examples/scenario_smoke.yaml dual_device_scenario.yaml

# 5. 编辑配置
vim dual_device_test.yaml
```

---

### 第四步：运行测试

#### 4.1 运行预检（推荐）

```bash
# 验证 DUT 环境 readiness
python -m gvstress dut inspect \
    --host 192.168.10.100 \
    --ifaces eno1,eno2,eno3,eno4 \
    --user user \
    --json | jq .
```

**预期输出**：

```json
{
  "run_validity": "valid",
  "preflight_result": "pass",
  "dut": {
    "host": "192.168.10.100",
    "interfaces": ["eno1", "eno2", "eno3", "eno4"]
  },
  "artifacts_root": "artifacts/preflight"
}
```

**失败情况**：

```json
{
  "run_validity": "invalid_environment",
  "preflight_result": "fail",
  "reasons": [
    "SSH connection failed: Connection timeout",
    "Interface 'eno3' does not exist on DUT"
  ]
}
```

此时应先修复环境问题：
- 检查 SSH 连接
- 验证接口名称
- 确认网络连通性

#### 4.2 启动 Fakecam（可选）

```bash
# 预先启动模拟相机
python -m gvstress fakecam up \
    --config dual_device_test.yaml \
    --json | jq .

# 查看状态
python -m gvstress fakecam status \
    --config dual_device_test.yaml \
    --json | jq .

# 停止相机
python -m gvstress fakecam down \
    --config dual_device_test.yaml \
    --json
```

**注意**: 通常不需要手动启动 Fakecam，`test` 命令会自动管理其生命周期。

#### 4.3 运行测试

```bash
# 冒烟测试（60 秒）
python -m gvstress test smoke \
    --config dual_device_test.yaml \
    --json | jq .

# 四流测试（300 秒）
python -m gvstress test four-stream \
    --config dual_device_test.yaml \
    --json | jq .

# 老化测试（1800 秒）
python -m gvstress test soak \
    --config dual_device_test.yaml \
    --json | jq .
```

#### 4.4 查看测试结果

```bash
# 查看最新运行的 JSON 报告
python -m gvstress report show \
    --latest \
    --source artifacts/dual_test/runs \
    --json | jq .

# 查看 Markdown 摘要报告
python -m gvstress report show \
    --latest \
    --source artifacts/dual_test/runs

# 查看生成的 summary.md
cat artifacts/dual_test/runs/<run-id>/reports/summary.md

# 导出运行数据
python -m gvstress report export \
    --run-id <run-id> \
    --source artifacts/dual_test/runs \
    --output results.json
```

#### 4.5 查看原始数据

```bash
# 查看 NIC 采样数据
head artifacts/dual_test/runs/<run-id>/raw/nic_samples.jsonl

# 查看流采样数据
head artifacts/dual_test/runs/<run-id>/raw/stream_samples.jsonl

# 查看系统采样数据
head artifacts/dual_test/runs/<run-id>/raw/system_samples.jsonl
```

---

## 数据流向详解

### 测试执行全流程

```
时间线：

T0: 控制主机执行 `test smoke`
     ↓
T1: 预检阶段 (Preflight)
     ├─ SSH 连接 DUT: 192.168.10.100
     ├─ 验证 DUT 上 Python 可用
     │  执行：ssh user@dut "python3 --version"
     ├─ 验证 DUT 网络接口存在
     │  执行：ssh user@dut "ip link show"
     ├─ 验证 SSH 到各个接口的路由
     │  执行：ping -I eno1 192.168.10.100
     └─ 结果：run_validity=valid 或 invalid_environment
     ↓
T2: 启动 Fakecam（在控制主机本地）
     ├─ 进程 1: fakecam GV-001 → 192.168.10.100 (eno1)
     ├─ 进程 2: fakecam GV-002 → 192.168.11.100 (eno2)
     ├─ 进程 3: fakecam GV-003 → 192.168.12.100 (eno3)
     ├─ 进程 4: fakecam GV-004 → 192.168.13.100 (eno4)
     └─ 开始通过物理网络发送 GigE Vision 视频流
     ↓
T3: DUT 准备阶段（通过 SSH）
     ├─ SSH 执行：python3 -m gvstress.cli.dut_agent stream-runner
     │  参数：--camera GV-001@192.168.10.100 --camera GV-002@192.168.11.100 ...
     ├─ DUT 开始监听视频流（从 4 个网口接收）
     ├─ DUT 启动 NIC 探针采集（ethtool, ip, /proc/net）
     └─ 数据通过 SSH 实时返回控制主机
     ↓
T4: 预热阶段 (Warmup) - 10 秒
     ├─ 控制主机：每 1 秒采集本地 NIC 统计
     │  数据：rx_packets, rx_errors, rx_dropped
     ├─ DUT：每 1 秒采集流健康状态（通过 SSH 返回）
     │  数据：frames_received, frames_lost, resend_requests
     └─ 数据同步到控制主机，写入 JSON Lines 文件
     ↓
T5: 稳态测试 (Steady State) - 60 秒
     ├─ 持续采集（每秒）:
     │  ├─ 控制主机 NIC 统计 → nic_samples.jsonl
     │  ├─ DUT 流状态 → stream_samples.jsonl
     │  └─ DUT 系统指标 → system_samples.jsonl
     ├─ 实时检测:
     │  ├─ 丢包检测（rx_dropped > 0）
     │  ├─ 重传检测（resend_requests > 阈值）
     │  └─ 流中断检测（frames_received 停止增长）
     └─ 生成事件记录 → events_samples.jsonl
     ↓
T6: 冷却阶段 (Cooldown) - 5 秒
     └─ 停止数据流，等待缓冲区清空
     ↓
T7: 清理阶段 (Teardown)
     ├─ SSH 停止 DUT 代理
     │  执行：ssh user@dut "kill <stream-runner-pid>"
     ├─ 本地停止 Fakecam
     │  执行：kill <fakecam-pid>
     └─ 生成报告
     ↓
T8: 输出产物 (Reporting)
     artifacts/dual_test/runs/<run-id>/
     ├── raw/nic_samples.jsonl      (控制主机采集)
     ├── raw/stream_samples.jsonl   (DUT 返回)
     ├── raw/system_samples.jsonl   (DUT 返回)
     ├── raw/events_samples.jsonl   (状态转换事件)
     ├── reports/run.json           (判定结果)
     └── reports/summary.md         (人类可读报告)
```

### 数据采集详解

#### 控制主机采集的数据

**nic_samples.jsonl**（每秒一条）：

```json
{
  "record_type": "nic_sample",
  "timestamp": 1712649600.123,
  "interface": "eno1",
  "rx_packets": 1000000,
  "rx_errors": 0,
  "rx_dropped": 0,
  "rx_overrun": 0,
  "rx_frame": 0
}
```

**来源**: `/sys/class/net/eno1/statistics/` 和 `ethtool -S eno1`

#### DUT 采集的数据

**stream_samples.jsonl**（每秒一条）：

```json
{
  "record_type": "stream_sample",
  "timestamp": 1712649600.123,
  "serial_number": "GV-001",
  "ip_address": "192.168.10.100",
  "frames_received": 5000,
  "frames_lost": 0,
  "resend_requests": 10,
  "resend_failures": 0,
  "buffer_underrun": 0
}
```

**来源**: Aravis 库的流探针 API

**system_samples.jsonl**（每秒一条）：

```json
{
  "record_type": "system_sample",
  "timestamp": 1712649600.123,
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "irq_counts": {
    "eno1": 150000,
    "eno2": 148000
  }
}
```

**来源**: `/proc/stat`, `/proc/meminfo`, `/proc/interrupts`

---

## 配置参数说明

### 网络接口配置

```yaml
generator:
  cameras:
    - serial_number: "GV-001"
      ip_address: "192.168.10.100"  # DUT 的 IP
      interface_name: "eno1"         # 控制主机的接口
```

**注意事项**：
- `ip_address` 必须是 DUT 上存在的 IP
- `interface_name` 必须是控制主机上存在的接口
- 两者必须在物理上连接（通过网线/交换机）

### SSH 配置

```yaml
dut:
  host: "192.168.10.100"    # DUT 的主机名或 IP
  user: "user"              # SSH 用户名（可选）
  port: 22                  # SSH 端口（可选）
  ifaces: ["eno1", "eno2"]  # DUT 上的接口列表
```

**常见问题**：
- 忘记配置 `user` 导致使用错误的 SSH 用户
- `ifaces` 与实际 DUT 接口不匹配
- SSH 密钥未配置导致反复要求输入密码

### 流参数配置

```yaml
stream:
  packet_resend: true            # 是否启用包重传
  socket_buffer_size: 1048576    # Socket 缓冲区大小（字节）
  frame_retention: 200000        # 帧保留数
  packet_timeout: 2000           # 包超时（毫秒）
  packet_request_ratio: 0.25     # 重传请求比例
```

**调优建议**：

| 问题 | 推荐配置 |
|------|----------|
| 偶尔丢包 | 增加 `socket_buffer_size` 到 2097152 |
| 重传过多 | 增加 `packet_timeout` 到 3000 |
| 内存不足 | 减少 `frame_retention` 到 100000 |
| 高丢包环境 | 增加 `packet_request_ratio` 到 0.5 |

### 输出配置

```yaml
output:
  root: artifacts/dual_test    # 输出目录
```

**产物结构**：

```
artifacts/dual_test/
├── preflight/                 # 预检结果
│   └── <timestamp>.json
├── fakecam/                   # Fakecam 状态
│   └── state.json
└── runs/                      # 测试运行
    └── <run-id>/
        ├── raw/               # 原始数据
        │   ├── nic_samples.jsonl
        │   ├── stream_samples.jsonl
        │   ├── system_samples.jsonl
        │   └── events_samples.jsonl
        ├── reports/           # 报告
        │   ├── run.json
        │   └── summary.md
        └── logs/              # 日志
            ├── fakecam.log
            └── orchestrator.log
```

---

## 部署检查清单

### 控制主机（生成器）
- [ ] GVStress 已安装并激活虚拟环境
- [ ] ethtool 已安装（`ethtool --version`）
- [ ] Aravis 库已安装（如果使用 Fakecam）
- [ ] 网络接口静态 IP 已配置并激活
- [ ] SSH 密钥已生成（`~/.ssh/gvstress`）
- [ ] 到 DUT 的 SSH 无密码登录可用
- [ ] 到 DUT 各接口的 ping 测试通过

### DUT（被测设备）
- [ ] Linux 系统可 SSH 访问
- [ ] Python 3.10+ 已安装（`python3 --version`）
- [ ] GVStress 代码已复制到 `/opt/gvstress/`
- [ ] 依赖已安装（`pip3 install pydantic typer`）
- [ ] DUT 代理可运行（`python3 -m gvstress.cli.dut_agent ping`）
- [ ] 网络接口已配置（与控制主机同一网段）

### 网络
- [ ] 控制主机 ↔ DUT 网线已连接
- [ ] 所有静态 IP 已配置（同一网段）
- [ ] ping 测试通过（所有接口）
- [ ] SSH 无密码登录可用
- [ ] 防火墙规则允许 SSH（端口 22）
- [ ] 防火墙规则允许 GigE Vision 流量（端口 3956）

### 配置文件
- [ ] `generator.cameras[].ip_address` 对应 DUT 的 IP
- [ ] `generator.cameras[].interface_name` 对应控制主机的接口
- [ ] `dut.host` 正确（DUT 的 SSH 地址）
- [ ] `dut.ifaces` 列表与实际 DUT 接口匹配
- [ ] `output.root` 目录可写

### 运行前
- [ ] 预检通过（`dut inspect` 返回 `run_validity=valid`）
- [ ] 虚拟环境已激活（`source .venv/bin/activate`）
- [ ] 无其他进程占用网络接口

---

## 常见问题

### Q1: 为什么不直接在 DUT 上运行所有东西？

**A**: GVStress 的设计理念是**模拟真实相机 → DUT 的拓扑**。Fakecam 需要生成视频流并通过物理网络发送给 DUT，这样才能测试：

- 网线质量和长度
- 网卡性能和驱动
- 交换机缓冲区
- 真实网络延迟和抖动
- 端到端丢包率

如果都在 DUT 上运行，就变成"自己发给自己"，失去了测试网络的意义。

---

### Q2: 控制主机和 DUT 可以是同一台机器吗？

**A**: 可以（单机模式），配置如下：

```yaml
dut:
  host: "localhost"
  ifaces: ["lo"]
```

但这**只能测试软件功能，无法测试真实网络环境**。适用于：
- 开发调试 CLI 命令
- 验证配置语法
- 快速测试报告生成

**不适用于**：
- 生产环境验证
- 网络性能测试
- 稳定性验证

---

### Q3: 需要几根网线？

**A**: 取决于测试规模：

| 测试类型 | 网线数量 | 连接方式 |
|----------|----------|----------|
| 单流测试 | 1 根 | 控制主机 eno1 ↔ DUT eno1 |
| 四流测试 | 4 根 | 控制主机 eno1-eno4 ↔ DUT eno1-eno4 |
| 通过交换机 | N+1 根 | N 根设备到交换机 + 1 根交换机互联（如需要） |

**建议**: 使用 Cat6 或更高规格的网线，长度不超过 100 米。

---

### Q4: SSH 连接失败怎么办？

**A**: 按以下步骤排查：

```bash
# 1. 测试基础 SSH
ssh user@192.168.10.100 "hostname"

# 2. 检查 SSH 密钥
ls -la ~/.ssh/gvstress
chmod 600 ~/.ssh/gvstress

# 3. 检查 DUT SSH 服务
ssh user@192.168.10.100 "sudo systemctl status sshd"

# 4. 检查网络连通性
ping 192.168.10.100

# 5. 检查防火墙
ssh user@192.168.10.100 "sudo ufw status"
```

---

### Q5: Fakecam 启动失败

**A**: 常见原因和解决方案：

```bash
# 原因 1: Aravis 未安装
sudo apt install libaravis-0.8-dev

# 原因 2: 接口名称错误
ip link show  # 查看实际接口名

# 原因 3: IP 地址不可路由
ip route get 192.168.10.100  # 检查路由

# 原因 4: GenICam 文件不存在
ls /path/to/camera-a.xml
```

---

### Q6: 预检通过但测试失败

**A**: 可能是以下原因：

1. **网络延迟/抖动**
   ```bash
   # 检查网络质量
   ping -c 100 192.168.10.100
   
   # 查看丢包率
   ping -c 100 192.168.10.100 | grep "packet loss"
   ```

2. **NIC 缓冲区不足**
   ```bash
   # 增加 ring buffer
   sudo ethtool -G eno1 rx 4096
   ```

3. **DUT 负载过高**
   ```bash
   # SSH 到 DUT 查看
   ssh user@192.168.10.100 "top -b -n 1 | head -20"
   ```

4. **查看测试报告定位问题**
   ```bash
   python -m gvstress report show --latest --source artifacts/dual_test/runs
   ```

---

### Q7: 如何分析测试结果？

**A**: 查看生成的报告：

```bash
# 1. 查看判定结果
python -m gvstress report show --latest --json | jq '.verdict'

# 2. 查看归因
python -m gvstress report show --latest --json | jq '.primary_attribution'

# 3. 查看详细报告
cat artifacts/dual_test/runs/<run-id>/reports/summary.md

# 4. 分析 NIC 数据
cat artifacts/dual_test/runs/<run-id>/raw/nic_samples.jsonl | jq '.rx_errors'

# 5. 分析流数据
cat artifacts/dual_test/runs/<run-id>/raw/stream_samples.jsonl | jq '.resend_requests'
```

**判定说明**：

| Verdict | 含义 | 建议措施 |
|---------|------|----------|
| pass | 测试通过 | 继续运行更长测试 |
| warn | 有警告 | 检查轻微丢包/重传 |
| fail | 测试失败 | 查看详细报告，定位问题 |

---

## 下一步

成功运行双设备测试后，建议：

1. **阅读详细文档**：
   - [测试指南](testing-zh.md) - 测试类型和结果分析
   - [部署指南](deployment-zh.md) - 高级配置和性能优化
   - [CLI 参考](cli-reference-zh.md) - 完整命令参考

2. **尝试不同场景**：
   - 冒烟测试 → 快速验证
   - 四流测试 → 中等负载
   - 老化测试 → 长时间稳定性

3. **调优配置**：
   - 根据 NIC 性能调整 socket buffer
   - 根据网络质量调整超时参数
   - 根据测试目标调整采样间隔

4. **分析趋势**：
   - 保留历史运行报告
   - 对比不同版本的性能变化
   - 设置阈值告警
