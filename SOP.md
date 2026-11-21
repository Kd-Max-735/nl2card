# 可编辑名片 PPT 项目 SOP

本文档约束本项目从自然语言到可编辑名片 PPT 的完整链路：

```text
自然语言
-> OpenCode/GLM5
-> business_card_builder_params.json
-> build_business_card_schema()
-> business_card.schema.json
-> shared layout plan
-> HTML / SVG / PNG / editable PPTX
-> verifier
```

本 SOP 只描述本项目，不套用 Word 表单、docx、OOXML、表格合并、页码等其它项目规则。

## 1. 目标

本项目的核心目标是生成可编辑名片 PPT，并同时导出可审查的 HTML、SVG、PNG 预览和验证报告。它不是简历生成器、海报生成器，也不是把整页截图塞进 PPTX 的截图包装工具。

一次合格交付必须满足：

1. 自然语言入口必须通过真实 OpenCode/GLM5 命令生成 `business_card_builder_params.json`；如果用户直接提供真实 builder params 文件，也可以从该文件进入 pipeline。
2. Codex 不得手写、脑补或复制固定 JSON 来冒充 GLM5 输出。
3. 没有 `--builder-params-json`，且没有可执行的 `--glm-command` / `--opencode-glm-command` 时，pipeline 必须停在模型调用层。
4. Builder 输出的 `business_card.schema.json` 语义必须是名片：姓名、职位、公司、联系方式、地址、品牌、标语、logo、头像、二维码、额外名片字段等。
5. 默认画布必须是名片尺寸，当前默认横版 90mm x 54mm，对应 340 x 204 px；不得退化成 A4 简历画布。
6. 用户明确提供的事实不得静默丢失、截断、省略或替换。
7. 用户未提供的具体事实不得自动生成；用户明确提到但留空的字段应进入 placeholder。
8. logo、avatar、QR 等媒体只能作为局部 intentional media 或占位元素，不得作为整页截图兜底。
9. HTML、SVG、PNG、PPTX 和 verifier 必须共享同一个 layout plan，并能用 `layout_plan_hash` 验证。
10. PPTX 必须由可编辑文本框、PowerPoint shape、线条、图标和局部 intentional media 组成；PNG 只是预览，不是 PPTX 主体。
11. 内容过多时必须暴露 overflow、重叠、越界、safe margin 等问题，不得删除事实或自动扩展成简历式多页来掩盖问题。

禁止事项：

- 禁止把项目做成简历、作品集、海报或长页面截图工具。
- 禁止把教育经历、项目经历、荣誉奖项、证书、自我介绍等作为名片默认结构；除非用户明确要求把某段文字作为名片字段。
- 禁止 GLM5 输出坐标、bbox、PPTX 实现细节、HTML/SVG/PPTX 代码。
- 禁止 Builder、Renderer 或 Verifier 补造姓名、公司、电话、地址、品牌、路径等事实。
- 禁止整页截图作为 PPTX 主体。
- 禁止针对某个 fixture、姓名、公司、电话、路径或 layout_style 写死规则。
- 禁止批量删除文件或目录；需要清理输出时使用新输出目录，或停止并询问用户手动处理。

## 2. 工程结构

当前真实目录和职责如下：

- `prompts/glm5_business_card_builder_params_from_nl_prompt.md`：GLM5 抽取提示词。它约束模型只输出严格 JSON，只抽取业务语义，不输出坐标或实现细节。
- `tools/run_business_card_pipeline.py`：单次 pipeline CLI。支持 `--builder-params-json` 固定 builder params 入口，也支持 `--input-request` + `--glm-command` / `--opencode-glm-command` 的真实模型入口。
- `business_card_ppt/core/schema.py`：默认名片尺寸、方向、layout_style、style、icon_policy 和 schema contract 校验。
- `business_card_ppt/business_card/builder.py`：把 builder params 归一化为 `business_card.schema.json`，负责字段、别名、placeholder、媒体、style、icon_policy、双面结构和 warning。
- `business_card_ppt/business_card/layout_engine.py`：计算共享 layout plan、元素 bbox、文本分行、媒体占位、装饰元素、双面布局和 diagnostics。
- `business_card_ppt/business_card/text_layout.py`：文本宽度估算、自然边界换行、矩形关系和 overlap/safe-area 基础判断。
- `business_card_ppt/business_card/renderer.py`：从 layout plan 渲染 SVG 和 HTML，并写入 side marker、layout hash、`data-full-text` 等可验证标记。
- `business_card_ppt/business_card/export.py`：导出 schema、HTML、SVG、PNG、PPTX 和 summary；PPTX 使用 `python-pptx` 生成可编辑文本框、shape、line、placeholder 或局部图片。
- `business_card_ppt/business_card/verifier.py`：检查文件、PPTX 可编辑文本、图片数量、整页截图风险、画布尺寸、layout hash、双面 side marker、可视文本、媒体记录、style token、overflow 和责任分类。
- `tests/`：当前覆盖 builder、pipeline、文本换行、export/verifier、双面名片、overflow、PPTX 可编辑性和 layout hash。
- `tests/fixtures/`：固定 builder params 样例，包括单面和双面。
- `outputs/`：pipeline 运行输出目录。输出目录可以新增或覆盖明确目标，但不得批量删除目录。

