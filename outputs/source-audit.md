# 初始论文来源核查记录

核查日期：2026-09-10。范围：arXiv 原论文元数据与摘要；9 个官方仓库的固定 commit README。未阅读全文、未下载 PDF、未执行论文代码。

| 条目 | 原论文版本 | 作者数 | 官方 README / 数据入口 |
| --- | --- | ---: | --- |
| MMLU | [arXiv 2009.03300 v3](https://arxiv.org/abs/2009.03300v3) | 7 | [固定 commit README](https://github.com/hendrycks/test/blob/4450500f923c49f1fb1dd3d99108a0bd9717b660/README.md) |
| MATH | [arXiv 2103.03874 v2](https://arxiv.org/abs/2103.03874v2) | 8 | [固定 commit README](https://github.com/hendrycks/math/blob/985bdc1696e88e8643f081a0ff4719da39f2ae2a/README.md) |
| HumanEval | [arXiv 2107.03374 v2](https://arxiv.org/abs/2107.03374v2) | 58 | [固定 commit README](https://github.com/openai/human-eval/blob/6d43fb980f9fee3c892a914eda09951f772ad10d/README.md) |
| GSM8K | [arXiv 2110.14168 v2](https://arxiv.org/abs/2110.14168v2) | 12 | [固定 commit README](https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/README.md) |
| HELM | [arXiv 2211.09110 v2](https://arxiv.org/abs/2211.09110v2) | 50 | [固定 commit README](https://github.com/stanford-crfm/helm/blob/63754d05db6f874e41a395880fb573890a13e791/README.md) |
| Mind2Web | [arXiv 2306.06070 v3](https://arxiv.org/abs/2306.06070v3) | 8 | [固定 commit README](https://github.com/OSU-NLP-Group/Mind2Web/blob/33bd95caeee7bba22dd08ecc935845e15c5e5dc7/README.md) |
| WebArena | [arXiv 2307.13854 v4](https://arxiv.org/abs/2307.13854v4) | 12 | [固定 commit README](https://github.com/web-arena-x/webarena/blob/dce04686a56253aefba7b18a4fa0937cf1dc987b/README.md) |
| AgentBench | [arXiv 2308.03688 v3](https://arxiv.org/abs/2308.03688v3) | 22 | [固定 commit README](https://github.com/THUDM/AgentBench/blob/d1e4a10db08c87075c78972e48ecc182be03e2d5/README.md) |
| SWE-bench | [arXiv 2310.06770 v3](https://arxiv.org/abs/2310.06770v3) | 7 | [固定 commit README](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/README.md) |
| GAIA | [arXiv 2311.12983 v1](https://arxiv.org/abs/2311.12983v1) | 6 | [原论文给出的官方入口](https://huggingface.co/gaia-benchmark)，数据卡 HTTP 401 |

## 官方命令

共 5 条命令摘录；逐条在取得的 README 文本中检查过完全匹配。命令仅作为转义文本展示，没有执行。

## 留空与限制

- AgentBench 的各环境具体指标尚未核对，metrics 留空。
- GAIA 官方代码、数据下载权限、评分实现与运行命令待核查。
- MATH 的完整答案归一化细节待核查。
- 当前官方仓库 commit 可能晚于原论文，不表示重建了原始实验环境。
- 所有条目均无本站实测记录；source_verified 不等同于维护者人工审核。
