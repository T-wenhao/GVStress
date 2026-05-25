# 测试指南

本指南涵盖使用 GVStress 运行测试和解读结果的完整流程。

## 测试类型

GVStress 支持多种测试场景：

| 场景 | 持续时间 | 预热 | 冷却 | 用途 |
|------|----------|------|------|------|
| smoke (冒烟) | 60s | 10s | 5s | 快速验证 |
| four_stream (四流) | 300s | 10s | 5s | 多流压力测试 |
| soak (老化) | 1800s | 10s | 5s | 长期稳定性 |
| loss_injection (丢包注入) | 300s | 10s | 5s | 丢包恢复能力 |

## CLI 命令

### Fakecam 管理

**启动模拟相机：**
```bash
python -m gvstress fakecam up --config examples/fakecam_4p.yaml
```

**检查状态：**
```bash
python -m gvstress fakecam status --config examples/fakecam_4p.yaml --json
```

**停止模拟相机：**
```bash
python -m gvstress fakecam down --config examples/fakecam_4p.yaml
```

### 运行测试

**冒烟测试（快速验证）：**
```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml
```

**四流压力测试：**
```bash
python -m gvstress test four-stream --config examples/scenario_4stream.yaml
```

**老化测试（长时间运行）：**
```bash
python -m gvstress test soak --config examples/scenario_soak.yaml
```

**丢包注入测试：**
```bash
python -m gvstress test loss-injection --config examples/scenario_loss.yaml
```

### 基线基准测试

**运行 pktgen 基线：**
```bash
python -m gvstress baseline pktgen --config examples/pktgen_4p.yaml
```

### DUT 检查

**检查 DUT 就绪状态：**
```bash
python -m gvstress dut inspect \
    --host dut-hostname \
    --ifaces eno1,eno2 \
    --user admin
```

### 节点与 Web 监控

在服务级验证或硬件验收前，可以先检查本机节点健康状态和能力：

```bash
python -m gvstress node health --json
python -m gvstress node capabilities --json
python -m gvstress node status --json
```

启动轻量 Controller API：

```bash
python -m gvstress controller serve --host localhost --port 8079 --data-dir data
```

另开一个终端启动 Web 监控 UI：

```bash
python -m gvstress web serve \
    --host localhost \
    --port 8080 \
    --data-dir data \
    --artifacts-dir artifacts \
    --web-dir web
```

常用检查：

```bash
curl http://localhost:8079/health
curl http://localhost:8080/api/nodes
curl http://localhost:8080/api/reports
curl http://localhost:8080/metrics
```

### 报告查看

报告命令从产物根目录读取数据。场景运行结果存储在 `<output>/<scenario-name>/runs/<run-id>/`。

**查看最新运行报告：**
```bash
python -m gvstress report show --latest --source artifacts/smoke/runs
```

**查看指定运行：**
```bash
python -m gvstress report show --run-id abc123 --source artifacts/smoke/runs
```

**导出运行报告：**
```bash
python -m gvstress report export \
    --run-id abc123 \
    --source artifacts/smoke/runs \
    --output exported-run.json
```

## 退出码

| 代码 | 含义 |
|------|------|
| 0 | 成功/通过 |
| 1 | 使用/操作错误 |
| 2 | 警告 (WARN) |
| 3 | 失败 (FAIL) |
| 4 | 不适用/无效 (NOT_APPLICABLE) |

## JSON 输出

所有命令都支持 `--json` 标志：

```bash
python -m gvstress test smoke --config examples/scenario_smoke.yaml --json
```

输出示例：
```json
{
  "run_id": "abc123",
  "scenario": "smoke",
  "run_validity": "valid",
  "aborted": false,
  "sample_counts": {
    "nic": 60,
    "stream": 60,
    "system": 60,
    "events": 5
  },
  "artifacts_root": "artifacts/smoke/runs/abc123"
}
```

## 产物解读

### 运行报告 (run.json)

关键字段：
- `verdict`: 判定结果 (pass, warn, fail, not_applicable)
- `run_validity`: 运行有效性 (valid, invalid_environment, invalid_prereq, interrupted)
- `primary_attribution`: 主要归因 (nic, stream, mixed, environment, unknown)
- `samples`: 原始数据文件路径

