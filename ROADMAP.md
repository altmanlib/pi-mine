# Roadmap

任务按类目管理：待决策、进行中、下一步、规划中、已完成。流转：规划中 → 下一步 → 进行中 → 已完成

- 编号 `R###` 全局唯一递增，待决策项也占用；一经分配不重用、不重排，移动类目时不变；新任务取文件中现有最大编号加 1
- 容量：进行中最多 1 项，下一步 1~3 项，已完成倒序保留最近约 10 项（更早的历史靠 `git log`）
- 条目格式：`R006 标题 — 说明（依赖 R00x）`；提交信息末尾附编号，如 `feat: extract user utterances (R003)`
- 断点写在「进行中」任务下，分三行：已做、未做、注意

| 阶段 | 规则 |
|---|---|
| 执行前 | 先看「待决策」，有项阻塞要做的任务时先向用户确认，不要自行假设；选任务：「进行中」有就按断点继续，否则取「下一步」第一项；把任务移入「进行中」并写初始断点，随首个工作提交一起提交 |
| 执行中 | 完成子步骤就更新断点；发现新任务取新编号放入「规划中」，不插队；需要用户拍板的放入「待决策」并注明阻塞的任务编号，当前任务无法继续时移回「下一步」或「规划中」；暂停但未完成时提交一次本文件，保证断点不丢 |
| 执行后 | 验证通过后在同一 commit 里移入「已完成」；从「规划中」把依赖已满足的任务提升到「下一步」；用户拍板的决策先把结论写入设计或 AGENTS，再从「待决策」删除，被阻塞的任务随之解除；修剪过长的「已完成」 |

## 待决策

无

## 进行中

无

## 下一步

- R013 确定性结论表 — 重复长指令与带参数句式 → prompt template 候选；同 session 内触发词先后顺序 → 工作流链条；可作为 R012 输入（依赖 R006）
- R007 候选裁定工作流 — 明确人工如何把结论标成 AGENTS / skill / prompt / discard；对照现有 AGENTS 标 `already_codified`（首轮结论中「函数内 import」「`from __future__`」等已在 AGENTS）（依赖 R012）

## 规划中

- R014 结论跨组去重 — 分组请求会产生重复结论（如 #10 与 #163 都归纳出「不要每次都 cd」）；考虑在总结请求前加一步合并（依赖 R012；触发：R007 裁定时重复干扰判断）

- R011 聚类区分否定句 — TF-IDF 与 embedding 都把「你不要启动 dev server」与「启动 dev server 我看看」、「不要 icon」与「缺少 icon」归为同簇，约束簇 count 偏高；考虑 `is_correction` 不同的 phrase 不入同簇（依赖 R005；触发：R007 裁定时约束簇失真影响判断）

## 已完成

- R012 LLM 综合出结论 — `pi-mine synthesize`：经 CPA（默认 `grok-4.5`）分 3 组归纳 + 1 次画像总结；evidence 本地校验、簇合计次数与项目数本地计算；`out/llm-cache/` 缓存；候选新增稳定 `number` 与 `project_keys`；全量：525 候选 → 46 条结论（AGENTS 37 / skill 4 / prompt 1 / notes 4）+ 6 条总结；51 tests
- R008 embedding 语义聚类 — `services/embedding.py`（SiliconFlow 客户端、`out/embeddings.npz` 缓存与断点续传、4 路并发重试）；`leader_cluster` 兼容稀疏 / 稠密向量；`mine --embedding` 可选后端（阈值 0.8）；全量试验：候选 150 → 525、覆盖发言 1654 → 3962、约束 strong 5 → 29；45 tests
- R010 candidates.md 可读性 — 按去向分节（约束 / 偏好 / 工具 / 工作流 + 附录）、全局序号；label 与变体用 `‹路径›` / `‹数字›` 掩码并按句式聚合计数；template 显示 skill 名或模板首行；`Candidate.sample_texts` 改为 `variants` / `variant_count`；1236 行 → 188 行；39 tests
- R006 全量试跑与阈值校准 — 抽查 Top 候选后：低信息短句（同意/hi/选项回答）移入 extract 过滤；纠偏、工作流、工具词表扩充；`strong` 改为以项目覆盖为主（长期高频为辅）；裸路径簇不入候选；基线 8523 utterances → 149 candidates（strong 114）；35 tests
- R005 cluster + rank + render — `cluster`（TF-IDF leader 聚类）/ `rank`（kind 规则 + strong/medium）/ `render` / `mine` 编排；`mine` 命令可用并写出 candidates.md/json 与 persona.md；`fsutil.atomic_text_writer`；34 tests；真实数据 8675 utterances → 7148 phrases → 6711 clusters → 160 candidates（strong 132）
- R004 normalize 近重复与清洗 — `services/normalize.py`：`normalize_key` / `match_key`、确认与纠偏词表、fork 去重、bigram Jaccard 近重复合并为 `Phrase`；确认过滤迁入 normalize；28 tests；真实数据 8694 条 → 7148 phrases（0.2s）
- R003 实现 extract — `services.extract` 流式读 JSONL；文本块拼接；slash/确认句过滤；写出 `out/utterances.jsonl`；17 tests；真实目录冒烟 1295 files → 8685 utterances / 90 projects
- R002 骨架收敛 — 路径 `expanduser().resolve()`；运行时依赖仅 click；`options` / `output`；pyright 入 `make check`；`status` 可运行；8 tests 通过
- R001 正式包骨架 — `app/` + Makefile + AGENTS + 设计文档；Click 子命令占位；对齐 fishx 正式 Python 工程形态
