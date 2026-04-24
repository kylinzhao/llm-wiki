---
name: llm-wiki
description: 在项目中从 0-1 初始化、构建、增量维护、查询和审查一套基于 raw 文档与 BUSINESS_CONTEXT.md 的 LLM Wiki。适用于新项目冷启动、wiki 目录搭建、文本优先语义精修、实体/概念归一化、graph/health 维护、以及新窗口中的业务问答和质量检查。
---

# LLM Wiki

这个 skill 面向“文件型 LLM Wiki 项目”的全生命周期，而不只是查询。
它也是这类项目后续唯一推荐维护和调用的统一入口，不再需要拆分单独的 query-only skill。

它适用于：

- 新项目 0-1 初始化
- 已有项目的增量构建
- `BUSINESS_CONTEXT.md` 驱动的业务语义规范化
- 基于 `wiki/` 的查询与审查

## 必查入口

开始前先确认项目根目录里是否存在：

- `raw/`
- `BUSINESS_CONTEXT.md`

如果项目已经初始化，还要确认：

- `wiki/index.md`
- `wiki/overview.md`
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`

如果缺文件，不要假装项目已经完整可用，要先说明缺什么，再走初始化或补档流程。

## 阅读顺序

### 新项目 / 构建任务

- `/Users/zhaoliang/.codex/skills/llm-wiki/README.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/bootstrapping.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/build-and-maintenance.md`

### 已有项目 / 查询任务

- `/Users/zhaoliang/.codex/skills/llm-wiki/README.md`
- `docs/retrieval-playbook.md`
- `docs/build-and-maintenance.md`

### 按需读

- `/Users/zhaoliang/.codex/skills/llm-wiki/references/project-principles.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/wiki-structure.md`
- `/Users/zhaoliang/.codex/skills/llm-wiki/references/query-logic.md`

## 核心工作方式

### 1. 新项目优先构建，不优先查询

如果项目还没有 `wiki/` 骨架，应先做：

1. 检查 `raw/` 和 `BUSINESS_CONTEXT.md`
2. 初始化目录结构
3. 运行确定性构建
4. 运行健康检查
5. 再进入 AI-native 精修
6. 最后构建 graph

### 2. 已有项目优先读 BUSINESS_CONTEXT

在任何生成、查询、审查任务前，如果根目录存在：

- `BUSINESS_CONTEXT.md`

都要优先读取它，并把它当成业务语义基线。

### 3. 默认文本优先

除非用户显式要求或文本不足以回答，否则默认：

- 不主动做图片多模态识别
- 不把 `staging/image-notes/` 当默认主链路

### 4. 查询路径必须显式

不管是问答还是审查，都要说明：

- 问题类型
- 是否用了 `BUSINESS_CONTEXT.md`
- 先查哪一层目录
- 有没有用 `concepts / entities` 扩展
- 最终依据了哪些 `sources`

### 5. 规范实体优先

优先使用项目内规范实体，而不是历史别名。

例如在当前项目里：

- `C1` = 卖车 C 端用户
- `C2` = 购车 C 端用户
- `车主` = `C1` 的历史别名

如果旧页面和 `BUSINESS_CONTEXT.md` 冲突，应优先按 `BUSINESS_CONTEXT.md` 理解，并在回答中指出冲突。

## 任务模式

### A. 0-1 初始化

适用于：

- 新项目只有 `raw/`
- 新项目已有 `raw/` 和 `BUSINESS_CONTEXT.md`
- 需要搭一整套 `wiki/graph/staging/tools/docs`

### B. 增量构建

适用于：

- 新增了一批 `raw/`
- 更新了 `BUSINESS_CONTEXT.md`
- 调整了 taxonomy / entity 规则

### C. 查询问答

适用于：

- 业务问题
- 专题串讲
- 概念/实体解释
- 分层目录解释

### D. 质量审查

适用于：

- 检查 wiki 是否真的可用
- 检查实体/概念冲突
- 检查 layered pages 是否错分

## 输出要求

### 构建任务

至少说明：

1. 当前处于哪个阶段
2. 缺什么输入
3. 先执行哪些命令
4. 后续还需要哪些 AI-native 步骤

### 查询任务

至少说明：

1. 查询类型
2. 检索路径
3. 结论
4. 支撑页面
5. 未决点

### 审查任务

必须 findings first。

## 推荐入口

### 新项目初始化

`Use $llm-wiki to bootstrap a new LLM Wiki project from raw/ and BUSINESS_CONTEXT.md. Explain the phases first, then initialize the structure, build deterministic outputs, and tell me what still needs AI-native refinement.`

### 查询已有 wiki

`Use $llm-wiki against this project. Read BUSINESS_CONTEXT.md first, state the query type and retrieval path, then answer with supporting wiki pages and unresolved points.`

### 质量审查

`Use $llm-wiki to audit this wiki project. Check entry usability, semantic consistency, retrieval usefulness, layered-page quality, and concept/entity conflicts. Put findings first with file paths and a final usability verdict.`
