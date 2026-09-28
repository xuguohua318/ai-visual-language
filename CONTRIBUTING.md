# 贡献指南 / Contributing Guide

感谢你帮助视觉创作者更准确地表达想法。你可以补充缺失图片、修正现有词条，或提出新的视觉词汇。

## 提交内容

- 补图：横向 16:9，建议至少 1280×720，无水印；必须是你有权按 CC BY 4.0 发布的作品。
- 修正：请提供词条 ID、当前问题、建议文本和可核验依据。
- 新词条：需包含中英文名称、模块、分类、大白话解释、提示词示例与常见搭配。
- 避免同义重复；先搜索 `data/terms.json` 或在线图鉴。

请优先使用仓库的 Issue 模板。维护者确认内容与授权后，再创建 Pull Request 或代为合入。

## 数据约定

- 已发布的 `id` 永不复用或重新编号。
- JSON 使用 UTF-8；CSV 使用带 BOM 的 UTF-8，方便 Excel 直接打开。
- 抽象视觉图片命名为三位编号加英文短名，例如 `001-particle.webp`。
- 网站展示图统一输出为 960×540 WebP；原始高分辨率素材不进入 Git 历史。

## English

Contributions are welcome through the provided issue templates. New terms need Chinese and English names, module, category, plain-language explanation, prompt example, and common pairings. Image contributions must be redistributable under CC BY 4.0 and include attribution details.