现状：

- 已有真实 shell 命令式 GLM 入口：命令从 stdin 读取 prompt，向 stdout 写 JSON。
- 已有固定 builder params 测试和 fake GLM 单次入口测试。
- 已有双面 schema、双面 HTML/SVG/PNG/PPTX 结构和 verifier 检查。
- 已有文本不使用省略号截断的换行测试。
- 已有 PPTX 可编辑文本、非整页截图、layout plan hash、style token、media accounting、safe margin、overflow 等检查。

建议后续补充：

- 当前未看到独立的真实 GLM5 批量 case 脚本和批量 prompt 留痕矩阵；如要验收提示词稳定性，应补充真实 GLM5 批量测试，而不是只用 fake GLM。
- 当前 schema 是 Python dict contract，未看到单独落盘维护的 JSON Schema 文件模板；若交付要求严格 schema 校验，可补充 `business_card.schema.json` 的结构化规范或 JSON Schema 文件。
- 当前 verifier 已做文本和结构检查，但 PNG 视觉质量仍可能需要人工审查或更细的像素级检查。

## 3. 数据入口与语义归一化

数据入口分为两类：

1. 真实自然语言入口：`--input-request` + `--glm-command` / `--opencode-glm-command`。
2. 已存在真实 builder params 文件入口：`--builder-params-json`。

GLM5 的边界：

- 只抽取用户明确提供的名片业务语义。
- 可抽取字段包括 `name`、`title` / `role`、`company`、`department`、`phone`、`email`、`website`、`address`、`wechat`、`qq`、`social`、`slogan` / `tagline`、`brand_name`、`extra_fields`。
- 可抽取 style/theme 意图、layout_style、logo/avatar/QR 路径或 usage、icon_policy、design、双面 front/back 语义和 uncertainties。
- 不输出坐标、bbox、字号、shape 坐标、PPTX 细节、HTML/SVG/PPTX 代码。
- 不输出 Markdown、解释、代码块、注释或非 JSON 文本。
- 不臆造用户未提供的姓名、职位、公司、电话、邮箱、地址、社交账号、品牌、标语、媒体路径等事实。

Builder 的边界：

- `build_business_card_schema()` 接收 builder params，并输出项目内部 schema。
- 它负责字段别名归一，例如 `role -> title`、`tagline -> slogan`、`tel/mobile -> phone`、`mail -> email`、`url -> website`、`location -> address`、`weixin -> wechat`。
- 它保留用户明确提供的标准字段和 `extra_fields`。
- 用户明确提到但值为空的字段，归一为 `等待用户填入`，并记录到 `placeholders.items`。
- 未提供的可选事实不生成。
- logo/avatar/qr 路径不存在时，不伪造素材；应生成占位，记录 `missing`、`placeholder` 和 warning。
- 媒体只进入 `assets.intentional_media`，并明确不是整页截图。
- 业务不应生成 `education`、`sections` 等简历结构。

事实保留规则：

- 用户明确给出的姓名、职位、公司、部门、联系方式、地址、品牌、标语、logo/avatar/qr、额外字段必须进入 schema，并在可视产物中可检查。
- 如果字段从 builder params 进入 schema 后没有进入 HTML/SVG/PPTX 可视文本或 intentional media，verifier 应失败。
- 如果证据不足以判断某个输入是否为事实，记录到 `uncertainties`；不要猜。

## 4. Layout / Renderer / PPTX 可编辑性

共享 layout plan 是本项目的排版事实源。HTML、SVG、PNG、PPTX 和 verifier 不得各自重新解释排版。

Layout 必须负责：

