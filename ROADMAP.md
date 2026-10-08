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

- R009 可选 embedding 是否允许外发 phrase — SiliconFlow `Qwen/Qwen3-Embedding-8B` 已定为 R008 供应商/模型（见 `docs/design/2026-10-08-02-optional-embedding.md`）；启用会把 normalize 后的代表句发到外部 API，与现行「不上传衍生语料」冲突。需确认：禁止外发 / 仅本地模型 / 允许 SiliconFlow 且限定只发 phrase。阻塞 R008 实现

## 进行中

- R005 cluster + rank + render — 引入 scikit-learn 做 TF-IDF 句式聚类；按频次与项目覆盖分级；写出 `candidates.md` / `candidates.json` / `persona.md`（依赖 R004）
  - 已做：方案确定（services 拆 cluster / rank / render / mine；leader 聚类，按 count 降序、余弦阈值归并）
  - 未做：`uv add scikit-learn`；cluster；rank（kind 规则 + 分级）；render（candidates.md/json、persona.md）；mine 命令接线；测试；真实数据冒烟；更新设计文档与 README
  - 注意：聚类阈值、kind 关键词为 v1 默认值，R006 校准；不引入 embedding / LLM

## 下一步

无

## 规划中

- R006 全量试跑与阈值校准 — 对 `~/.pi/agent/sessions` 跑通 extract→mine；人工抽查 Top 候选，调整 `min-count` / `min-projects` 与假阳性规则（依赖 R005）
- R007 候选裁定工作流 — 明确人工如何把强候选标成 AGENTS / skill / prompt / discard；是否需要 `already_codified` 对照现有 AGENTS（依赖 R006；触发：首轮候选清单可用后）
- R008 可选 embedding / LLM 簇命名 — 仅当 TF-IDF 同义拆散严重或画像可读性不足时启动；默认不进主路径；供应商/模型已定为 SiliconFlow `Qwen/Qwen3-Embedding-8B`（`dimensions=1024`）（依赖 R006、R009；触发：人工抽查判定需要）

## 已完成

- R004 normalize 近重复与清洗 — `services/normalize.py`：`normalize_key` / `match_key`、确认与纠偏词表、fork 去重、bigram Jaccard 近重复合并为 `Phrase`；确认过滤迁入 normalize；28 tests；真实数据 8694 条 → 7148 phrases（0.2s）
- R003 实现 extract — `services.extract` 流式读 JSONL；文本块拼接；slash/确认句过滤；写出 `out/utterances.jsonl`；17 tests；真实目录冒烟 1295 files → 8685 utterances / 90 projects
- R002 骨架收敛 — 路径 `expanduser().resolve()`；运行时依赖仅 click；`options` / `output`；pyright 入 `make check`；`status` 可运行；8 tests 通过
- R001 正式包骨架 — `app/` + Makefile + AGENTS + 设计文档；Click 子命令占位；对齐 fishx 正式 Python 工程形态
