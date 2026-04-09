# GVStress

GigE Vision 压力测试框架，用于验证相机流在负载下的稳定性。

## 概述

GVStress 提供工具来模拟多个 GigE Vision 相机，并对被测设备 (DUT，如图像采集卡或视觉系统) 进行压力测试。它包含：

- **Fakecam 工作进程** - 使用 Aravis 生成合成的 GigE Vision 视频流
- **DUT 探针** - 用于 NIC 统计、系统指标和流健康状态监控
- **预检 (Preflight)** - 在测试执行前验证环境就绪状态
- **结构化报告** - 包含运行产物、摘要报告和判定归因
- **远程 DUT 支持** - 通过 SSH 实现真实网络拓扑测试

## 安装

```bash
pip install -e .
```

### 依赖项

- Python 3.10+
- Aravis 库 (用于 fakecam 工作进程)
- ethtool (用于预检 NIC 检查)
- SSH 访问 DUT (用于远程场景)

## 快速开始

### 1. 配置 Fakecam

定义虚拟相机配置：

```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

检查状态：

```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

### 2. 验证 DUT 就绪状态

运行预检检查：

```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### 3. 运行测试场景

冒烟测试 (快速验证)：

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

老化测试 (长时间稳定性)：

```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

### 4. 查看报告

最新运行报告：

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

## 项目结构

```
src/gvstress/
├── cli/                     # 命令行接口模块
│   ├── main.py              # CLI 主应用
│   ├── test.py              # 测试场景命令
│   ├── fakecam.py           # 模拟相机管理命令
│   ├── dut.py               # DUT 探测命令
│   ├── report.py            # 报告查看/导出命令
│   └── baseline.py          # 基线测试命令
│
├── core/                    # 核心引擎模块
│   ├── orchestrator.py      # 运行编排器
│   ├── scenario_engine.py   # 场景引擎
│   ├── verdict.py           # 结果判定引擎
│   ├── runner.py            # 命令执行器 (本地/SSH)
│   └── preflight.py         # 预检模块
│
├── fakecam/                 # 模拟相机模块
│   ├── manager.py           # 相机管理器
│   └── worker.py            # 单相机工作进程
│
├── dut/                     # 设备探测模块
│   ├── nic_probe.py         # NIC 统计探测
│   ├── stream_probe.py      # 流状态探测
│   └── system_probe.py      # 系统 CPU/IRQ 探测
│
├── config/                  # 配置模块
│   ├── models.py            # Pydantic 配置模型
│   └── loader.py            # YAML 配置加载器
│
├── report/                  # 报告模块
│   ├── models.py            # 报告数据模型
│   ├── renderer.py          # Markdown 渲染器
│   └── writer.py            # JSON 写入器
│
└── baseline/                # 基线测试模块
    └── pktgen_runner.py     # pktgen 基线测试
```

## 产物布局

```
artifacts/
├── <scenario-name>/     # 场景输出 (如 smoke, soak)
│   ├── preflight/       # 预检检查结果
│   ├── fakecam/         # Fakecam 状态 (如适用)
│   └── runs/
│       └── <run-id>/
│           ├── raw/      # JSON Lines 原始采样数据
│           ├── reports/  # run.json, summary.md
│           └── logs/     # 工作进程日志
└── pktgen/              # 基线基准测试
```

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

## CLI 命令一览

```
gvstress [OPTIONS] COMMAND [ARGS]...

全局选项:
  --version, -v    显示版本号并退出

命令组:
  fakecam      模拟相机生命周期管理
  dut          DUT (被测设备) 检查
  test         运行压力测试场景
  report       查看和导出测试报告
  baseline     运行基线基准测试
  dut-agent    远程 DUT 代理
```

### 测试场景类型

| 场景 | 持续时间 | 预热 | 冷却 | 用途 |
|------|----------|------|------|------|
| smoke | 60s | 10s | 5s | 快速验证 |
| four_stream | 300s | 10s | 5s | 多流压力测试 |
| soak | 1800s | 10s | 5s | 长期稳定性 |
| loss_injection | 300s | 10s | 5s | 丢包恢复能力 |

## 架构说明

GVStress 采用模块化设计，各组件职责明确：

