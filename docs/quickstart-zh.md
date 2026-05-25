# 快速入门指南

本指南帮助您在 5 分钟内开始使用 GVStress 进行第一个压力测试。

## 前提条件

确保您有以下环境：

- Linux 机器 (Ubuntu 20.04+ 推荐)
- Python 3.10+
- 至少一个可用的网络接口
- 对被测设备 (DUT) 的 SSH 访问权限（可选，本地测试不需要）

## 1. 安装 GVStress

### 克隆仓库

```bash
git clone <repository-url>
cd GVStress
```

### 安装依赖

```bash
pip install -e .
```

### 验证安装

```bash
python -m gvstress --version
python -m gvstress --help
```

如果显示版本号，说明安装成功。

### 验证本机节点能力

```bash
python -m gvstress node health --json
python -m gvstress node capabilities --json
```

这些命令不需要真实相机或 DUT，适合先确认本机 Python 包、节点状态和基础能力
检测是否正常。

## 2. 安装可选依赖

### Aravis（用于 fakecam）

如果您要运行模拟相机：

```bash
# Ubuntu/Debian
sudo apt install libaravis-0.8-dev

# 验证
arv-viewer-0.8 --version
```

### ethtool（用于预检）

```bash
sudo apt install ethtool
```

## 3. 准备配置文件

### 复制示例配置

```bash
# 示例配置位于 examples/ 目录
ls examples/
```

典型配置文件：
- `fakecam_4p.yaml` - 4 相机配置
- `scenario_smoke.yaml` - 冒烟测试场景
- `scenario_4stream.yaml` - 四流测试场景

### 查看示例配置

**fakecam_4p.yaml**：
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

**scenario_smoke.yaml**：
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

### 修改配置

**您需要修改：**

1. **网络接口名称**：将 `interface_name: eno1` 中的 `eno1` 替换为您的实际接口名称
   ```bash
   # 查看您的网络接口
   ip link show
   ```

2. **IP 地址**：根据您的网络拓扑调整 `ip_address`

3. **DUT 主机名**：如果有远程 DUT，修改 `dut.host`

**修改示例**：
```bash
cp examples/fakecam_4p.yaml my_fakecam.yaml
cp examples/scenario_smoke.yaml my_scenario.yaml

# 使用编辑器修改
vim my_fakecam.yaml
vim my_scenario.yaml
```

## 4. 运行第一个测试

### 步骤 1: 启动模拟相机

```bash
python -m gvstress fakecam up --config my_fakecam.yaml
```

**预期输出**：
```
Starting 4 fake cameras...
  GV-001 → 192.168.10.11 (eno1) [OK]
  GV-002 → 192.168.11.11 (eno2) [OK]
  GV-003 → 192.168.12.11 (eno3) [OK]
  GV-004 → 192.168.13.11 (eno4) [OK]
```

**检查状态**：
```bash
python -m gvstress fakecam status --config my_fakecam.yaml --json | jq .
```

### 步骤 2: 运行预检（可选）

如果有远程 DUT：
```bash
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2,eno3,eno4 \
    --json | jq .
```

### 步骤 3: 运行冒烟测试

```bash
python -m gvstress test smoke --config my_scenario.yaml
```

**预期输出**：
```
[2024-01-01 10:00:00] Starting smoke test...
[2024-01-01 10:00:05] Preflight: PASS
[2024-01-01 10:00:05] Warming up (10s)...
[2024-01-01 10:00:15] Steady state (60s)...
[2024-01-01 10:01:15] Cooldown (5s)...
[2024-01-01 10:01:20] Test completed
[2024-01-01 10:01:20] Verdict: PASS
[2024-01-01 10:01:20] Report: artifacts/smoke/runs/abc123/reports/summary.md
```

### 步骤 4: 查看报告

**查看摘要报告**：
```bash
python -m gvstress report show --latest --source artifacts/smoke/runs
```

**查看 JSON 报告**：
```bash
python -m gvstress report show --latest --source artifacts/smoke/runs --json | jq .
```

**查看生成的 Markdown 报告**：
```bash
cat artifacts/smoke/runs/<run-id>/reports/summary.md
```

### 步骤 5: 启动本机 Web 监控（可选）

如果只想在本机查看任务、报告索引和 `/metrics`，可以启动 Controller 和 Web UI：

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

另开一个终端：

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

打开 `http://localhost:8080/`，或直接检查 API：

```bash
curl http://localhost:8079/health
curl http://localhost:8080/api/nodes
curl http://localhost:8080/metrics
```