### 摘要报告 (summary.md)

包含以下内容的可读 Markdown 文档：
- 运行元数据（ID、时间戳、场景）
- 预检检查结果
- 采样计数
- 判定和归因
- 建议措施

### 原始采样数据

`raw/` 目录中的 JSON Lines 文件：
- `nic_samples.jsonl`: 每个采样间隔的 NIC 统计
- `stream_samples.jsonl`: 流探针记录
- `system_samples.jsonl`: 系统指标（CPU、内存）
- `events_samples.jsonl`: 状态转换和事件

### 采样记录结构

**NIC 采样：**
```json
{
  "record_type": "nic_sample",
  "timestamp": 1234567890.123,
  "interface_name": "eno1",
  "rx_packets": 1000000,
  "rx_errors": 0,
  "rx_dropped": 0
}
```

**流采样：**
```json
{
  "record_type": "stream_sample",
  "timestamp": 1234567890.123,
  "serial_number": "GV-001",
  "ip_address": "192.168.10.11",
  "frames_received": 5000,
  "frames_lost": 0,
  "resend_requests": 10
}
```

## 结果分析

### 通过条件

- `run_validity=valid`
- `verdict=pass`
- 所有预检检查通过
- 测试期间无流错误

### 警告条件

- `verdict=warn`
- 检测到次要问题（如偶尔的包重传）
- 非关键的预检警告

### 失败条件

- `verdict=fail`
- `run_validity` 不是 valid
- 流错误超过阈值
- 丢包或丢帧

### 解读归因

- **nic**: 故障在网络接口（驱动、硬件）
- **stream**: 故障在流处理（Aravis、重传逻辑）
- **mixed**: 多个域受影响
- **environment**: 设置/配置问题
- **unknown**: 无法确定

## 建议措施

根据归因采取相应措施：

### NIC 故障
- 更新 NIC 驱动/固件
- 检查网线质量
- 验证 MTU 设置
- 增加 socket 缓冲区大小

### 流故障
- 调整包超时设置
- 优化重传请求比例
- 检查接收器优先级
- 验证 GenICam 配置

### 环境故障
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

**症状**: fakecam up 命令返回错误或相机无法启动

**解决步骤**:
1. 检查 Aravis 安装：`arv-viewer-0.8 --version`
2. 验证配置文件中的接口名称是否正确
3. 确保 IP 地址可路由：`ip route get <camera-ip-address>`
4. 检查防火墙规则：`sudo iptables -L`

### 无流采样数据

**症状**: 运行报告显示 stream_samples 为空

**解决步骤**:
1. 确认 fakecam 正在运行：`python -m gvstress fakecam status --config <config> --json`
2. 检查防火墙规则是否阻止 GigE Vision 端口（通常 3956）
3. 验证 GenICam 文件存在于配置的路径
4. 检查网络连通性：`ping <camera-ip-address>`

### 预检失败

**症状**: dut inspect 返回 run_validity=invalid_environment

**解决步骤**:
1. 检查输出中的 `reasons` 字段，了解具体失败原因
2. 在测试前修复环境问题
3. 更改后重新运行预检
4. 常见问题：
   - SSH 连接失败：验证 SSH 密钥配置
   - 接口不存在：检查接口名称是否正确
   - Python 未安装：在 DUT 上安装 Python 3.10+

### NIC 错误计数增加

**症状**: nic_samples 显示 rx_errors 或 rx_dropped 持续增长

**解决步骤**:
1. 检查 IRQ 平衡：`cat /proc/interrupts | grep <interface-name>`
2. 增加 ring buffer：`ethtool -G <iface> rx 4096`
3. 增加 socket 缓冲区大小
4. 检查 CPU 负载是否过高
5. 验证 NIC 驱动版本

### 流重传过多

**症状**: stream_samples 显示 resend_requests 数量高

**解决步骤**:
1. 调整包超时设置（增加 packet-timeout）
2. 优化重传请求比例（packet-request-ratio）
3. 检查网络延迟和抖动
4. 验证接收器优先级设置
5. 增加 frame retention 缓冲

## 完整测试流程示例

### 示例 1: 完整四相机测试流程

