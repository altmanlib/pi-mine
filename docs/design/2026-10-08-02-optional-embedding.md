---
title: 可选 Embedding 供应商约定
type: design
status: draft
updated: 2026-10-08
---

# 可选 Embedding 供应商约定

## 1. 目标与范围

为路线图 [R008](../../ROADMAP.md)（可选 embedding / LLM 簇命名）预先固定供应商与模型，避免触发时再选型。

本设计**不改变**第一版主路径：主路径仍是 TF-IDF / 确定性聚类。仅在人工抽查判定同义拆散严重或画像可读性不足时，才允许启用可选 `--embedding` 路径。

## 2. 已定选择

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

## 3. 数据外发边界

已拍板：

- **禁止**：上传原始 session JSONL，或把完整 utterance 导出原样发给外部服务
- **允许**：可选 embedding / LLM 路径把 **normalize 后的 phrase 代表句** 发给 SiliconFlow
- 默认仍不进 `mine` 主路径；实现时须可关闭、可回退到纯本地 TF-IDF

## 4. 触发条件

- 仍以 R008 为准：仅当 TF-IDF 同义拆散严重或画像可读性不足
- 不把 embedding 设为强制依赖

## 5. 明确不做

- 第一版强制 embedding
- 把 API key 写入仓库或 `out/`
- 用 embedding 替换 TF-IDF 作为唯一聚类手段
- 上传原始 sessions