- 根据 `card_size`、`content_area`、`safe_margin`、字段数量、文本长度、媒体存在性、style 和 layout_style 计算元素 bounds。
- 计算文本分行、文本框高度、overflow、overlap、safe_margin、line_conflicts、text_errors 等 diagnostics。
- 支持当前 layout_style：`left_logo_right_info`、`top_logo_bottom_info`、`centered`、`split_panel`、`minimal_corner`、`black_white_double_sided`。
- 规则必须适用于所有 layout_style，不得只为某个 fixture 或某个样例名片写死。

名片尺寸与安全边距：

- 默认横版为 340 x 204 px，90mm x 54mm。
- 支持 `horizontal_card` 和 `vertical_card`。
- safe margin 和 content area 由 `card_size_from_params()` 归一化；元素不得越出名片画布，关键文本和媒体不得越出安全内容区。
- 不得用 A4 或简历页面尺寸作为默认画布。

文本换行与 overflow：

- 换行是 Layout 的全局能力，不是某个 Renderer 的临时行为。
- 英文、网址、邮箱、品牌短语、地址应优先按空格、连字符、斜杠、冒号、点号、`@` 等自然边界换行。
- 禁止为了看起来不溢出而用省略号隐藏显式事实。
- 禁止把品牌词或英文单词粗暴切成不自然片段，例如 `OFFIC / E`。
- 内容仍无法安全容纳时，layout/verifier 必须报告 overflow，而不是删除字段或改成多页简历。

装饰元素避让：

- 背景、纹理、线条、几何块必须位于可控层级中。
- 黑色结构线、几何块、装饰线不得遮挡或穿过姓名、公司、联系方式、地址、logo、QR 等关键元素。
- 当前 layout diagnostics 已检查 line-vs-content 冲突；后续新增装饰元素也必须接入同类检查。

联系方式图标：

- contact icons 是联系字段的辅助视觉，不是事实来源。
- 图标缺失时可以 fallback 或省略，但电话、邮箱、地址等文本事实不得因此丢失。
- 极简风格可关闭 contact icons；若用户明确要求图标，应通过 `icon_policy.force_contact_icons` 保留。

双面名片：

- 单面是默认；双面只在用户明确要求或 builder params 明确包含 `sides.front` / `sides.back` 时启用。
- 如果 schema 中存在双面结构，HTML、SVG、PNG、PPTX、summary 和 verifier 都必须体现 front/back。
- SVG/HTML 必须有可检测 side marker，例如 `data-card-side="front"` 和 `data-card-side="back"`。
- 背面不得自动复制正面的姓名、职位、联系方式，除非用户明确要求。
- 当前实现倾向于双面 PPTX 分成两张 slide；如未来改为单 slide 双面组合，必须提供 front/back object marker，并更新 verifier。

PPTX 可编辑性：

- PPTX 必须使用可编辑文本框承载文字。
- shape、line、placeholder 和局部图片应作为独立可编辑或可替换对象。
- PNG 只是预览产物，不得作为 PPTX 主体。
- PPTX 中图片数量不得超过 loaded intentional media 数量；如果出现超额图片或命名中出现 screenshot/full-page 风险，verifier 必须失败。
- PPTX 文本应使用 layout 已计算好的分行和高度；不要让 PowerPoint/WPS 生成未被 layout plan 记录的自动换行。

## 5. 测试与交付

交付物：

```text
business_card_builder_params.json
business_card.schema.json
business_card.html
business_card.svg
business_card.png
business_card.pptx
summary.json
verification_report.json
```

运行测试：

```powershell
python -m pytest .\tests -q
```

使用真实 builder params：

```powershell
python .\tools\run_business_card_pipeline.py `
  --builder-params-json .\tests\fixtures\sample_business_card_builder_params.json `
  --output-dir .\outputs\sample
```

使用 OpenCode/GLM5：

```powershell
python .\tools\run_business_card_pipeline.py `
  --input-request .\examples\input_request.md `
  --glm-command "your-glm5-json-command" `
  --output-dir .\outputs\from_nl
