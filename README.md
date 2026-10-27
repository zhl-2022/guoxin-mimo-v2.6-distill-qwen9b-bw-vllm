# MiMo-V2.6-Distill-Qwen-9B on BW + native vLLM（BF16）

当前是完整 Agent 评测的代码与已结束任务备份，未宣称完成投递。历史开发材料保留，不能将 HTTP/工具接线测试换成正式准确率。

## 1. 简介

固定 `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` revision `2367e865d009c13ac81713a2878291d33ab28177`，SCNet BW64GB 单卡，原生 vLLM BF16。当前完整 Terminal-Bench2.1 共89项仍在原工作区运行。

## 2. 验证环境

DTK26.04，native vLLM0.18.1，204800总上下文，四序列上限，原生 qwen3 reasoning parser 与 qwen3_coder tool parser。本地 Harbor0.25.0 在 DockerDesktop隔离容器内执行任务，三任务并行。GPU模型端点只通过已授权 SSH 回环转发访问；仓库不保存密码或隧道认证材料。

## 3. 适配与协议

权重、tokenizer和模型chat template不改。Agent使用发布方 `XiaomiMiMo/mimoagent` 固定commit的BashOnlyAgent，137份源码逐Git blob校验，MIT原许可保留。适配器仅桥接Harbor执行环境和SCNet OpenAI兼容服务，保存模型输入、原始消息、工具命令、输出与退出状态。

普通命令超时返回124，允许Agent继续，真正通信故障单独报错。017采用非流式API，暴露出长生成触发六分钟读取超时；018改用发布方已有的流式消息组装，已在真实模型验证工具名和完整JSON参数重建，生成预算与采样参数不因此改变。

## 4. 服务与运行脚本

`scripts/submission013/launch_mimo_agent017.py` 保存实际服务004启动源码；服务受12小时自有进程看门狗保护，Notebook按用户要求保留。旧 `run_mimo_native_harbor017.py` 控制器已于2026-10-27 16:11:21 UTC 主动停止，为修复长生成读取超时切换到发布方已有流式消息组装。`run_mimo_repair018.py`于16:12:24 UTC 接续87项通信/环境异常或未完成任务；两个已正常评分的结果保持不变，分母仍为89。

本分支的配置和状态副本在`publisher017`，属于时间点原件。执行器当前的工作区路径、数据和进程状态尚未移植成此备份仓库的一键入口，因此不要直接复用状态副本启动重复任务。

## 5. 功能验证

真实原生bash工具接线已完成，流式API的工具JSON参数精确重建已验证。工具测试不并入准确率。旧通用JSON Terminus格式不匹配的失败诊断保留在原工作区，当前不再使用。

## 6. 完整准确率

固定官方Terminal-Bench2.1 commit `7131e4375048a0e408a8fb404b5f499d726b695b` 的全部89项。发布方SFT基线37.1%，按绝对2pt容差最低35.1%，至少需要32/89通过；不能混用RL分数。当前尚未完成全89项。旧 full017 的一个 reward=1 和一个正常3600秒任务超时 reward=0 已保留；后者不作为通信故障重跑。一个真正的 API 读取超时和三个主动取消的未完成任务保留原件并接续运行，不据此推算全量成绩。

`publisher017/session017-initial-harbor-finished-trials.zip` 保存已停止旧轮的全部81个原始文件，SHA256 `2dbb841ad65df4d2b3bd501fb6c21dac7945d802f1c3e7d5eaff37d5a188bea0`。`mimo-streaming-transition-audit.json` 更正原事件中“两项 API 超时”的不精确描述：实际为一个 API 超时、一个正式任务超时零分。流式修复不修改模型预算或采样参数。

最终可使用 `scripts/submission013/audit_mimo_selection019.py`独立核对018完整选择清单。它明确区分有真实零分的正常任务超时与未解决基础设施错误，拒绝正常零分重试和排除分母；没有全部89项选择清单时拒绝生成准确率结论。

完整框架的所有细化发布配置并未全部公开，本报告保留当前BashOnlyAgent/Harbor协议差异。所有环境及通信失败保留原件，不删除失败样本抬高分数。Harbor内建retry会删除上一目录，因此关闭；后续基础设施重试另建目录。

## 7. 性能参考

当前没有将新的Agent完整评测判为通过，尚未封装新的完整性能与镜像交付。旧开发性能材料不替代此处尚未完成的验证。

## 8. 当前交付状态

`standard_submission_ready=false`、`submitted=false`。当前分支用于安全保存源码、固定上游身份、真实已结束任务和运行快照；后续仅以全部89项完整结果、真实性能、八章报告、固定光合版本及超算镜像材料决定投递。新编代码继续保留原版权说明，未自行选择新许可证。