### 核心组件

1. **编排器 (RunOrchestrator)**：协调测试的所有阶段，包括预检、预热、稳态运行、冷却和报告生成

2. **场景引擎 (ScenarioEngine)**：根据配置构建测试计划，定义各阶段的持续时间

3. **判定引擎 (VerdictEngine)**：基于收集的证据（NIC 统计、流状态、系统指标）判定测试结果（PASS/WARN/FAIL）

4. **探针 (Probes)**：
   - NICProbe：采集网卡统计（rx_packets、rx_errors、rx_dropped）
   - StreamProbe：采集 GigE Vision 流状态（frames_received、frames_lost、resend_requests）
   - SystemProbe：采集系统指标（CPU 使用率、IRQ 分布）

### 测试生命周期

```
预检 (preflight) → 启动 fakecam → DUT 准备 → 
预热 (warmup) → 稳态 (steady_state) → 冷却 (cooldown) → 
清理 (teardown) → 报告生成 (reporting)
```

## 文档

- [测试指南 (英文)](docs/testing.md)
- [部署指南 (英文)](docs/deployment.md)
- [测试指南 (中文)](docs/testing-zh.md)
- [部署指南 (中文)](docs/deployment-zh.md)
- [CLI 命令参考](docs/cli-reference-zh.md)
- [快速入门](docs/quickstart-zh.md)

## 典型使用场景

### 场景 1: 四相机压力测试

```bash
# 1. 启动 4 个模拟相机
python -m gvstress fakecam up --config examples/fakecam_4p.yaml

# 2. 检查相机状态
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json

# 3. 运行四流测试
python -m gvstress test four-stream --config examples/scenario_4stream.yaml

# 4. 查看报告
python -m gvstress report show --latest --source artifacts/four-strean/runs

# 5. 停止相机
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### 场景 2: 远程 DUT 测试

```bash
# 1. 检查远程 DUT 就绪状态
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2,eno3,eno4 \
    --user admin

# 2. 运行冒烟测试
python -m gvstress test smoke \
    --config examples/scenario_smoke.yaml \
    --output artifacts/remote_test
```

### 场景 3: 基线性能测试

```bash
# 运行 pktgen 基线测试
python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml

# 查看基线报告
python -m gvstress report show --latest --source artifacts/pktgen/runs
```

## 报告解读

### 运行报告 (run.json) 关键字段

- `verdict`: 判定结果 (pass/warn/fail/not_applicable)
- `run_validity`: 运行有效性 (valid/invalid_environment/invalid_prereq/interrupted)
- `primary_attribution`: 主要归因 (nic/stream/mixed/environment/unknown)
- `samples`: 原始数据文件路径

### 判定归因说明

- **nic**: 故障在网络接口（驱动、硬件）
- **stream**: 故障在流处理（Aravis、重传逻辑）
- **mixed**: 多个域受影响
- **environment**: 设置/配置问题
- **unknown**: 无法确定

### 建议措施

根据归因采取相应措施：

**NIC 故障:**
- 更新 NIC 驱动/固件
- 检查网线质量
- 验证 MTU 设置
- 增加 socket 缓冲区大小

**流故障:**
- 调整包超时设置
- 优化重传请求比例
- 检查接收器优先级
- 验证 GenICam 配置

**环境故障:**
- 修复网络拓扑
- 更正 IP/接口映射
- 验证 SSH 连接
- 安装缺失的依赖项

## 最佳实践

1. **先运行预检**: 测试前始终验证环境设置
2. **从冒烟测试开始**: 长时间测试前先进行快速验证
3. **使用 JSON 输出**: 便于自动化解析结果
4. **归档产物**: 保留报告用于趋势分析
5. **老化测试期间监控**: 长时间运行时检查中间状态

## 故障排除

### Fakecam 启动失败
- 检查 Aravis 安装
- 验证配置文件中的接口名称
- 确保 IP 地址可路由

### 无流采样数据
- 确认 fakecam 正在运行
- 检查防火墙规则
- 验证 GenICam 文件存在

### 预检失败
- 检查输出中的 `reasons` 字段
- 在测试前修复环境问题
- 更改后重新运行预检

## 许可证

MIT License
