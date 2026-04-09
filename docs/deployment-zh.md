# 部署指南

本指南涵盖在生成器和 DUT（被测设备）机器上安装和配置 GVStress 组件的完整流程。

## 概述

GVStress 由以下组件组成：
- **生成器 (Generator)**: 运行 fakecam 工作进程的机器，模拟 GigE Vision 相机
- **被测设备 (DUT)**: 接收相机流的设备（如图像采集卡、视觉系统）
- **控制主机**: 协调测试的机器（可以与生成器相同）

## 前置要求

### 生成器要求

- Linux 操作系统（推荐 Ubuntu 20.04+）
- Python 3.10+
- 具有静态 IP 的网络接口
- 足够的 CPU 资源支持模拟的相机数量
- Aravis 库（用于 fakecam 工作进程）

### DUT 要求

- 来自生成器/控制主机的 SSH 访问权限
- Python 3.10+（用于代理部署）
- 连接到生成器的网络接口

## 安装

### 生成器安装

**1. 克隆仓库：**
```bash
git clone <repository-url>
cd GVStress
```

**2. 安装依赖：**
```bash
pip install -e .
```

**3. 验证安装：**
```bash
python -m gvstress --version
```

### DUT 代理安装

DUT 代理通过 SSH 远程运行。在 DUT 上安装：

**1. 复制 gvstress 包到 DUT：**
```bash
scp -r src/gvstress user@dut:/opt/gvstress/
```

**2. 在 DUT 上安装依赖：**
```bash
ssh user@dut "pip install pydantic typer"
```

**3. 验证代理：**
```bash
ssh user@dut "python -m gvstress.cli.dut_agent ping"
```

## SSH 配置

配置从生成器到 DUT 的无密码 SSH：

**1. 生成 SSH 密钥（如不存在）：**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/gvstress -N ""
```

**2. 复制密钥到 DUT：**
```bash
ssh-copy-id -i ~/.ssh/gvstress user@dut
```

**3. 测试连接：**
```bash
ssh -i ~/.ssh/gvstress user@dut "hostname"
```

## 二进制依赖

### Aravis（生成器）

需要 Aravis 库进行流探测：

**Ubuntu/Debian:**
```bash
sudo apt install libaravis-0.8-dev
```

**从源码构建:**
```bash
git clone https://github.com/AravisProject/aravis
cd aravis
meson build && cd build
ninja && sudo ninja install
```

**验证安装:**
```bash
arv-viewer-0.8 --version
```

### Pktgen（可选）

用于基线基准测试：

```bash
pip install pktgen
```

### ethtool（预检检查）

用于 NIC 预检：

```bash
sudo apt install ethtool
```

## 网络拓扑

### 典型设置

```
[生成器]                    [DUT]
  eno1 (192.168.10.1) -------- eno1 (192.168.10.11)
  eno2 (192.168.11.1) -------- eno2 (192.168.11.11)
  eno3 (192.168.12.1) -------- eno3 (192.168.12.11)
  eno4 (192.168.13.1) -------- eno4 (192.168.13.11)
```

### 接口配置

**在生成器上配置静态 IP：**

使用 /etc/network/interfaces (Debian/Ubuntu)：
```bash
# /etc/network/interfaces
auto eno1
iface eno1 inet static
    address 192.168.10.1
    netmask 255.255.255.0

auto eno2
iface eno2 inet static
    address 192.168.11.1
    netmask 255.255.255.0

auto eno3
iface eno3 inet static
    address 192.168.12.1
    netmask 255.255.255.0

auto eno4
iface eno4 inet static
    address 192.168.13.1
    netmask 255.255.255.0
```

**使用 NetworkManager：**
```bash
# 配置 eno1
nmcli con mod "Wired connection 1" ipv4.addresses "192.168.10.1/24"
nmcli con mod "Wired connection 1" ipv4.method manual
nmcli con mod "Wired connection 1" ipv4.gateway "192.168.10.254"
nmcli con up "Wired connection 1"

# 配置 eno2
nmcli con mod "Wired connection 2" ipv4.addresses "192.168.11.1/24"
nmcli con mod "Wired connection 2" ipv4.method manual
nmcli con up "Wired connection 2"
```

### DUT 网络配置

DUT 端也需要配置相应的静态 IP：

```
eno1: 192.168.10.11/24
eno2: 192.168.11.11/24
eno3: 192.168.12.11/24
eno4: 192.168.13.11/24
```

## 验证

测试前运行预检检查：

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2,eno3,eno4 \
    --json
```

预期输出显示 `run_validity=valid` 且无错误原因。

### 预检检查项

预检会验证以下内容：

1. **SSH 连接**: 能否通过 SSH 访问 DUT
2. **Python 环境**: DUT 上是否安装了 Python 3.10+
3. **网络接口**: 配置的接口是否存在
4. **IP 连通性**: 生成器能否 ping 通 DUT 的各接口
5. **权限**: SSH 用户是否有足够权限执行必要命令

### 排查预检失败

**SSH 连接失败:**
```bash
# 测试 SSH 连接
ssh -v -i ~/.ssh/gvstress user@dut "hostname"

# 检查 SSH 密钥权限
chmod 600 ~/.ssh/gvstress
chmod 700 ~/.ssh
```

**Python 未安装:**
```bash
# 在 DUT 上安装 Python
ssh user@dut "sudo apt update && sudo apt install -y python3 python3-pip"

# 验证版本
ssh user@dut "python3 --version"
```

