---
title: 可选 Embedding 与 LLM 外部调用约定
type: design
status: draft
updated: 2026-10-08
---

# 可选 Embedding 与 LLM 外部调用约定

## 1. 目标与范围

固定可选路径的外部调用方式：

- [R008](../../ROADMAP.md) embedding 语义聚类：把意思相近、写法不同的发言归到一起，覆盖频次法看不到的长尾（全量中约 80% 的发言只出现一次）
- R012 LLM 综合：把簇归纳成结论式画像与资产建议

主路径仍是 TF-IDF / 确定性聚类；两条可选路径均须可关闭、可回退。

## 2. Embedding

| 项 | 选择 |
|---|---|
| 供应商 | SiliconFlow |
| API | OpenAI 兼容 `POST {base}/embeddings` |
| Base URL | `https://api.siliconflow.cn/v1`（环境变量 `SILICONFLOW_BASE_URL`） |
| API Key | 环境变量 `SILICONFLOW_API_KEY`（不入库、不写进仓库配置） |
| 模型 | `Qwen/Qwen3-Embedding-8B` |
| 默认输出维度 | `1024`（调用时显式传 `dimensions`；模型默认是 `4096`） |
| 编码 | `encoding_format=float` |

已在本机用该 key 验证：

- `GET /models` 含 `Qwen/Qwen3-Embedding-8B`
- `POST /embeddings` 对中英短句返回向量；`dimensions=1024` 时输出长度 1024

官方文档：

- Quickstart：<https://api-docs.siliconflow.cn/docs/userguide/quickstart>
- Embeddings：<https://api-docs.siliconflow.cn/docs/api/embeddings-post>

## 3. LLM

| 项 | 选择 |
|---|---|
| 通道 | 本机 CPA（CLIProxyAPI），OpenAI 兼容协议 |
| Base URL | 环境变量 `CLIPROXYAPI_BASE_URL` |
| API Key | 环境变量 `CLIPROXYAPI_API_KEY`（不入库、不写进仓库配置） |
| 模型 | 实现 R012 时选定 |

输出约束：每条结论必须附依据（候选编号或簇 id、次数、项目数），便于人工核对。

## 4. 数据外发边界

已拍板：

- **禁止**：上传原始 session JSONL，或把完整 utterance 导出原样发给外部服务
- **允许**：把 **normalize 后的 phrase 代表句** 及其统计（次数、项目数）发给 SiliconFlow（embedding）与 CPA（LLM）

## 5. 首步验证

R008 先做低成本试验：全量 phrase 代表句做 embedding，抽查长尾能否聚成有意义的簇，再决定接入方式。

## 6. 明确不做

- 把 embedding 或 LLM 设为 `mine` 主路径的强制依赖
- 把 API key 写入仓库或 `out/`
- 用 embedding 替换 TF-IDF 作为唯一聚类手段
- 上传原始 sessions
