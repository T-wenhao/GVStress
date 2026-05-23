# Web 监控操作指南

本指南为运维人员提供在生产环境中部署、配置和监控 GVStress 的全面信息。

## 目录

- [架构概览](#架构概览)
- [部署模式](#部署模式)
- [指标与监控](#指标与监控)
- [测试策略](#测试策略)
- [运维流程](#运维流程)
- [故障排除](#故障排除)

## 架构概览

GVStress 是一个 GigE Vision 压力测试框架，用于验证相机流在负载下的稳定性。架构将数据平面（流量生成）与控制平面（编排和监控）分离。

### 组件架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        控制平面 (Control Plane)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   CLI 工具   │  │   Web API    │  │  控制器服务 (Controller)│  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ SSH / HTTP
                               │
┌─────────────────────────────────────────────────────────────────┐
│                        数据平面 (Data Plane)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Fakecam      │  │   DUT Agent  │  │   pktgen Worker      │  │
│  │ Workers      │  │   (SSH)      │  │   (Kernel)           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 关键组件

| 组件 | 用途 | 网络要求 |
|-----------|---------|---------------------|
| Fakecam Workers | 生成合成 GigE Vision 流 | 直接 NIC 访问，静态 IP |
| DUT Agent | 收集 NIC 统计信息、系统指标、流健康状态 | 从控制主机通过 SSH 访问 |
| pktgen Worker | 内核级数据包生成 | Root/CAP_NET_ADMIN，`/proc/net/pktgen` 访问权限 |
| Controller Service | 作业编排和生命周期管理 | HTTP API 端点 |
| CLI Tool | 测试执行的命令行界面 | 通过 SSH 连接到远程节点 |

## 部署模式

GVStress 支持三种部署模式，在便利性和性能之间有不同的权衡。

### 部署矩阵

| 模式 | 数据平面 | 控制平面 | 使用场景 | 性能 |
|------|-----------|---------------|----------|-------------|
| **Full Native** | 原生/systemd | 原生 | 生产环境、基准测试 | 最高 |
| **Hybrid** | 远程节点上原生运行 | Docker Compose | 容器化控制，裸机数据平面 | 高 |
| **Full Compose** | Docker 容器 | Docker Compose | 开发环境、演示 | 有限 |

### 1. Full Native 部署（生产环境推荐）

所有组件在裸机或虚拟机上以 systemd 服务管理的方式原生运行。

**单节点设置：**

```bash
# 安装 GVStress
pip install -e .

# 启动 fakecam 工作进程
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 运行预检检查
python -m gvstress dut inspect \
    --host localhost \
    --ifaces eno1,eno2,eno3,eno4 \
    --json

# 执行测试
python -m gvstress test soak --config examples/scenario_soak.yaml
```

**双节点设置：**

```bash
# 生成器节点 - 启动 fakecam
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# DUT 节点 - 配置 SSH 访问
# 控制主机通过远程 DUT 运行测试
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --dut-host dut.example.com \
    --dut-user admin
```

### 2. Hybrid 部署（Compose 控制 + 原生数据节点）

控制平面服务在 Docker Compose 中运行；生成器/DUT 节点原生运行。

**控制平面（Docker Compose）：**

```yaml
# docker-compose.yml
services:
  gvstress-controller:
    image: gvstress/controller:latest
    ports:
      - "8080:8080"
    volumes:
      - /var/lib/gvstress:/data
    environment:
      - DATA_DIR=/data
```

**数据节点（原生）：**

```bash
# 在生成器节点上 - 原生运行工作进程
sudo systemctl start gvstress-worker

# 在 DUT 节点上 - 确保 SSH 访问和代理可用性
python -m gvstress.cli.dut_agent ping
```

**Hybrid 命令示例：**

```bash
# 从控制容器通过 SSH 在原生节点上执行
docker exec gvstress-controller \
    python -m gvstress test soak \
    --config /config/scenario_soak.yaml \
    --generator-host gen1.example.com \
    --dut-host dut1.example.com
```

### 3. Full Docker Compose（仅用于开发）

**警告：** Docker 桥接网络会引入 NAT、MTU 变更和数据包开销。不适用于对性能敏感的 pktgen 流量。

```yaml
# docker-compose.yml - 仅用于开发
devices:
  gvstress-worker:
    image: gvstress/worker:latest
    network_mode: host      # 需要用于 NIC 访问
    privileged: true         # 需要用于 /proc/net/pktgen
    volumes:
      - /proc/net/pktgen:/proc/net/pktgen
```

### 能力要求

| 组件 | 所需能力 | 是否需要特权 |
|-----------|----------------------|---------------------|
| Fakecam workers | 无 | 否 |
| pktgen workers | CAP_NET_ADMIN 或 root | 是（或 cap_add） |
| DUT agent (SSH) | 无 | 否 |
| node_exporter | 无 | 否 |

## 指标与监控

### node_exporter 与 GVStress 自定义指标

GVStress 使用关注点分离的方式进行指标收集：

#### node_exporter（基础设施指标）

node_exporter 提供标准的 Prometheus 节点指标：

- **CPU**：使用率百分比、平均负载
- **内存**：利用率、swap 使用
- **磁盘**：I/O 速率、空间使用
- **网络**：接口统计（数据包、字节、错误）
- **系统**：运行时间、文件描述符

**部署：**

```bash
# 作为 systemd 服务运行
sudo systemctl start prometheus-node-exporter

# 或作为 Docker 容器运行
docker run -d \
  --net="host" \
  --pid="host" \
  -v "/:/host:ro,rslave" \
  prom/node-exporter:latest \
  --path.rootfs=/host
```

**抓取配置：**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets: ['generator:9100', 'dut:9100']
```

#### GVStress 自定义指标（应用指标）

GVStress 暴露应用特定的指标：

- **流健康状态**：接收的帧、丢失的帧、重传请求
- **工作进程状态**：活跃的工作进程、相机状态
- **测试进度**：采样计数、持续时间、判定结果
- **NIC 统计**：每个接口的数据包计数（来自 DUT）
- **系统指标**：测试期间的 CPU、内存（来自 DUT agent）

**收集方法：**

GVStress 指标通过报告管道收集并存储在运行产物中：

```
artifacts/<scenario>/runs/<run-id>/
├── raw/
│   ├── nic_samples.jsonl       # 每个采样的 NIC 统计
│   ├── stream_samples.jsonl    # 流探测记录
│   ├── system_samples.jsonl    # 系统指标
│   └── events_samples.jsonl    # 状态转换
└── reports/
    ├── run.json                # 结构化运行报告
    └── summary.md              # 人类可读的摘要
```

#### 关键差异

| 方面 | node_exporter | GVStress 自定义指标 |
|--------|--------------|------------------------|
| **范围** | 整个基础设施 | 测试特定 |
| **粒度** | 系统级 | 每个流、每个接口 |
| **持久化** | 时序数据库（Prometheus） | 运行产物（JSON Lines） |
| **归属** | 节点级 | 测试运行级 |
| **收集** | 拉取（抓取） | 推送（测试期间） |
| **生命周期** | 持续 | 测试持续时间 |

**分离的理由：**

1. **独立扩展**：node_exporter 可以在多个工作负载间共享
2. **测试归属**：GVStress 指标保持与特定测试运行的关联
3. **运维灵活性**：即使测试未运行时，基础设施监控也能继续

### 监控架构

```
┌─────────────────────────────────────────────────────────────┐
│                    监控栈 (Monitoring Stack)                   │
├─────────────────────────────────────────────────────────────┤
│  Prometheus (node_exporter)    │   GVStress 产物 (Artifacts)   │
│  - 持续收集                   │   - 每次测试收集               │
│  - 长期趋势                   │   - 运行归属                   │
│  - 基础设施健康               │   - 流特定数据                 │
└─────────────────────────────────────────────────────────────┘
```

### 报告语义

#### 运行报告（run.json）

运维人员的关键字段：

| 字段 | 值 | 描述 |
|-------|--------|-------------|
| `verdict` | pass, warn, fail, not_applicable | 整体测试结果 |
| `run_validity` | valid, invalid_environment, invalid_prereq, interrupted | 结果是否可信 |
| `primary_attribution` | nic, stream, mixed, environment, unknown | 故障所在位置 |
| `aborted` | true, false | 测试是否被手动中止 |

#### 判定结果解读

- **pass**：测试成功完成，无问题
- **warn**：测试完成，有轻微问题（如偶尔的数据包重试）
- **fail**：测试因错误超过阈值而失败
- **not_applicable**：配置或环境对测试无效

#### 归因指南

| 归因 | 含义 | 操作 |
|-------------|---------|--------|
| `nic` | 网络接口故障 | 检查驱动/固件、网线、MTU |
| `stream` | 流处理故障 | 调整 Aravis 设置、重传逻辑 |
| `mixed` | 多个域受影响 | 需要全面调查 |
| `environment` | 设置/配置问题 | 验证拓扑、SSH、依赖项 |
| `unknown` | 无法确定 | 查看日志、增加采样 |

### pktgen 限制

**重要：** pktgen 提供基线基准测试，但有重要限制：

1. **不等同于 GigE Vision**：pktgen 生成原始数据包，而非 GigE Vision 协议流量
2. **无协议开销**：pktgen 不包含 GVSP（GigE Vision Streaming Protocol）头部
3. **无重传逻辑**：pktgen 不实现数据包重传机制
4. **仅内核级**：pktgen 在内核级运行，绕过用户空间处理

**pktgen 适用于：**
- 原始吞吐量基线测量
- 网络基础设施验证
- 驱动性能测试

**请勿将 pktgen 用于：**
- GigE Vision 协议验证
- 应用级性能测试
- 流稳定性评估

### RX 背景流量警告

**关键：** RX（接收）数据包计数器可能包含与测试无关的背景流量。

#### 为什么 RX 增量可能包含背景流量

1. **广播/组播流量**：ARP、LLDP、IPv6 邻居发现
2. **管理流量**：SNMP、监控代理、SSH 连接
3. **操作系统服务**：NTP、DNS、系统更新
4. **其他应用**：DUT 上的共存服务

#### 对测量的影响

```
观察到的 RX = 测试流量 + 背景流量
```

这意味着：
- **RX 计数器可能高于**实际测试流量
- **基于 TX/RX 差异的丢包计算**可能不准确
- **每个接口的总数**包含所有接收的数据包

#### 缓解策略

1. **使用专用测试接口**：在专用 NIC 上隔离测试流量
2. **基线测量**：测试前测量背景流量
3. **按协议过滤**：尽可能专门过滤 GigE Vision 流量
4. **比较 TX/RX**：交叉引用生成器 TX 与 DUT RX

#### 背景流量估算示例

```bash
# 测试前测量背景流量
python -m gvstress dut inspect --host dut --ifaces eno1 --json
# 记录 rx_packets 基线

# 运行测试
python -m gvstress test smoke --config examples/scenario_smoke.yaml

# 将增量与预期测试流量进行比较
```

## 测试策略

### 测试矩阵

GVStress 在多个级别实现全面的测试策略：

| 测试级别 | 目的 | 工具 | 频率 |
|------------|---------|-------|-----------|
| **单元** | 组件隔离 | pytest | 每次提交 |
| **集成** | 组件交互 | pytest + fixtures | 每次提交 |
| **服务** | API 契约验证 | pytest + HTTP client | 发布前 |
| **Compose** | 容器编排 | docker-compose | 发布前 |
| **硬件** | 物理 NIC 验证 | 真实硬件 | 每周 |
| **浏览器** | UI/UX 验证 | Playwright | 发布前 |

### 单元测试

**范围：** 隔离的单个函数、类和模块。

**命令：**

```bash
pytest tests/unit/ -v --cov=gvstress
```

**覆盖区域：**
- 配置解析和验证
- 指标计算函数
- 状态机转换
- 工具函数

### 集成测试

**范围：** 组件交互和数据流。

**命令：**

```bash
pytest tests/integration/ -v
```

**覆盖区域：**
- Fakecam 工作进程生命周期
- DUT agent 通信
- 报告生成管道
- 产物存储

### 服务测试

**范围：** API 契约和服务边界。

**命令：**

```bash
pytest tests/service/ -v
```

**覆盖区域：**
- 控制器服务端点
- 作业生命周期管理
- 拓扑验证
- 状态转换强制执行

### Compose 测试

**范围：** Docker Compose 编排。

**命令：**

```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

**覆盖区域：**
- 服务启动和健康检查
- 服务间通信
- 卷挂载和权限
- 网络配置

### 硬件测试

**范围：** 物理硬件验证。

**要求：**
- 物理生成器和 DUT 机器
- 专用网络接口
- 静态 IP 配置

**命令：**

```bash
# 完整硬件验证套件
python -m gvstress test soak --config examples/scenario_soak.yaml

# 快速验证
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

**覆盖区域：**
- 真实 NIC 吞吐量
- 负载下的丢包
- 驱动稳定性
- 硬件时间戳精度

### 浏览器测试

**范围：** Web UI 验证。

**命令：**

```bash
pytest tests/browser/ -v --headed
```

**覆盖区域：**
- 仪表板渲染
- 作业状态显示
- 报告可视化
- 用户交互

### 测试配置示例

#### 冒烟测试（快速验证）

```yaml
# examples/scenario_smoke.yaml
scenarios:
  - name: smoke
    duration: 60      # 1 分钟
    warmup: 10
    cooldown: 5
```

#### 老化测试（长期稳定性）

```yaml
# examples/scenario_soak.yaml
scenarios:
  - name: soak
    duration: 1800    # 30 分钟
    warmup: 10
    cooldown: 5
```

#### 丢包注入测试（弹性）

```yaml
# examples/scenario_loss.yaml
scenarios:
  - name: loss_injection
    duration: 300
    warmup: 10
    cooldown: 5
generator:
  cameras:
    - ip_address: 192.168.10.11
      gvsp_lost_ratio: 0.01  # 1% 丢包
```

## 运维流程

### 飞行前检查清单

运行生产测试前：

1. **验证网络连通性**
   ```bash
   python -m gvstress dut inspect --host <dut> --ifaces <ifaces> --json
   ```

2. **检查 fakecam 状态**
   ```bash
   python -m gvstress fakecam status --config <config> --json
   ```

3. **验证配置**
   ```bash
   python -m gvstress config validate --config <config>
   ```

4. **检查磁盘空间**
   ```bash
   df -h <artifact-root>
   ```

5. **检查系统资源**
   ```bash
   free -h && uptime
   ```

### 运行生产测试

```bash
# 1. 启动 fakecam 工作进程
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 2. 运行飞行前检查
python -m gvstress dut inspect \
    --host dut.example.com \
    --ifaces eno1,eno2,eno3,eno4 \
    --user admin \
    --json

# 3. 执行老化测试
python -m gvstress test soak \
    --config examples/scenario_soak.yaml \
    --output /data/artifacts

# 4. 生成报告
python -m gvstress report show --latest --source /data/artifacts/soak/runs

# 5. 停止 fakecam
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### 测试期间监控

**实时指标：**

```bash
# 监视 DUT 指标
watch -n 5 'python -m gvstress dut inspect --host dut --ifaces eno1 --json'

# 监控产物
tail -f artifacts/soak/runs/<run-id>/logs/worker.log
```

**Prometheus 查询：**

```promql
# 网络吞吐量
rate(node_network_receive_bytes_total{device="eno1"}[5m])

# CPU 使用率
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 内存利用率
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100
```

### 测试后流程

1. **归档产物**
   ```bash
   tar czf soak-$(date +%Y%m%d-%H%M%S).tar.gz artifacts/soak/
   ```

2. **清理旧运行**
   ```bash
   find artifacts/soak/runs -type d -mtime +30 -exec rm -rf {} +
   ```

3. **生成趋势报告**
   ```bash
   python -m gvstress report trend --source artifacts/soak/runs --days 30
   ```

## 故障排除

### 常见问题

#### Fakecam 启动失败

**症状：**
```
Error: Failed to start fakecam workers
```

**原因：**
- Aravis 库未安装
- 配置中的接口名称不正确
- IP 地址不可路由
- 权限不足

**解决方案：**
```bash
# 验证 Aravis 安装
python -c "import gi; gi.require_version('Aravis', '0.8')"

# 检查接口名称
ip link show

# 验证 IP 配置
ip addr show <interface>
```

#### 未收集到流采样

**症状：**
- `stream_samples.jsonl` 为空
- 流指标全为零

**原因：**
- Fakecam 未运行
- 防火墙阻止流量
- 配置中的 IP 地址错误
- GenICam 文件缺失

**解决方案：**
```bash
# 验证 fakecam 状态
python -m gvstress fakecam status --config <config> --json

# 检查防火墙
sudo iptables -L -n | grep <port>

# 验证 GenICam 文件
ls -la /usr/share/arv-fakecam/
```

#### 飞行前检查失败

**症状：**
```json
{
  "run_validity": "invalid_prereq",
  "reasons": ["interface eno1 not found"]
}
```

**解决方案：**
1. 查看输出中的 `reasons`
2. 修复环境问题
3. 重新运行飞行前检查

#### pktgen 权限被拒绝

**症状：**
```
PermissionError: [Errno 13] Permission denied: '/proc/net/pktgen/kpktgend_0'
```

**解决方案：**
```bash
# 使用 sudo 运行
sudo python -m gvstress baseline pktgen --config <config>

# 或添加能力（如果使用容器）
docker run --cap-add=NET_ADMIN --cap-add=SYS_ADMIN ...
```

### 日志位置

| 组件 | 日志位置 |
|-----------|-------------|
| Fakecam workers | `artifacts/<scenario>/logs/fakecam.log` |
| DUT agent | `artifacts/<scenario>/logs/dut_agent.log` |
| Test runner | `artifacts/<scenario>/runs/<run-id>/logs/runner.log` |
| Controller service | `/var/log/gvstress/controller.log` |

### 获取帮助

1. **查看文档：** 查看[测试指南](testing-zh.md)和[部署指南](deployment-zh.md)
2. **查看日志：** 检查组件日志以获取错误详情
3. **验证配置：** 使用 `python -m gvstress config validate`
4. **运行飞行前检查：** 使用 `python -m gvstress dut inspect` 验证环境

## 参考

- [测试指南](testing-zh.md) - 详细测试流程
- [部署指南](deployment-zh.md) - 安装和配置
- [部署架构 ADR](deployment-architecture-zh.md) - 架构决策
- [迁移指南](migration-from-soak-test.md) - 从临时脚本迁移
