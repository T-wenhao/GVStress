# 快速参考指南

## 常用命令速查

### 预检检查
```bash
# 远程 DUT 检查
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin

# 本地环境检查
python -m gvstress fakecam status --config config.yaml --json
```

### 测试执行
```bash
# 冒烟测试（60 秒）
python -m gvstress test smoke --config config.yaml

# 四流测试（300 秒）
python -m gvstress test four-stream --config config.yaml

# 老化测试（1800 秒）
python -m gvstress test soak --config config.yaml

# JSON 输出
python -m gvstress test smoke --config config.yaml --json
```

### Fakecam 管理
```bash
# 启动
python -m gvstress fakecam up --config config.yaml

# 状态
python -m gvstress fakecam status --config config.yaml --json

# 停止
python -m gvstress fakecam down --config config.yaml
```

### 报告查看
```bash
# 最新运行报告
python -m gvstress report show --latest --source artifacts/smoke/runs

# 特定运行
python -m gvstress report show --run-id abc123 --source artifacts/smoke/runs

# 导出 JSON
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output report.json
```

## 判定结果说明

| Verdict | 含义 | 条件 |
|---------|------|------|
| PASS | 测试通过 | 无 NIC 错误、无流错误、无欠载 |
| WARN | 警告 | 1-3 次欠载、IRQ 不平衡、CPU 过热 |
| FAIL | 失败 | NIC 错误、流错误超阈值、意外模式 |
| NOT_APPLICABLE | 不适用 | 运行有效性无效 |

## 故障归因

| Attribution | 故障域 | 建议措施 |
|------------|--------|----------|
| NIC | 网卡驱动/硬件 | 更新驱动、检查网线、增加 buffer |
| STREAM | 流处理 | 调整超时、优化重传比例 |
| MIXED | 多域 | 综合诊断 |
| ENVIRONMENT | 环境配置 | 修复网络拓扑、IP 映射 |

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 |
| 3 | 失败 |
| 4 | 不适用/无效 |

## 常见问题排查

### Fakecam 启动失败
1. 检查 Aravis: `pkgconf --modversion aravis-0.8`
2. 验证接口：`ip addr`
3. 检查路由：`ip route`
4. 查看日志：`artifacts/<scenario>/fakecam/logs/`

### 预检失败
1. 读取 `preflight.json` 的 `reasons` 字段
2. 检查接口：`ip link show`
3. 验证 IP: `ip addr show <interface>`
4. 安装缺失工具：`apt-get install ethtool`

### 无流采样
1. 确认 fakecam 运行：`python -m gvstress fakecam status --config <config>`
2. 检查防火墙：`ufw status`
3. 验证 GenICam: `ls <genicam-filename>`
4. 测试连通性：`ping <camera-ip>`

### NIC 错误
1. 查看 `rx_errors`和`rx_dropped`
2. 更新驱动：`ethtool -i <interface>`
3. 检查网线：`ethtool <interface>`
4. 增加 buffer: `sysctl -w net.core.rmem_max=134217728`

## 测试场景选择指南

| 场景 | 持续时间 | 用途 | 推荐时机 |
|------|----------|------|----------|
| smoke | 60s | 快速验证 | 新环境首次测试 |
| four_stream | 300s | 多接口压力 | 多相机部署验证 |
| soak | 1800s | 长期稳定性 | 生产环境验证 |
| loss_injection | 300s | 丢包恢复 | 网络质量诊断 |
