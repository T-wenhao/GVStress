# GVStress 文档索引

## 快速链接

### 入门文档

| 文档 | 说明 |
|------|------|
| [README (中文)](../README-zh.md) | 项目概述和快速开始 |
| [快速入门指南](quickstart-zh.md) | 5 分钟开始第一个测试 |
| [CLI 命令参考](cli-reference-zh.md) | 完整的命令行接口文档 |

 ### 详细指南

| 文档 | 说明 |
|------|------|
| [双设备部署指南](dual-device-deployment-zh.md) | 控制主机+DUT 双设备部署详解 |
| [测试指南 (中文)](testing-zh.md) | 运行测试和解读结果 |
| [部署指南 (中文)](deployment-zh.md) | 安装和配置说明 |
| [测试指南 (英文)](testing.md) | Testing Guide (English) |
| [部署指南 (英文)](deployment.md) | Deployment Guide (English) |

## 文档结构

```
docs/
├── INDEX.md                      # 文档索引（本文件）
├── quickstart-zh.md              # 快速入门（中文）
├── cli-reference-zh.md           # CLI 命令参考（中文）
├── dual-device-deployment-zh.md  # 双设备部署指南（中文）
├── testing-zh.md                 # 测试指南（中文）
├── deployment-zh.md              # 部署指南（中文）
├── testing.md                    # 测试指南（英文）
└── deployment.md                 # 部署指南（英文）
```

## 推荐阅读顺序

### 新用户

1. [README (中文)](../README-zh.md) - 了解项目是什么
2. [快速入门指南](quickstart-zh.md) - 运行第一个测试
3. [CLI 命令参考](cli-reference-zh.md) - 学习所有命令
4. [双设备部署指南](dual-device-deployment-zh.md) - 部署控制主机+DUT 双设备环境
5. [测试指南 (中文)](testing-zh.md) - 深入了解测试类型
6. [部署指南 (中文)](deployment-zh.md) - 配置生产环境

### 已有经验用户

- [CLI 命令参考](cli-reference-zh.md) - 命令速查
- [测试指南 (中文)](testing-zh.md) - 故障排除和最佳实践
- [部署指南 (中文)](deployment-zh.md) - 性能优化和网络配置

## 主要内容概览

### 快速入门指南

涵盖：
- 安装 GVStress
- 准备配置文件
- 运行第一个冒烟测试
- 理解测试结果
- 常见问题解答

### CLI 命令参考

涵盖：
- 所有 CLI 命令和选项
- 参数详细说明
- 使用示例
- JSON 输出格式
- 故障排除

### 双设备部署指南

涵盖：
- 控制主机 + 生成器+DUT 三角色架构
- 网络拓扑和连接方式
- DUT 代理部署和配置
- SSH 无密码登录设置
- 双设备配置文件详解
- 数据流向和采集机制
- 完整部署检查清单
- 常见问题和故障排除

### 测试指南

涵盖：
- 测试类型（smoke、four_stream、soak、loss_injection）
- CLI 命令详解
- 产物解读
- 结果分析
- 建议措施
- 故障排除
- 完整测试流程示例

### 部署指南

涵盖：
- 生成器和 DUT 安装
- SSH 配置
- 二进制依赖（Aravis、pktgen、ethtool）
- 网络拓扑配置
- 性能优化
- 完整部署检查清单

**注意**: 双设备部署请参阅 [双设备部署指南](dual-device-deployment-zh.md)

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

## 退出码参考

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

## 测试场景类型

| 场景 | 持续时间 | 预热 | 冷却 | 用途 |
|------|----------|------|------|------|
| smoke | 60s | 10s | 5s | 快速验证 |
| four_stream | 300s | 10s | 5s | 多流压力测试 |
| soak | 1800s | 10s | 5s | 长期稳定性 |
| loss_injection | 300s | 10s | 5s | 丢包恢复能力 |

## 外部资源

- [GVStress GitHub 仓库](../)
- [Aravis 项目](https://github.com/AravisProject/aravis)
- [GigE Vision 标准](https://www.emva.org/standards-technology/gige-vision/)

## 获取帮助

### 命令帮助

```bash
# 主帮助
python -m gvstress --help

# 子命令帮助
python -m gvstress fakecam --help
python -m gvstress test smoke --help
python -m gvstress dut inspect --help
```

### 在线支持

- GitHub Issues - 报告问题和功能请求
- GitHub Discussions - 提问和交流
- 文档问题 - 在相应文档仓库提交 issue

---

**最后更新**: 2024 年 1 月