```bash
# 1. 启动前检查
python -m gvstress dut inspect \
    --host 192.168.10.11 \
    --ifaces eno1,eno2,eno3,eno4 \
    --user admin \
    --json | jq .

# 2. 启动 4 个模拟相机
python -m gvstress fakecam up \
    --config examples/fakecam_4p.yaml \
    --json

# 3. 验证相机状态
python -m gvstress fakecam status \
    --config examples/fakecam_4p.yaml \
    --json | jq '.cameras[].health'

# 4. 运行四流测试
python -m gvstress test four-stream \
    --config examples/scenario_4stream.yaml \
    --output artifacts/four_stream_test \
    --json

# 5. 获取运行 ID
RUN_ID=$(python -m gvstress test four-stream \
    --config examples/scenario_4stream.yaml \
    --json | jq -r .run_id)

# 6. 查看报告
python -m gvstress report show \
    --run-id $RUN_ID \
    --source artifacts/four_stream_test/runs

# 7. 导出详细数据
python -m gvstress report export \
    --run-id $RUN_ID \
    --source artifacts/four_stream_test/runs \
    --output run_data.json

# 8. 停止相机
python -m gvstress fakecam down \
    --config examples/fakecam_4p.yaml \
    --json
```

### 示例 2: 自动化测试脚本

```bash
#!/bin/bash
# run_tests.sh - 自动化测试脚本

set -e

CONFIG_DIR="examples"
OUTPUT_DIR="artifacts/automated"
DUT_HOST="192.168.10.11"
DUT_IFACES="eno1,eno2,eno3,eno4"

echo "=== GVStress 自动化测试 ==="

# 1. 预检
echo "[1/5] 运行预检..."
python -m gvstress dut inspect \
    --host $DUT_HOST \
    --ifaces $DUT_IFACES \
    --json > $OUTPUT_DIR/preflight.json

# 检查预检结果
if ! jq -e '.run_validity == "valid"' $OUTPUT_DIR/preflight.json > /dev/null; then
    echo "预检失败！"
    jq '.reasons' $OUTPUT_DIR/preflight.json
    exit 1
fi
echo "预检通过 ✓"

# 2. 启动 fakecam
echo "[2/5] 启动模拟相机..."
python -m gvstress fakecam up \
    --config $CONFIG_DIR/fakecam_4p.yaml \
    --json > $OUTPUT_DIR/fakecam_up.json

# 3. 运行测试
echo "[3/5] 运行冒烟测试..."
RUN_OUTPUT=$(python -m gvstress test smoke \
    --config $CONFIG_DIR/scenario_smoke.yaml \
    --output $OUTPUT_DIR \
    --json)

RUN_ID=$(echo $RUN_OUTPUT | jq -r .run_id)
echo "运行 ID: $RUN_ID"

# 4. 通过 report 命令获取判定
echo "[4/5] 检查测试结果..."
VERDICT=$(python -m gvstress report show --run-id $RUN_ID --source $OUTPUT_DIR/runs --json | jq -r .verdict)
echo "判定：$VERDICT"

if [ "$VERDICT" != "pass" ]; then
    echo "测试未通过！"
    python -m gvstress report show --run-id $RUN_ID --source $OUTPUT_DIR/runs
    exit 1
fi

# 5. 清理
echo "[5/5] 停止模拟相机..."
python -m gvstress fakecam down \
    --config $CONFIG_DIR/fakecam_4p.yaml \
    --json > /dev/null

echo "=== 测试完成 ✓ ==="
```

## 配置示例

### Fakecam 配置 (fakecam_4p.yaml)

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

### 场景配置 (scenario_smoke.yaml)

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

## 趋势分析

对于长期质量跟踪，建议：

1. **保留所有运行产物**：按日期组织 artifacts 目录
2. **提取关键指标**：使用 jq 或自定义脚本提取 verdict、sample_counts 等
3. **生成趋势图**：使用提取的数据生成时间序列图表
4. **设置阈值告警**：当错误率超过阈值时触发告警

示例指标提取：
```bash
# 提取所有运行的判定结果
for run in artifacts/*/runs/*/reports/run.json; do
    jq -r '[.run_id, .scenario, .verdict, .primary_attribution] | @tsv' $run
done > all_runs.tsv
```
