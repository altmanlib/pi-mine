# pi-mine

从 Pi coding agent 的 sessions 里挖掘用户高频话术与约束，产出**资产候选清单**和**用户画像**，供后续写入 `AGENTS.md`、制作 skill / prompt template。

## 定位

- 输入：`~/.pi/agent/sessions/**/*.jsonl`（可配置）
- 主交付：语义合并后的句式候选表 + 用户画像摘要
- 不做：自动改写 AGENTS、自动生成 skill（需人工裁定后再做）

## 快速上手

```bash
cd ~/code/fishx/pi-mine
uv sync

uv run pi-mine extract
uv run pi-mine mine [--min-count 3] [--min-projects 3]
uv run pi-mine mine --embedding   # 可选语义聚类，需 SILICONFLOW_BASE_URL / SILICONFLOW_API_KEY
uv run pi-mine synthesize         # 可选 LLM 综合结论，经 CPA，需 CLIPROXYAPI_BASE_URL / CLIPROXYAPI_API_KEY
ls out/
```

## 产出目录

默认写入 `out/`（gitignore）：

| 文件 | 说明 |
|---|---|
| `utterances.jsonl` | 清洗后的用户发言 |
| `candidates.md` / `candidates.json` | 资产候选清单 |
| `persona.md` | 用户画像摘要 |
| `embeddings.npz` | `--embedding` 的向量缓存 |
| `conclusions.md` / `conclusions.json` | LLM 综合的结论与画像总结，附候选编号依据 |
| `llm-cache/` | `synthesize` 的回复缓存 |

## 文档

| 文档 | 说明 |
|---|---|
| [ROADMAP.md](ROADMAP.md) | 进度、下一步、待决策项 |
| [AGENTS.md](AGENTS.md) | 开发约束 |
| [docs/design/2026-10-08-01-pipeline.md](docs/design/2026-10-08-01-pipeline.md) | 管线设计 |

## 开发

```bash
make fmt
make check
```