### 步骤 6: 停止模拟相机

```bash
python -m gvstress fakecam down --config my_fakecam.yaml
```

## 5. 理解测试结果

### 通过 (PASS)

```
Verdict: PASS
Primary Attribution: nic
```

表示测试通过，问题（如有）主要归因于 NIC。

### 警告 (WARN)

```
Verdict: WARN
Reasons: ["Minor packet retries detected"]
```

表示有次要问题，但不影响主要功能。

### 失败 (FAIL)

```
Verdict: FAIL
Run Validity: invalid_environment
Reasons: ["SSH connection failed", "Interface eno3 not found"]
```

表示测试失败，需要检查环境问题。

## 6. 下一步

### 运行其他测试场景

**四流测试**：
```bash
python -m gvstress test four-stream --config my_scenario.yaml
```

**老化测试**：
```bash
python -m gvstress test soak --config my_scenario.yaml
```

**丢包测试**：
```bash
python -m gvstress test loss-injection --config my_scenario.yaml
```

### 基线测试

```bash
python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml
```

### 自定义配置

根据您的实际需求修改配置文件：

1. **调整相机数量**：在 `generator.cameras` 中增减相机条目（需要 `serial_number`, `ip_address`, `interface_name`）
3. **修改测试时长**：编辑 `scenarios: - name: smoke` 下的 `duration`, `warmup`, `cooldown`
3. **自定义流参数**：调整 `stream.packet_resend`, `stream.socket_buffer_size` 等

## 常见问题

### Q: fakecam 启动失败

**A**: 检查以下几点：
1. Aravis 是否正确安装：`arv-viewer-0.8 --version`
2. 网络接口名称是否正确：`ip link show`
3. IP 地址是否可路由：`ip route get <camera-ip-address>`

### Q: 测试显示连接失败

**A**: 如果是远程 DUT 测试：
1. 验证 SSH 连接：`ssh user@dut "hostname"`
2. 检查 SSH 密钥配置
3. 确认 DUT 上安装了 Python

### Q: 找不到网络接口

**A**: 本地测试需要使用存在的接口：
```bash
# 查看可用接口
ip link show

# 修改配置文件中的 interface_name 值
# 例如将 eno1 改为 eth0 或 ens1
```

### Q: 如何查看详细日志？

**A**: 日志存储在产物目录中：
```bash
# 查看工作进程日志
ls artifacts/<scenario>/runs/<run-id>/logs/

# 查看特定日志
cat artifacts/<scenario>/runs/<run-id>/logs/fakecam.log
```

## 快速参考

### 常用命令

```bash
# 启动相机
python -m gvstress fakecam up --config <config.yaml>

# 查看相机状态
python -m gvstress fakecam status --config <config.yaml> --json

# 运行测试
python -m gvstress test smoke --config <config.yaml>

# 查看最新报告
python -m gvstress report show --latest --source artifacts/<scenario>/runs

# 停止相机
python -m gvstress fakecam down --config <config.yaml>
```

### 配置文件位置

| 配置 | 文件 |
|------|------|
| 4 相机示例 | `examples/fakecam_4p.yaml` |
| 冒烟测试 | `examples/scenario_smoke.yaml` |
| 四流测试 | `examples/scenario_4stream.yaml` |
| 老化测试 | `examples/scenario_soak.yaml` |
| 丢包测试 | `examples/scenario_loss.yaml` |
| 基线测试 | `examples/pktgen_4p.yaml` |

### 输出目录结构

```
artifacts/
├── smoke/
│   └── runs/
│       └── <run-id>/
│           ├── raw/              # 原始数据
│           ├── reports/          # 报告
│           │   ├── run.json
│           │   └── summary.md
│           └── logs/             # 日志
└── fakecam-up/                   # Fakecam 状态
```

## 获取帮助

### 查看更多文档

- [测试指南](testing-zh.md) - 详细的测试类型和结果分析
- [部署指南](deployment-zh.md) - 安装和配置说明
- [CLI 参考](cli-reference-zh.md) - 完整的命令参考

### 获取命令帮助

```bash
# 主帮助
python -m gvstress --help

# 子命令帮助
python -m gvstress fakecam --help
python -m gvstress fakecam up --help
python -m gvstress test smoke --help
```

### 在线资源

- GitHub 仓库
- 问题追踪
- 讨论区

---

**恭喜！** 您已经成功运行了第一个 GVStress 测试。继续探索更多功能和配置选项吧！
