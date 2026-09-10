# benchmark-atlas

中文优先的 LLM / Agent Benchmark 论文知识库。这个名字是项目暂名，**不宣称提出新的 Benchmark**。

第一阶段使用 Astro 静态构建、少量 TypeScript 和 Python 采集程序。没有数据库、登录、常驻后端、向量数据库或模型运行服务。开发、测试、构建与基础采集不需要模型 Key。

## 默认访问地址

默认站点入口为 **[GitHub Pages](https://hamsterstation.github.io/benchmark-atlas/)**。本地地址只用于开发和测试。

站点通过 GitHub Actions 构建并发布到 Pages；部署结果见仓库的 **Deploy reviewed site** 工作流。仓库公开，默认发布模式为 review，定时采集独立控制。

## 本地开始

要求 Node.js **22.22.0**（见 `.nvmrc`）、npm、Python **3.13**。

```bash
# 已安装 nvm 时可先运行 nvm install && nvm use
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm run dev
```

打开终端显示的地址下的 `/benchmark-atlas/`。生产构建与预览：

```bash
npm run build
npm run preview
```

本地开发预览地址为 `http://127.0.0.1:4321/benchmark-atlas/`，不作为默认分享入口。Astro 7 的 preview 可能后台运行，停止命令为 `npx astro preview stop`。

`package-lock.json` 和 `requirements.lock` 锁定依赖；GitHub Actions 也固定 commit。`esbuild` override 固定到已修复安全公告的 0.28.2，升级时重新运行完整测试。字体优先使用 Noto Serif SC / Noto Sans SC / DM Mono；字体 CDN 不可用时使用本机中文字体，功能不依赖字体网络请求。

## 目录与资料边界

| 路径 | 用途 | 自动采集可否写入 |
| --- | --- | --- |
| `data/curated/<id>.json` | 人工维护、来源核查后的论文资料 | 否 |
| `data/drafts/<id>.json` | 机器元数据和模型草稿 | 是 |
| `notes/<id>.md` | 长篇人工复现笔记 | 否 |
| `schemas/paper.schema.json` | 共用 JSON Schema（AJV / Python） | 否 |
| `config/taxonomy.json` | 分类 ID、中文标签和说明 | 否 |
| `config/collector.json` | 检索词、起点、分页、配额与重试 | 否 |
| `automation/state.json` | 窗口、游标、去重记录、队列、每日调用数 | 是 |
| `automation/deployment.json` | 最近成功部署的时间、commit、运行链接 | 仅部署成功后 |
| `work/` | 临时来源材料、隔离测试、工具 | 不提交 |
| `outputs/` | 验收报告和页面截图 | 无采集权限 |

每篇论文一个 JSON。基础 arXiv ID 是去重身份，例如 `2009.03300`；稳定 ID 为 `arxiv-2009.03300`，版本独立保存为整数 `3`，论文链接指向 `v3`。兼容旧式 `cs/9901001`，对应 `arxiv-cs-9901001`。

同一个 ID 可同时存在于 curated 和 drafts，表示机器发现新版本、等待人工对比；两个目录各自禁止重复 ID。**任何发布模式下，curated 优先，机器新版本不覆盖它。** `publication=pending` 不发布，`excluded` 留档但不发布，`listed` 才可能出现在网站。

JSON Schema 校验必填字段、枚举、真实日期、HTTPS URL 和未知字段；附加校验检查 ID/文件名/版本链接一致性、来源证据和复现记录。`isTest=true` 的数据禁止放入两个正式内容目录。测试 fixture 只在测试代码或 `work/` 下的隔离目录中使用，不进入生产构建。

## 初始 10 篇论文

已于 **2026-09-10** 联网核对 arXiv API 的原论文元数据与摘要；9 个官方仓库 README 读取并固定至完整 commit。GAIA 的官方资源组织入口来自原论文摘要，数据卡直接读取返回 HTTP 401，具体代码和下载步骤保持待核查。

| 简称 | arXiv | 核对版本 | 论文贡献 |
| --- | --- | --- | --- |
| MMLU | 2009.03300 | v3 | 提出 Benchmark |
| MATH | 2103.03874 | v2 | 提出 Benchmark |
| HumanEval | 2107.03374 | v2 | 提出 Benchmark，论文同时介绍代码模型 |
| GSM8K | 2110.14168 | v2 | 提出 Benchmark，论文同时研究验证器 |
| HELM | 2211.09110 | v2 | 提出评测框架 |
| Mind2Web | 2306.06070 | v3 | 提出 Benchmark |
| WebArena | 2307.13854 | v4 | 提出 Benchmark |
| AgentBench | 2308.03688 | v3 | 提出 Benchmark |
| SWE-bench | 2310.06770 | v3 | 提出 Benchmark |
| GAIA | 2311.12983 | v1 | 提出 Benchmark |

每条 `sources` 保存版本、核查日期与核查范围。`source_verified` 表示这些来源已核对，不表示维护者人工审核，更不表示亲测。当前所有条目均未实测：9 篇为“官方文档整理、未亲测”，GAIA 为“复现资料待核查”。摘要和官方 README 整理不能冒充全文解读。缺少的指标、代码、命令等显示“待核查”。

首发日期使用 arXiv v1 提交时间，**不是会议正式出版日期**。论文版本更新时间、本站核查日期、本站资料更新时间分别展示。当前官方工具可能晚于原论文环境，命令旁注明来源 commit 与适用范围，不把新版工具等同于论文原始实验。

## 手动添加与审核

```bash
.venv/bin/python scripts/manual.py add 2609.12345 --title '填写真实论文标题'
# 已有机器草稿时：
.venv/bin/python scripts/manual.py promote 2609.12345 --reviewer '你的署名'
```

示例 ID 只说明命令格式，不能作为真实论文直接发布。两个命令只创建 `pending` 人工条目，已有文件会拒绝覆盖。`promote` 不自动宣布审核完成。填写并核对来源、日期、版本、分类、简介、任务形式和指标后，手动完成审核：

1. 将实际核对材料的日期填入 `checkedAt` 和对应 `sources[].checkedAt`。
2. 设置 `review.status=human_reviewed`，填写 `reviewer`、`reviewedAt`。
3. 判断论文是提出 Benchmark、提出评测框架还是仅使用 Benchmark。纯使用论文默认不自动收录；维护者有理由收录时明确保留 `uses_benchmark` 标签。
4. 设置 `publication=listed`，更新 `updatedAt`，运行 `npm run validate && npm run build`，检查页面后提交评审。

不要凭未确认信息填字段。已审核旧版本遇到新版本时，人工对照 drafts 更新 curated；原来的笔记只说明其记录的 commit 与环境。

复现命令必须有已核对的官方来源 URL 与版本。实测状态必须填写 `reproduction.runs`：日期、操作者、完整 commit、环境、验证范围、结果、Markdown 文件名；指定实验复现还需填写 `experiment`。人工笔记模板见 `notes/README.md`。

## arXiv 采集与 dry-run

```bash
# 默认检索，可分页；仅预览，默认不调用模型
.venv/bin/python -m collector.collect --dry-run --report work/preview.json

# 手动指定真实论文 ID，仍经同一个去重与版本检测流程
.venv/bin/python -m collector.collect --dry-run --ids 2009.03300 2310.06770

# 明确落盘，只修改机器草稿和采集状态，不推送或部署
.venv/bin/python -m collector.collect --report work/collection-report.json
```

dry-run 不写资料、队列、采集成功时间，不调用模型，不创建 PR、不发布。只有显式 `--report` 会写预览报告。报告中的 `preview_collected_at` 是本次预览完成时间，`last_successful_collection_at` 是之前真实保存的成功记录。

检索词为 arXiv API 查询语法，配置在 `queries` 数组。默认首次从 2026-09-01 开始并向前重叠 7 天，这不是宣称补齐所有历史文献；完整历史回填需手动设定更早 `initial_since` 并连续运行到 `collection_complete=true`。已存在游标时只修改初始日期不会重置进度；备份 `atlas-state` 后由维护者清空对应 query 的进度可重新回填，seen 仍负责去重。

每个检索词独立保存固定 `since/until` 窗口和页偏移，查询 `lastUpdatedDate`，按更新时间升序分页，直到 `totalResults` 覆盖完毕；达到单次页数上限就保留窗口继续，下次不会把未完成的一页当成全部数据。这样能发现很早发表论文的新版本。重叠窗口补查索引延迟；超过窗口的延迟收录仍可能遗漏，可扩大窗口或周期性手工回填。

请求至少间隔 3.1 秒，有超时、响应大小限制、有限重试与退避。页返回空但总数尚未覆盖时判失败，不推进成功游标。不并发运行本地采集进程；CI 使用共用 concurrency 锁避免多个写者。基础 ID 去重，版本更新进入同一 ID 的新草稿。已有成功结果与版本相同，不重复调用模型。

先把取得的材料放入持久队列，再提交游标。单篇模型失败不会被游标推进吞掉，失败条目保留；模型异常退避 6 小时，每版本总尝试上限默认 3 次。达到上限后保留 `retry_exhausted`，修好服务后维护者可在 state 分支将该条目的 `attempts` 设为 0、`next_attempt_at` 设为 null 再重试。不要删除队列来“消除”错误。

无模型配置时仍完成分页采集，候选保留 `waiting_model` 与 null 简介；后续有模型时处理队列。队列先处理未处理条目，避免等 Key 的旧条目挡住新元数据。宽松关键词规则只做范围预筛，最终类型不足则 `uncertain`，纯使用 Benchmark 的模型草稿标为 excluded。人工审核与运行记录永远不由采集写入。

报告包含 new、updated、skipped、pending_review、failed、pages、model_calls 和 queue_remaining。前五项是本轮触及的处理计数，并非相加等于检索总数的互斥分类；`queue_remaining` 才是运行结束后待处理总量。首次发现的 v2 论文仍计为 new，因为本站此前没有这个基础 ID。

## 可选模型

基础运行无需任何 Secret。要启用中文草稿，可配置兼容 `messages` / `response_format=json_object` 的 HTTPS chat-completions 接口：

| 配置 | 类型 | 含义 |
| --- | --- | --- |
| `MODEL_API_KEY` | Secret / 本地环境变量 | 唯一模型密钥，不打印、不保存 |
| `MODEL_API_URL` | Repository Variable / 环境变量 | 完整 HTTPS 请求地址，不自动拼路径，不接受重定向 |
| `MODEL_NAME` | Repository Variable / 环境变量 | 服务支持的模型名称，项目不指定品牌 |

模型只收到当前标题和摘要，没有网页访问、工具调用、文件系统或执行权限。响应只能包含 7 个分类/简介字段，任何额外字段会被拒绝。JSON 文本不会成为 MDX、模板或构建代码。材料版本、范围、输入哈希、截断标记、模型名与生成时间写入 provenance；没有读取的全文不进入声明。

每日调用上限 20，输入上限 12,000 字符，每轮重试上限 1，每个版本总尝试上限 3，均可配置。失败调用也占配额。CI 会在模型请求前把配额预留推送到持久 state 分支；持久化失败就停止，不在未知配额状态下继续请求。模型返回格式或服务不兼容时保留待审核元数据；本阶段未接入真实付费模型，相关异常和成功路径使用明确的测试替身验证。

## GitHub Actions 与持久状态

首次本地验收时未建立远端仓库或启用公开发布；`outputs/` 中的验收报告记录该阶段的结果。后续仓库上传与在线 CI 状态以 GitHub 提交和 Actions 记录为准。Pages 与定时采集仍需要显式启用。

`collect.yml` 每天 **02:20 UTC / 北京时间 10:20** 计划运行，也支持 `workflow_dispatch`。默认 `COLLECTION_ENABLED` 未设置，定时任务跳过；手动运行默认 `dry_run=true`。只有默认分支可运行生产采集。GitHub 可能延迟计划任务，长期无活动也可能暂停计划，需要维护者检查 Actions。

`atlas-state` 分支是运行状态的持久来源，保存完整队列、游标、seen、每日配额、drafts 和部署成功记录，绝不使用临时 runner 目录或有过期时间的 artifact 作为唯一状态。每页游标、模型调用配额和完成记录有远端检查点；工作结束或失败后再次保存。首次写入可创建该分支；不可访问远端会失败，不会误认为状态不存在而从零覆盖。所有推送都是普通推送，遇到权限限制或分支保护直接停止。

| 模式 | 行为 |
| --- | --- |
| `review`（默认） | 生成或更新固定 `atlas-review` 分支上的一个待审核 PR。只改机器草稿与状态快照；不自动合并。人工提升、核查并合并 curated 后，默认分支部署。只合并 drafts 不会让它进入正式索引。 |
| `auto`（显式配置） | 通过 schema 和内容边界校验的新增模型草稿进入索引，状态固定为“自动收录、未审核”。元数据空简介、uncertain 与 uses_benchmark 不发布。该次采集工作流直接构建、上传 Pages artifact 并部署，不依赖机器人 push 触发另一个工作流。 |

不自动写默认分支。review PR 更新会合并默认分支，冲突则停下等待人工解决，不 force push。`GITHUB_TOKEN` 创建 PR / 推送分支不一定触发其他工作流，所以采集工作流自身已经做校验、测试与构建；受保护分支要求单独 CI 状态时，可从 Actions 的 Validate and test 手动选择 atlas-review 分支运行，或另行配置符合团队政策的 GitHub App。项目不绕过这些要求。

采集、持久化、校验或构建失败均不会进入部署 job，现有线上站点保留。成功采集时间仅在所有检索窗口完成后更新，与模型是否可用分开；单页预算中断不算整个检索完成。部署时间只在 deploy-pages 成功后记录到 `atlas-state:automation/deployment.json`。网站显示的是构建时已知的成功记录，通常是上一轮；最新值以该分支记录和 Pages 运行结果为准。若部署已成功但后续记录写入失败，工作流会报错，维护者应依据 deploy job 补记。

## 需要你设置的部署选项

1. 审阅 GitHub 仓库中的项目。仓库名可以是 `benchmark-atlas`。是否公开由你决定；私有仓库可用的 Pages 能力取决于账户计划。
2. Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。配置 `github-pages` environment 允许默认分支部署，按需保留人工审批。
3. Settings → Actions → General 允许需要的官方 Actions，允许工作流创建 PR。提供的 job 仅申请所需 `contents: write`、`pull-requests: write` 或 `pages: write` + `id-token: write`；PR CI 只有 `contents: read`。组织策略可进一步限制，遇到拒绝不会自动提升权限。
4. 首次只手动运行采集 workflow，保持 dry-run。确认日志和审核流程后，设置 Repository Variable **`COLLECTION_ENABLED=true`** 才启用每日持久采集。
5. 确认要公开部署后，设置 **`PAGES_ENABLED=true`**，再手动运行 Deploy reviewed site。它只允许从默认分支部署。
6. 长期保持 **`PUBLISH_MODE=review`**；如果你决定使用自动收录，再设 `PUBLISH_MODE=auto`，且启用 Pages。手动选择 auto 只影响那次采集；后续部署模式仍以仓库变量为准。

基础采集、review PR 和 Pages 不需要额外 PAT，默认使用仓库提供的 GITHUB_TOKEN。需要模型时才配置上一节三个变量/Secret。不要把 Key 写入 JSON、Markdown 或 workflow。

部署脚本自动从 `owner/repository` 得到 `SITE_URL=https://owner.github.io` 和 `BASE_PATH=/repository`；`owner.github.io` 用户站使用 `/`。本地自定义测试：

```bash
SITE_URL=https://example.github.io BASE_PATH=/my-repository npm run build
```

内链、favicon、构建 CSS/JS、静态 JSON 搜索索引与详情页都使用 base。当前测试覆盖 `/benchmark-atlas/` 和 `/test-repository/`。如果使用自定义域名，需要维护者调整 `pages_env.py` 和 Pages 域名配置；本阶段没有配置 DNS 或服务器。

## 测试与验收

```bash
npm test
.venv/bin/python -m unittest discover -s tests/python -v
npm run check
npm run build
npx playwright install chromium
npm run test:pages
node scripts/test-addition.mjs
```

浏览器测试实际访问**生产构建**，覆盖首页、标题/简称/中文搜索、组合筛选、URL 状态、空结果、重置、10 个详情地址、分类/规则页与手机宽度。新增测试在隔离副本中把真实 GAIA 条目从 pending 改为 listed，验证首页/搜索/详情由 9 篇变为 10 篇，结束后删除自己的隔离副本，不修改正式资料。

Python 测试覆盖分页、断点续采、重叠窗口、重复运行、版本更新、模型失败/缺 Key、HTTP 重试、每日配额、输入限制、仅使用基准排除、JSON 注入拒绝、XML 实体拒绝、dry-run 不落盘与人工笔记保护。合成测试资料不会发布。GitHub 工作流另用 actionlint 做静态检查。

本次验收报告和截图见 `outputs/`。尚未验证在线 PR 创建、分支保护、真实 Pages 部署、付费模型兼容性、论文实验复现或 GAIA 受限数据下载。没有提交 PDF、数据集、模型权重或密钥；只读取过官方文本材料和仓库 refs，没有 clone/执行论文项目。

## 后续维护

先持续审核条目和完善来源，再考虑扩展采集来源。定期检查 API 查询范围、失败队列和模型预算；升级依赖后使用锁文件与生产页面测试验证。分类变化应同步更新 taxonomy、JSON Schema 和测试。不要让采集草稿成为自动执行的代码，也不要把缺少运行证据的条目标为已复现。