```

测试分层：

- 固定 builder params 测试：验证 Builder、Layout、Renderer、Export、Verifier 的结构稳定性。当前 fixture 覆盖单面和双面。
- 真实 GLM/OpenCode 入口测试：验证自然语言是否能通过真实模型转成 builder params。fake GLM 只能证明 CLI 调用链，不等同于真实模型验收。
- 导出文件检查：验证 schema、HTML、SVG、PNG、PPTX、summary、verification_report 是否存在。
- PPTX 可编辑性检查：读取 PPTX 内部 slide XML，确认关键文本以可编辑文本存在，确认没有整页截图主体。
- 可视文本覆盖检查：SVG/HTML 的 visible text 应与 `data-full-text` 一致；schema / builder params 中显式事实应出现在可视产物或 intentional media 中。
- layout 统一性检查：summary、SVG、HTML、verifier 使用同一 `layout_plan_hash`。
- 双面检查：front/back side marker、side_count、背面不泄漏正面专属联系方式。
- overflow 检查：内容过密时 verifier 必须失败并给出原因。

验收失败时的定位顺序：

1. GLM5 Prompt：模型是否输出严格 JSON，是否丢事实、造事实、输出坐标或输出 Markdown。
2. Builder：事实、别名、placeholder、media、style、双面结构、warning 是否正确进入 schema。
3. Layout：bounds、lines、safe margin、overlap、line_conflicts、overflow 是否正确。
4. Renderer/Export：HTML/SVG/PPTX 是否消费同一 layout plan，PPTX 是否可编辑，PNG 是否仅预览。
5. Verifier：检查项是否覆盖了问题，错误分类是否能指向责任层。
6. Tests：是否只换姓名/标题凑样例，还是覆盖了真实结构变化。

循环修复标准：

- 每次发现失败，先记录输入、命令、输出目录、期望、实际、相关文件和错误报告。
- 证据不足时明确“不确定”，不要猜测责任层。
- 能自动检查的规则进入 tests；只能人工判断的规则写入验收清单并说明判断依据。
- 修复后运行相关测试；涉及全链路行为时运行 `python -m pytest .\tests -q`。
- 如果需要清理旧输出，不得批量删除目录；使用新的 `--output-dir`，或停止并请用户手动删除。

## 6. GLM5 真实入口与提示词验收

真实入口的目标是验证：

```text
用户自然语言
-> GLM5/OpenCode
-> business_card_builder_params.json
-> schema
-> layout/export
-> verifier
```

不得用 Codex 手写 JSON 冒充模型输出。没有 builder params 且没有真实 GLM 命令时，pipeline 必须停止在模型调用层。

当前 CLI 契约：

- `--glm-command` / `--opencode-glm-command` 必须能从 stdin 读取完整 prompt 和用户输入。
- 命令必须向 stdout 输出严格 JSON。
- 返回非 JSON 或命令失败时，pipeline 应失败并暴露错误。
- pipeline 会把生成的 `business_card_builder_params.json` 写入输出目录。

提示词必须约束：

- 只输出一个合法 JSON 对象。
- 不输出 Markdown、解释、代码块、注释、坐标、bbox、渲染代码或 PPTX 实现细节。
- 保留用户明确给出的事实、路径、品牌、字段标签、额外字段和双面意图。
- 未提供的具体事实不补造。
- 媒体路径缺失时输出 placeholder usage 或保留缺失路径，让 Builder 记录 warning。
- 用户要求双面时输出 `sides.front` / `sides.back`；背面不自动复制正面个人联系方式。
- 跨领域输入必须仍然落到名片业务字段或 `extra_fields`，不得生成简历 sections。

真实入口验收：

- `business_card_builder_params.json` 由真实 GLM5/OpenCode 命令产生。
- 输出目录保留 `input_request.md`、builder params、schema、HTML、SVG、PNG、PPTX、summary、verification_report。
- summary/verifier 中不得包含真实 API Key、数据库密码或敏感凭证。
- 关键业务事实必须同时体现在 builder params、schema、可视产物和 PPTX 可编辑文本中。
- 未给出的高风险事实不得出现在 builder params 或 schema 中。
- 若模型输出失败，必须保留错误原因，不得自动回退到 Codex 手写 JSON。

建议后续补充：

- 增加真实 GLM5 批量 case 脚本，独立于固定 builder params。
- 每个真实 case 保存 prompt、模型原始输出、normalized/schema、产物、summary 和 verification_report。
- 批量 case 覆盖完整输入、极简输入、字段为空、路径缺失、别名/口语、严格限制、双面名片、媒体占位、长文本 overflow、layout_style 变化和越界要求。
- 批量调用应串行限速和重试退避，避免模型限流。

## 7. 返工问题沉淀

返工问题必须沉淀为全局规则，而不是给单个样例打补丁。每个问题都要记录本质原因、解决原则和验收方式。

### 事实丢失

- 本质原因：模型、Builder、Layout 或 Export 中某层把用户显式字段当成可选装饰，或空间不足时静默省略。
- 解决原则：显式事实必须进入 schema，并进入 HTML/SVG/PNG/PPTX 的可视结果或 intentional media；空间不足时报 overflow。
- 验收方式：检查 builder params、schema、SVG/HTML visible text、PPTX editable text 和 verification_report。

### 名片被做成简历

- 本质原因：把自然语言中的个人信息扩展成教育、项目、经历、荣誉等长文档结构。
- 解决原则：默认只生成名片字段；非名片事实只在用户明确要求作为名片字段时进入 `extra_fields`。
- 验收方式：schema 中不得出现 `education`、`sections` 等简历结构；画布不得是 A4。

### PPTX 不可编辑

- 本质原因：导出层用图片或截图替代文本框和 shape。
- 解决原则：文字使用 editable textbox，形状使用 PowerPoint shape/line，局部媒体使用 picture 或 placeholder。
- 验收方式：读取 PPTX slide XML，确认关键文字存在于文本节点；图片数量不超过 loaded intentional media。

### 整页截图兜底

- 本质原因：为了快速复刻预览，把 PNG 当成 PPTX 主体。
- 解决原则：PNG 只能作为预览；PPTX 必须由 layout element 转成独立对象。
- 验收方式：PPTX shape name 和 media count 不得出现 full-page/screenshot 风险；verifier 的 `no_full_page_screenshot` 必须为 true。

### layout plan 分裂

- 本质原因：HTML/SVG/PPTX/verifier 分别计算或依赖各自自动换行，导致不同格式表现不一致。
- 解决原则：Layout plan 是唯一排版事实源；所有导出和验证使用同一个 hash。
- 验收方式：summary、SVG、HTML、verifier 的 `layout_plan_hash` 一致；PPTX 文本分行遵循 layout 结果。

### 文本溢出 / 重叠

- 本质原因：长文本、联系方式、地址、额外字段或媒体占位没有纳入 bounds 和高度估算。
- 解决原则：先按自然边界换行和局部字号档位处理；仍放不下则报告 overflow。
- 验收方式：layout diagnostics 不应有 overlaps、safe_margin_errors、text_errors；过密样例必须失败而不是截断。

### 双面名片漏背面

- 本质原因：Renderer/Export 只读取 front 或 `layout_plan.elements`，忽略 `layout_plan.sides`。
- 解决原则：一旦 schema 有 `sides.front/back`，所有产物都必须体现双面。
- 验收方式：SVG/HTML 有 front/back marker；summary side_count 为 2；PPTX 有背面内容；背面不泄漏正面个人联系方式。

### 媒体路径 / 占位不规范

- 本质原因：模型或 Builder 伪造媒体路径，或路径缺失时未记录 warning。
- 解决原则：用户给路径就保留路径；路径不存在则占位并记录 warning；用户只要求媒体但无路径则使用 placeholder usage。
- 验收方式：schema assets、summary intentional_media、warnings、PPTX placeholder 或 picture 数量一致。

### 装饰元素遮挡内容

- 本质原因：背景线、几何块或纹理没有避让关键内容。
- 解决原则：装饰元素必须接入 line/content conflict 检查；冲突时移动、拆分、降低层级或报告 layout conflict。
- 验收方式：`layout_diagnostics.line_conflicts` 为空；人工查看 PNG 时关键内容未被遮挡。

### 联系方式图标影响事实

- 本质原因：把 icon 是否存在和 contact 文本是否渲染绑在一起。
- 解决原则：icon 只是视觉辅助；图标缺失不影响 contact 文本输出。
- 验收方式：缺少 icon 时 contact 字段仍进入 schema、SVG/HTML、PPTX；fallback_icons 或 warning 可追踪。

### 测试只换姓名但不验证结构

- 本质原因：测试样例只改值，不触发 layout、media、双面、overflow、style 或 verifier 的结构差异。
- 解决原则：测试必须覆盖责任层：固定 builder params 测结构，真实 GLM 测入口，verifier 测失败条件。
- 验收方式：每个新增 case 说明它验证了哪个层和哪类结构变化；不得用同结构不同姓名凑覆盖率。

### 代码能力不足但 SOP 先行

- 本质原因：文档规则超出现有实现，导致交付时假装已支持。
- 解决原则：能从当前代码和测试确认的写成“现状”；未确认或未实现的写成“建议后续补充”。
- 验收方式：SOP 更新时对照 `README.md`、project flow、实现和 tests；不确定性必须显式记录。
