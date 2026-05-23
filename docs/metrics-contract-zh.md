# GVStress Prometheus 指标合同

本文档定义了 GVStress 暴露的 Prometheus 指标，用于监控和告警。所有指标遵循 Prometheus 文本展示格式。

## 指标注册表

### `gvstress_node_up`

- **类型：** gauge（计量器）
- **描述：** GVStress 节点的健康指示器。当节点正常运行并报告指标时值为 `1`，否则为 `0`。
- **标签：** 无
- **重置行为：** 关闭时设置为 `0`；正常运行期间不重置。

### `gvstress_test_running`

- **类型：** gauge（计量器）
- **描述：** 指示测试场景当前是否处于活动状态。测试运行时为 `1`，空闲时为 `0`。
- **标签：**
  - `scenario` — 场景名称（例如 `smoke`、`soak`）
- **重置行为：** 测试完成或中断时设置为 `0`。

### `gvstress_test_elapsed_seconds`

- **类型：** gauge（计量器）
- **描述：** 当前测试开始以来的经过时间（秒）。
- **标签：**
  - `scenario` — 场景名称
  - `run_id` — 唯一运行标识符
- **重置行为：** 每次新测试运行开始时重置为 `0`。

### `gvstress_test_packets_sent`

- **类型：** gauge（计量器）
- **描述：** 当前运行期间 pktgen 发送的数据包总数。
- **标签：**
  - `run_id` — 唯一运行标识符
  - `interface` — 网络接口名称（例如 `eno1`）
- **重置行为：** 每次新测试运行开始时重置为 `0`。

### `gvstress_test_pktgen_errors`

- **类型：** gauge（计量器）
- **描述：** 当前运行期间检测到的 pktgen 错误数。
- **标签：**
  - `run_id` — 唯一运行标识符
  - `interface` — 网络接口名称
- **重置行为：** 每次新测试运行开始时重置为 `0`。

### `gvstress_test_expected_packets`

- **类型：** gauge（计量器）
- **描述：** DUT 预期接收的数据包数量，从 pktgen 基线配置派生。
- **标签：**
  - `run_id` — 唯一运行标识符
  - `interface` — 网络接口名称
- **重置行为：** 每次新测试运行开始时重置为 `0`。

### `gvstress_job_state_info`

- **类型：** gauge（计量器）
- **描述：** 当前作业状态作为信息风格指标。任何时候只有一个标签组合的值会为 `1`。
- **标签：**
  - `state` — 以下之一：`idle`（空闲）、`preflight`（预检）、`running`（运行中）、`completed`（已完成）、`failed`（失败）、`interrupted`（中断）
- **重置行为：** 转换到新状态时，前一个状态标签设置为 `0`。

### `gvstress_test_verdict_info`

- **类型：** gauge（计量器）
- **描述：** 测试裁决作为信息风格指标。测试完成后设置。
- **标签：**
  - `verdict` — 以下之一：`pass`（通过）、`warn`（警告）、`fail`（失败）、`not_applicable`（不适用）
  - `run_id` — 唯一运行标识符
- **重置行为：** 每次新测试运行开始时重置（所有标签设置为 `0`）；完成时设置一次。

### `gvstress_test_role`

- **类型：** gauge（计量器）
- **描述：** 当前 GVStress 实例在测试拓扑中的角色。
- **标签：**
  - `role` — 以下之一：`controller`（控制器）、`dut`（被测设备）、`generator`（生成器）
- **重置行为：** 进程生命周期内不重置；启动时设置。

## 示例输出

请参阅 `tests/fixtures/metrics/gvstress_sample.prom` 获取完整的 Prometheus 文本格式示例。

## 标签约定

- `run_id`：测试运行的唯一标识符，与 `RunArtifact` 中的 `run_id` 字段匹配（参见 `src/gvstress/report/models.py`）。
- `scenario`：场景名称，与 `ScenarioType` 值匹配。
- `interface`：pktgen 报告的网络接口名称。
- `verdict`：与 `Verdict` 枚举匹配：`pass`（通过）、`warn`（警告）、`fail`（失败）、`not_applicable`（不适用）。
- `state`：反映测试作业的当前生命周期阶段。

## 重置语义

所有 gauge 指标必须在新测试运行开始时重置为 `0`，除非另有说明。信息风格指标（`*_info`）使用约定：任何时候只有一个标签组合的值携带 `1`。
