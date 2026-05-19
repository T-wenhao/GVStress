# GVStress 自动化测试技能

> **技能位置**: `docs/skills/gvstress-automated-testing/`  
> **适用项目**: GVStress - GigE Vision 压力测试框架  
> **技能类型**: 自动化测试与诊断

---

## 📋 技能概述

本技能为 GVStress 项目提供自动化压力测试能力，使 AI 助手能够：

1. **环境验证** - 运行预检检查，确保测试环境就绪
2. **测试执行** - 运行压力测试场景（smoke/four-stream/soak/loss-injection）
3. **配置管理** - 创建和管理测试配置文件 (YAML)
4. **报告生成** - 生成结构化测试报告和故障分析
5. **问题诊断** - 分析测试失败原因并提供修复建议

---

## 📁 文件结构

```
docs/skills/gvstress-automated-testing/
├── SKILL.md                       # 技能主文件（AI 使用）
├── README.md                      # 本文档（人类使用）
├── examples/
│   └── config-examples.yaml       # 配置文件示例（4 种场景）
└── references/
    └── quick-reference.md         # 快速参考指南
```

---

## 🚀 典型应用场景

### 场景 1: 新设备首次验证
**用户请求**: "我刚拿到一块新的采集卡设备，IP 是 192.168.10.100，连接在 eno1 网口上。请帮我运行一个快速验证测试。"

**技能执行**:
- ✅ 创建冒烟测试配置文件
- ✅ 运行预检检查验证环境
- ✅ 执行 smoke 测试（60 秒）
- ✅ 生成测试报告并展示判定结果
- ✅ 如预检失败，提供详细修复建议

### 场景 2: 多相机压力测试
**用户请求**: "我需要对 DUT 进行四相机压力测试。DUT 有 4 个网口 (eno1-eno4)，请配置 4 个虚拟相机并运行完整的压力测试流程。"

**技能执行**:
- ✅ 创建 4 相机配置文件（IP: 192.168.10.11-14 对应 eno1-4）
- ✅ 启动 fakecam 工作进程
- ✅ 运行 four-stream 测试（300 秒）
- ✅ 收集 NIC/流/系统采样数据
- ✅ 生成包含判定归因和建议措施的完整报告

### 场景 3: 测试失败诊断
**用户请求**: "上次测试失败了，报告显示'verdict: fail, primary_attribution: nic'。请分析原因并给出修复建议。"

**技能执行**:
- ✅ 读取 run.json 和 preflight.json 分析失败原因
- ✅ 检查 NIC 采样数据中的 rx_errors 和 rx_dropped
- ✅ 查看证据文件
- ✅ 根据 NIC 归因提供具体修复建议

### 场景 4: 远程 DUT 测试
**用户请求**: "我的 DUT 是远程设备，hostname 是 dut-lab-01，通过 SSH 访问。需要测试 2 个网口 eno1 和 eno2。"

**技能执行**:
- ✅ 创建包含 SSH 配置的远程 DUT 测试配置
- ✅ 运行 dut inspect 验证 SSH 连接性
- ✅ 执行预检检查确认远程接口状态
- ✅ 运行测试场景并收集远程采样数据

---

## ✅ 使用前提条件

### 硬件要求
- **物理网卡**: 至少一个可用的网络接口（eno1 等）
- **DUT 设备**: 被测设备（采集卡/视觉系统）
- **网络连接**: DUT 与相机之间的网络连通性

### 软件依赖
- **Python 3.10+**
- **GVStress 项目**: `pip install -e .`
- **Aravis 库**: 用于 fakecam 模拟 (`apt-get install aravis-tools`)
- **ethtool**: 用于 NIC 检查 (`apt-get install ethtool`)
- **SSH 访问**: 远程 DUT 测试需要

### 验证安装
```bash
# 检查 GVStress 安装
pip show gvstress

# 检查 Aravis
pkgconf --modversion aravis-0.8

# 检查 ethtool
ethtool --version

# 检查网络接口
ip addr
```

---

## 📊 测试流程详解

### 测试执行流程

```
环境评估 → 预检检查 → 配置创建 → 测试执行 → 结果分析 → 报告呈现
```

#### 阶段 1: 环境评估
- 检查 GVStress 项目安装
- 收集网络接口信息
- 确认 DUT 配置（本地/远程）

#### 阶段 2: 预检检查
- 网络接口存在性验证
- IP 地址与接口映射
- SSH 连接性（远程 DUT）
- 必需工具检查（ethtool, aravis）

#### 阶段 3: 配置创建
- 根据用户硬件创建 YAML 配置
- 验证 IP/接口映射
- 设置采样间隔和持续时间

#### 阶段 4: 测试执行
- 自动运行预检
- 启动 fakecam（如配置）
- 执行测试场景（warmup → steady_state → cooldown）
- 收集 NIC/stream/system 采样数据

