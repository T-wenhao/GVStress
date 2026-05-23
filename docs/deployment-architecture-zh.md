# 部署架构决策记录（ADR）

**状态：** 已接受
**日期：** 2026-05-20
**背景：** GVStress 数据平面（pktgen/fakecam）和控制平面的部署模式

## 决策

GVStress 支持三种部署模式，数据平面和控制平面的要求之间有明确的边界。

## 支持的部署模式

### 1. Full Native（生产环境推荐）

所有组件在裸机或虚拟机上以 systemd 服务管理的方式原生运行。

- **数据平面**：GVStress 工作进程和 pktgen 以原生进程运行，直接访问 NIC
- **控制平面**：CLI 和编排原生运行
- **指标**：node_exporter + GVStress 指标分开收集

**使用场景：** 运行真实压力测试、基准测试或生产验证。

### 2. Hybrid（Compose 控制 + 原生数据节点）

控制平面服务在 Docker Compose 中运行；生成器/DUT 节点原生运行。

- **控制平面**：Docker Compose 用于仪表板、API 或编排服务
- **数据平面**：GVStress 工作进程通过 SSH 在生成器/DUT 机器上原生运行
- **通信**：从控制容器通过 SSH 到原生节点，或控制平面也原生运行

**使用场景：** 你希望容器化控制服务，但需要裸机性能进行流量生成。

### 3. Full Docker Compose（仅用于开发/演示）

所有组件在 Docker Compose 中运行，用于本地开发或演示。

- **警告**：Docker 桥接网络会引入 NAT、MTU 变更和数据包开销
- **不适合**对性能敏感的 pktgen 流量或精确基准测试
- **可接受**用于：UI 开发、API 测试、工作流验证、低流量演示

**使用场景：** 开发功能、测试控制平面逻辑或演示工具。

## 安全和权限

### `/proc/net/pktgen` 访问

Linux 内核 pktgen 子系统需要提升的权限：

- 写入 `/proc/net/pktgen/` 文件需要 **root** 或 **CAP_NET_ADMIN**
- 与 pktgen 交互的 GVStress 工作进程必须以 root 或具有适当能力运行
- **切勿**在非特权容器中运行 pktgen 工作进程，它们会静默失败或崩溃

**推荐方法：**
```bash
# 原生/systemd 服务
sudo systemctl start gvstress-worker

# 如果使用 Docker（host-network + privileged，见下文）
docker run --network host --privileged gvstress/worker
```

### 能力要求

| 组件 | 所需能力 | 说明 |
|-----------|----------------------|-------|
| GVStress fakecam workers | 无（用户空间 Aravis） | 可以非特权运行 |
| Pktgen workers | `CAP_NET_ADMIN` 或 root | 写入 `/proc/net/pktgen/` |
| DUT agent (SSH) | 无 | 读取 `/sys/class/net/` 统计 |
| node_exporter | 无 | 标准指标收集 |

## 指标架构

### 关注点分离

GVStress 指标和基础设施指标分开收集：

- **node_exporter**：标准 Prometheus 节点指标（CPU、内存、磁盘、网络）
  - 作为单独的 systemd 服务或容器运行
  - 不与 GVStress 工作进程捆绑
  - 由外部 Prometheus 实例抓取

- **GVStress 指标**：应用特定指标（流健康、工作进程状态、测试进度）
  - 由 GVStress 工作进程自身暴露
  - 通过 GVStress 报告管道收集
  - 存储在运行产物中（JSON Lines 格式）

**理由：** 分离这些关注点允许：
1. 基础设施监控的独立扩展
2. node_exporter 可以在多个工作负载间共享
3. GVStress 指标保持与特定测试运行的关联以进行归因

## Docker 网络警告

### Docker 桥接不适合 Pktgen 流量

**关键：** Docker 的默认桥接网络驱动：

1. **增加 NAT 开销** - 数据包被伪装，改变源 IP
2. **修改 MTU** - 桥接 MTU 可能与物理 NIC 不同，导致分片
3. **引入延迟** - veth 对 + 桥接转发增加微秒级延迟
4. **破坏 pktgen** - `/proc/net/pktgen/` 绑定到真实接口，而非容器 veth 接口

**如果你必须容器化数据平面组件：**

```yaml
# docker-compose.yml - 仅用于开发/演示
services:
  gvstress-worker:
    network_mode: host      # 绕过桥接，直接使用主机网络栈
    privileged: true         # 需要用于 /proc/net/pktgen 写入访问
    # 或使用特定能力代替完整 privileged：
    # cap_add:
    #   - NET_ADMIN
    #   - SYS_ADMIN
```

### 何时需要 `network_mode: host` + `privileged`

| 场景 | network_mode | privileged | 原因 |
|----------|-------------|------------|--------|
| Pktgen 流量生成 | `host` | `true` 或 `CAP_NET_ADMIN` | 直接 NIC 访问，`/proc/net/pktgen` 写入 |
| Fakecam（Aravis）在特定 NIC 上 | `host` | `false` | Aravis 需要直接接口绑定 |
| DUT agent（基于 SSH） | N/A | `false` | 远程运行，不需要容器 |
| 控制平面/仪表板 | `bridge`（默认） | `false` | 不需要 NIC 访问 |

## 总结

| 模式 | 数据平面 | 控制平面 | 使用场景 |
|------|-----------|---------------|----------|
| Full Native | 原生/systemd | 原生 | 生产环境、基准测试 |
| Hybrid Compose+Native | 远程节点上原生/systemd | Docker Compose | 容器化控制，裸机数据 |
| Full Compose（开发） | `host` + `privileged` 容器 | Docker Compose | 仅用于开发、演示 |

**经验法则：** 如果你关心数据包级精度，请原生运行数据平面。