**接口不存在:**
```bash
# 列出 DUT 上的网络接口
ssh user@dut "ip link show"

# 检查接口名称是否匹配
ssh user@dut "ip -o link show | awk -F': ' '{print $2}'"
```

## 输出布局

产物存储在配置的输出目录中：

```
artifacts/
├── fakecam-up/       # Fakecam 状态
├── preflight/        # 预检检查结果
├── runs/             # 测试运行产物
│   └── <run-id>/
│       ├── raw/      # JSON Lines 采样数据
│       ├── reports/  # run.json, summary.md
│       └── logs/     # 工作进程日志
└── pktgen/           # 基线基准测试
```

### 产物说明

**fakecam-up/:**
- `state.json`: FakeCameraManager 的运行时状态
- 包含每个相机的序列号、IP、接口、PID 和健康状态

**preflight/:**
- `<timestamp>.json`: 预检检查结果
- 包含 run_validity 和失败原因（如有）

**runs/<run-id>/:**
- `raw/nic_samples.jsonl`: NIC 统计采样
- `raw/stream_samples.jsonl`: 流状态采样
- `raw/system_samples.jsonl`: 系统指标采样
- `raw/events_samples.jsonl`: 事件记录
- `reports/run.json`: 结构化运行报告
- `reports/summary.md`: 人类可读的摘要报告
- `logs/`: 各工作进程的日志文件

**pktgen/:**
- 基线基准测试结果
- 用于与压力测试结果对比

## 配置示例

 ### 多相机配置 (examples/fakecam_4p.yaml)

```yaml
generator:
  cameras:
    - serial_number: "GV-001"
      ip_address: "192.168.10.11"
      interface_name: "eno1"
    - serial_number: "GV-002"
      ip_address: "192.168.11.11"
      interface_name: "eno2"
    - serial_number: "GV-003"
      ip_address: "192.168.12.11"
      interface_name: "eno3"
    - serial_number: "GV-004"
      ip_address: "192.168.13.11"
      interface_name: "eno4"
```

### 场景配置 (examples/scenario_smoke.yaml)

```yaml
dut:
  host: "192.168.10.11"
  ifaces: ["eno1", "eno2", "eno3", "eno4"]
scenarios:
  - name: smoke
    duration: 60
    warmup: 10
    cooldown: 5
```

## 性能优化

### NIC 调优

**增加 Ring Buffer：**
```bash
# 查看当前设置
ethtool -g eno1

# 增加 RX ring buffer
ethtool -G eno1 rx 4096
```

**调整 IRQ 亲和性：**
```bash
# 查看 IRQ 分布
cat /proc/interrupts | grep eno1

# 将 IRQ 绑定到特定 CPU 核心
echo 1 > /proc/irq/<irq-number>/smp_affinity
```

### 系统调优

**增加文件描述符限制：**
```bash
# 查看当前限制
ulimit -n

# 增加限制（临时）
ulimit -n 65536

# 永久修改
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
```

**禁用 IRQ 平衡（可选）：**
```bash
# 停止 irqbalance 服务
sudo systemctl stop irqbalance
sudo systemctl disable irqbalance
```

## 完整部署检查清单

在开始测试前，确保完成以下步骤：

- [ ] 生成器已安装 GVStress 和所有依赖
- [ ] DUT 已安装 Python 3.10+ 和必要依赖
- [ ] SSH 无密码连接已配置并测试通过
- [ ] 所有网络接口已配置静态 IP
- [ ] 网络连通性已验证（ping 测试）
- [ ] Aravis 库已安装并验证
- [ ] 预检检查通过
- [ ] 时钟同步（如需要，配置 NTP）

## 常见问题

### Aravis 安装问题

**问题**: `libaravis-0.8-dev` 包不可用

**解决**: 从源码构建
```bash
sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    libgirepository1.0-dev gir1.2-aravis-0.8
```

### SSH 连接超时

**问题**: SSH 连接超时或被拒绝

**解决**:
1. 检查防火墙规则：`sudo ufw status`
2. 验证 SSH 服务运行：`sudo systemctl status sshd`
3. 检查网络路由：`ip route get <dut-ip>`

### 端口冲突

**问题**: Fakecam 启动失败，端口已被占用

**解决**:
1. 查找占用端口的进程：`sudo netstat -tlnp | grep 3956`
2. 终止冲突进程或更改配置中的端口

### 内存不足

**问题**: 长期运行时内存耗尽

**解决**:
1. 监控内存使用：`watch -n1 'free -h'`
2. 减少同时运行的相机数量
3. 增加系统内存或 swap 空间

## 卸载

### 生成器卸载

```bash
# 停用虚拟环境（如使用）
deactivate

# 卸载 Python 包
pip uninstall gvstress

# 删除项目目录
cd .. && rm -rf GVStress
```

### DUT 卸载

```bash
# SSH 到 DUT
ssh user@dut

# 卸载 Python 依赖
pip uninstall pydantic typer

# 删除 gvstress 目录
sudo rm -rf /opt/gvstress
```

## 升级

### 升级到新版本

```bash
# 拉取最新代码
git pull origin main

# 重新安装
pip install -e . --upgrade

# 验证版本
python -m gvstress --version
```

### 迁移配置

新版本可能引入配置格式变更。升级后：

1. 检查配置文件是否仍然有效
2. 运行预检确保兼容性
3. 运行冒烟测试验证基本功能