#### 阶段 5: 结果分析
- 读取 run.json 和 summary.md
- 分析 verdict 和 attribution
- 检查采样数据
- 生成故障诊断（如失败）

#### 阶段 6: 报告呈现
- 判定结果（PASS/WARN/FAIL）
- 故障归因（NIC/STREAM/MIXED/ENVIRONMENT）
- 具体修复建议
- 报告文件路径

---

## 📋 输出产物说明

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

### 关键文件说明

**run.json** - 完整运行报告
```json
{
  "run_id": "abc123",
  "scenario": "smoke",
  "verdict": "pass",
  "run_validity": "valid",
  "primary_attribution": "nic",
  "sample_counts": {"nic": 60, "stream": 60, "system": 60}
}
```

**preflight.json** - 预检结果
```json
{
  "run_validity": "valid",
  "reasons": [],
  "checks": [
    {"name": "ssh_connectivity", "passed": true},
    {"name": "interface_exists", "passed": true}
  ]
}
```

**summary.md** - 人类可读摘要
```markdown
# 测试报告

## 运行摘要
- 运行 ID: abc123
- 测试场景：smoke
- 判定结果：pass
...
```

---

## 🔍 故障诊断指南

### 常见失败场景

#### 1. 预检失败 - 找不到 ethtool
**症状**: `preflight.json` 中 `run_validity: invalid_prereq`  
**原因**: ethtool 未安装  
**解决**: `apt-get install ethtool` 并重新运行

#### 2. Fakecam 启动失败
**症状**: fakecam 状态异常  
**原因**: Aravis 未安装或配置错误  
**解决**:
```bash
# 检查 Aravis
pkgconf --modversion aravis-0.8

# 重新安装
apt-get install aravis-tools
```

#### 3. NIC 错误（verdict=fail, attribution=nic）
**症状**: `rx_errors` 或 `rx_dropped` > 0  
**原因**: 驱动问题、网线质量、buffer 不足  
**解决**:
```bash
# 更新驱动
ethtool -i eno1

# 检查网线
ethtool eno1 | grep -i link

# 增加 bufeprml
sysctl -w net.core.rmem_max=134217728
```

#### 4. 流错误（verdict=fail, attribution=stream）
**症状**: `frames_lost` 高，`resend_requests` 频繁  
**原因**: 包超时设置、重传比例  
**解决**: 调整 stream 配置中的 `packet_timeout`和`packet_request_ratio`

---

## 🎯 最佳实践

### 配置建议
- **IP 规划**: 相机 IP 与接口在同一子网（如 192.168.10.x/24）
- **采样间隔**: 默认 1000ms，高速场景设为 100-500ms
- **长时间测试**: 增加采样间隔到 2000-5000ms 减少开销

### 场景选择
| 场景 | 持续时间 | 用途 | 推荐时机 |
|------|----------|------|----------|
| smoke | 60s | 快速验证 | 新环境首次测试 |
| four_stream | 300s | 多接口压力 | 多相机部署验证 |
| soak | 1800s | 长期稳定性 | 生产环境验证 |
| loss_injection | 300s | 丢包恢复 | 网络质量诊断 |

### 安全注意事项
- ⚠️ 长时间测试（soak）前确保已保存配置
- ⚠️ 测试结束后清理 fakecam 进程
- ⚠️ 远程 DUT 测试确保 SSH 连接安全
- ⚠️ 避免在关键业务时间段运行压力测试

---

## 📖 相关文档

### 项目文档
- [测试指南](../testing.md) - 详细的测试流程说明
- [CLI 命令参考](cli-reference.md) - 完整的命令列表
- [部署指南](deployment.md) - 环境配置说明

### 技能配套文件
- [SKILL.md](SKILL.md) - AI 使用的技能定义
- [配置文件示例](examples/config-examples.yaml) - 4 种场景配置模板
- [快速参考](references/quick-reference.md) - 命令速查表

---

## 🔧 技能开发与维护

### 技能更新流程

1. **修改技能定义**: 编辑 `SKILL.md` 文件
2. **更新示例**: 修改 `examples/config-examples.yaml`
3. **同步文档**: 更新 `README.md` 和 `references/quick-reference.md`
4. **测试验证**: 在真实硬件环境中测试技能

### 技能触发机制

技能在以下场景自动触发：
- 用户提到 "DUT 测试"、"压力测试"、"运行场景"
- 需要配置 fakecam、预检、生成报告
- 诊断测试失败或环境问题
- 创建或修改测试配置文件

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2024-04-09 | 初始版本，包含完整测试流程和故障诊断能力 |

---

**最后更新**: 2024-04-09  
**维护者**: GVStress 开发团队  
**许可证**: MIT License
