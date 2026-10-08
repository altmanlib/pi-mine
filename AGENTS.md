# AGENTS.md — pi-mine

本文件定义本目录的开发约束。所有代码、测试、配置和文档修改均须遵守。

每次新会话开工前先读 `ROADMAP.md`：路线图按类目管理任务，每个任务有唯一编号 `R###`，文件顶部定义了类目、编号，以及执行前、中、后各阶段任务应移入哪个类目。agent 必须遵守，并在对应阶段更新 `ROADMAP.md`。

## 1. 项目定位

本机 CLI：从 Pi coding-agent sessions 挖掘用户高频话术与约束，产出资产候选清单与用户画像。

- 输入默认：`~/.pi/agent/sessions/**/*.jsonl`
- 输出默认：仓库内 `out/`（不入库）
- 只出候选，不自动改写 `AGENTS.md`，不自动生成 skill

## 2. 必读文档

| 文档 | 职责 |
|---|---|
| [ROADMAP.md](ROADMAP.md) | 任务进度、下一步、待决策；唯一待办真源 |
| [README.md](README.md) | 用法与产出说明 |
| [docs/README.md](docs/README.md) | 文档索引与格式约定 |
| [docs/design/2026-10-08-01-pipeline.md](docs/design/2026-10-08-01-pipeline.md) | 管线设计：提取 / 合并 / 候选 / 画像 |
| [docs/design/2026-10-08-02-optional-embedding.md](docs/design/2026-10-08-02-optional-embedding.md) | 可选 embedding（SiliconFlow）与 LLM（CPA）外部调用约定与外发边界 |

实现行为变化时同步更新对应文档。设计未决项不得静默固化；需要拍板的记入 ROADMAP「待决策」，不要自行假设。

## 3. 技术基线

| 项 | 选择 |
|---|---|
| Python | `>=3.14`（`.python-version` 固定） |
| 包管理 | 仅 `uv`（`uv add` / `uv remove`）；禁止 pip 或手编依赖版本后不 `uv lock` |
| CLI | Click |
| 运行时依赖 | 现阶段仅 `click`；`scikit-learn` 等到 `mine` 聚类再加 |
| 分析默认 | 离线统计；可选 embedding / LLM 后置允许走外部 API，但不得上传原始 sessions |
| 类型检查 | pyright `standard` |
| 缓存目录 | `.cache/`（pytest / ruff），不入库 |
| 默认产出 | 仓库内 `out/`；本工具默认在仓库目录运行 |

注意：Python 3.14 起不必再写 `from __future__ import annotations`。路径选项必须经 `expanduser().resolve()`，禁止把未展开的 `~` 传给文件系统 API。

## 4. 目录与依赖方向

```text
app/
  cli.py           # Click 根入口，只注册子命令
  options.py       # 共享选项与路径展开
  output.py        # human / JSON 输出
  models.py        # 数据结构
  commands/        # 参数解析与调度，不含业务算法
  services/        # 提取、清洗、聚类、排序、渲染
tests/
docs/
out/               # 生成物，gitignore
```

依赖方向：`commands → services → models`；`commands` 可依赖 `options` / `output`

- `commands` 只做参数收集、调用 service、格式化输出
- `services` 不依赖 Click
- 不引入可变全局业务状态
- sessions 只读；不得修改 `~/.pi/agent/sessions`

## 5. Python 约束

- 完整类型标注；注释与 docstring 用英文
- 项目命令通过 `uv run ...` 或 `make ...` 执行
- 输出默认人类可读；叶命令需要机器消费时提供 `--json`
- 不捕获裸 `Exception` 后静默忽略
- Import 必须在文件顶部；禁止函数 / 方法内 import。ruff `PLC0415` 强制；极少数必要延迟导入须同行标注 `# noqa: PLC0415` 并写明原因

## 6. 明确不做

- 自动写回个人 `AGENTS.md` 或生成 skill 目录
- 上传原始 session 文件到外部服务；可选 embedding / LLM 仅允许发送 normalize 后的 phrase 代表句，不得发送原始 JSONL 或完整 utterance 导出
- 第一版强制 embedding 或强制 LLM 总结
- 会话清理 / 删除（与 `sessions-clean` 无关）

## 7. Git 工作流

- 开发分支：`agent/develop`，agent 的所有改动都在该分支进行，不直接改动其他分支
- 在 `agent/develop` 上，完成一个功能或任务后，agent 可自行决定提交，无需逐次征求同意
- 提交信息：单行 `type: summary`（`feat` / `fix` / `docs` / `chore` / `style` / `refactor` / `test`）；对应 roadmap 任务时在末尾附编号，如 `feat: extract user utterances (R003)`
- ROADMAP 状态变更与对应工作放在同一个提交里
- 合并到其他分支、`git push` 必须由用户明确要求后才能执行

## 8. 开发命令

```bash
uv sync
make fmt
make check          # lint + typecheck + test
uv run pi-mine extract
uv run pi-mine mine
uv run pi-mine status
```
