# nl2card

自然语言 → 可编辑名片 PPTX 流水线。

**Natural language → editable business card PPTX.** GLM5 extracts semantic
parameters only; SVG / HTML / PNG / PPTX share one layout plan; a verifier
checks that the result is really editable.

![示例名片](docs/demo.png)

> 上图由 `tests/fixtures/sample_business_card_builder_params.json` 直接生成，未经手工修饰。

## 它解决什么

让模型只做语义提取，把排版、渲染、导出、校验交给确定性代码：

```text
自然语言输入
-> OpenCode/GLM5
-> business_card_builder_params.json
-> build_business_card_schema()
-> business_card.schema.json
-> 共享 layout plan
-> HTML / SVG / PNG / 可编辑 PPTX
-> verifier
```

Codex 不得手写 `business_card_builder_params.json` 绕过 GLM5。如果没有真实的
builder params 文件、也没有可用的 OpenCode/GLM5 命令，流水线会停在模型调用层。

## 安装

```powershell
pip install -r requirements.txt
```

仅在需要导出 PNG（HTML -> PNG）时，额外执行一次：

```powershell
playwright install chromium
```

## 快速开始

### 用真实 builder params

```powershell
python .\tools\run_business_card_pipeline.py `
  --builder-params-json .\tests\fixtures\sample_business_card_builder_params.json `
  --output-dir .\outputs\sample
```

### 用 OpenCode/GLM5

GLM 命令必须从 stdin 读取提示词，向 stdout 输出严格 JSON。

```powershell
python .\tools\run_business_card_pipeline.py `
  --input-request .\examples\input_request.md `
  --glm-command "your-glm5-json-command" `
  --output-dir .\outputs\from_nl
```

`--opencode-glm-command` 是 `--glm-command` 的别名。

### 跑测试

```powershell
python -m pytest .\tests -q
```

## 产物

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

PPTX 的页面尺寸跟随名片画布，不是 A4。默认横向 90mm x 54mm，对应 340 x 204 px。

## 设计边界

- GLM5 只提取语义 builder params，不生成坐标。
- Builder 保留名片事实，并归一化样式、媒体、占位元素、图标策略、画布尺寸与布局意图。
- Renderer / export 共用同一份 layout plan。
- PPTX 使用可编辑文本框、PowerPoint 形状与本地图片，禁止拿整页截图当名片主体。
- 缺失的 logo / 头像 / 二维码渲染为本地占位，并记入 warnings 与 `intentional_media`。
- 内容放不下时报告 overflow，不静默分页、不删除事实。

## 目录结构

```text
business_card_ppt/
  core/           schema 与数据模型
  business_card/  builder / layout_engine / renderer / export / verifier
  io/             输出写入
tools/            run_business_card_pipeline.py 命令行入口
prompts/          GLM5 提示词
examples/         示例输入
tests/            单元测试与 fixtures
svg_material/     联系方式图标
docs/             README 用示例图
outputs/          运行时产物（已在 .gitignore 中忽略）
SOP.md            完整作业规范
```
