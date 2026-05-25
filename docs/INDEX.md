# GVStress 文档索引

## 快速链接

### 入门文档

| 文档 | 说明 |
|------|------|
| [README（中文）](../README-zh.md) | 项目概览、快速开始、服务入口 |
| [README（英文）](../README.md) | English overview and entry points |
| [快速入门指南](quickstart-zh.md) | 5 分钟开始第一个测试，并验证本机服务命令 |
| [CLI 命令参考](cli-reference-zh.md) | 完整命令行接口，包括 `node`、`controller`、`web` |

### 测试与运行

| 文档 | 说明 |
|------|------|
| [测试指南（中文）](testing-zh.md) | 运行测试、查看报告、解读结果 |
| [测试指南（英文）](testing.md) | Testing guide |
| [双设备部署指南](dual-device-deployment-zh.md) | 控制主机 + 生成器 + DUT 拓扑详解 |
| [从临时 soak 脚本迁移](migration-from-soak-test.md) | `soak_test.py` 移除后的新命令映射 |

### 部署与监控

| 文档 | 说明 |
|------|------|
| [部署指南（中文）](deployment-zh.md) | 安装、SSH、网络和服务启动说明 |
| [部署指南（英文）](deployment.md) | Deployment guide |
| [部署架构决策（中文）](deployment-architecture-zh.md) | native、hybrid、compose 部署边界 |
| [Deployment Architecture ADR](deployment-architecture.md) | Deployment mode decision record |
| [Web 监控操作指南（中文）](web-monitoring-operator-guide-zh.md) | Web 监控平台的部署、指标和运维流程 |
| [Web Monitoring Operator Guide](web-monitoring-operator-guide.md) | Operator guide |
| [Prometheus 指标合同（中文）](metrics-contract-zh.md) | GVStress 自定义指标定义 |
| [Prometheus Metrics Contract](metrics-contract.md) | Metrics contract |
| [Web 监控验收 TODO](web-monitoring-validation-todos.md) | 受硬件或环境限制的剩余验证项 |

## 文档结构

```text
docs/
├── INDEX.md                           # 文档索引（本文件）
├── quickstart-zh.md                   # 快速入门（中文）
├── cli-reference-zh.md                # CLI 命令参考（中文）
├── testing.md                         # 测试指南（英文）
├── testing-zh.md                      # 测试指南（中文）
├── deployment.md                      # 部署指南（英文）
├── deployment-zh.md                   # 部署指南（中文）
├── deployment-architecture.md         # 部署架构决策（英文）
├── deployment-architecture-zh.md      # 部署架构决策（中文）
├── web-monitoring-operator-guide.md   # Web 监控操作指南（英文）
├── web-monitoring-operator-guide-zh.md # Web 监控操作指南（中文）
├── metrics-contract.md                # Prometheus 指标合同（英文）
├── metrics-contract-zh.md             # Prometheus 指标合同（中文）
├── dual-device-deployment-zh.md       # 双设备部署指南（中文）
├── migration-from-soak-test.md        # 临时 soak 脚本迁移说明
└── web-monitoring-validation-todos.md # Web 监控验收剩余项
```

## 推荐阅读顺序

### 新用户

1. [README（中文）](../README-zh.md) - 了解 GVStress 当前能力
2. [快速入门指南](quickstart-zh.md) - 完成第一次本机验证和测试
3. [CLI 命令参考](cli-reference-zh.md) - 学习所有命令
4. [测试指南（中文）](testing-zh.md) - 深入理解场景和报告
5. [部署指南（中文）](deployment-zh.md) - 准备真实环境
6. [Web 监控操作指南（中文）](web-monitoring-operator-guide-zh.md) - 部署监控和报告浏览

### 架构和运维用户

- [部署架构决策（中文）](deployment-architecture-zh.md) - 先确认 native、hybrid、compose 的边界
- [Prometheus 指标合同（中文）](metrics-contract-zh.md) - 对接监控和告警
- [Web 监控验收 TODO](web-monitoring-validation-todos.md) - 在 Linux 物理机补齐硬件/Compose/质量门验证
- [从临时 soak 脚本迁移](migration-from-soak-test.md) - 替换历史临时脚本

## 主要内容概览

### 快速入门指南

涵盖：

- 安装 GVStress
- 验证 `node health` 和 `node capabilities`
- 准备配置文件
- 运行第一个冒烟测试
- 启动本机 Controller 和 Web UI
- 理解测试结果

### CLI 命令参考

涵盖：

- 传统测试命令：`fakecam`、`dut`、`test`、`report`、`baseline`、`dut-agent`
- 新服务命令：`node`、`controller`、`web`
- 参数详细说明
- JSON 输出格式
- 常见调用示例

### 部署与 Web 监控文档

涵盖：

- Full native、hybrid、full compose 的部署取舍
- native/systemd 节点服务
- Docker Compose 监控栈
- Prometheus/Grafana 和 node_exporter 集成
- Web UI 报告浏览和 `/metrics` 端点
- 硬件验收、真实 Prometheus/Grafana 联调、ruff/mypy 等剩余验证项

## 配置文件示例

所有示例配置文件位于项目根目录的 `examples/` 文件夹：

| 文件 | 说明 |
|------|------|
| `examples/fakecam_4p.yaml` | 4 相机配置 |
| `examples/scenario_smoke.yaml` | 冒烟测试场景 |
| `examples/scenario_4stream.yaml` | 四流测试场景 |
| `examples/scenario_soak.yaml` | 老化测试场景 |
| `examples/scenario_loss.yaml` | 丢包测试场景 |
| `examples/pktgen_4p.yaml` | pktgen 基线配置 |

## 获取帮助

```bash
python -m gvstress --help
python -m gvstress node --help
python -m gvstress controller serve --help
python -m gvstress web serve --help
```

---

**最后更新**: 2026 年 5 月
