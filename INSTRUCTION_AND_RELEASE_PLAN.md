# LLM Wiki Skill 指令与发布方案

## 目标

把 `$llm-wiki` 从“单一大入口”整理成一个可发布、可发现、可维护的 skill bundle：

- 保留 `$llm-wiki` 主 skill 作为唯一协议源。
- 把高频二级命令拆成 superpowers 风格的短入口 wrapper。
- 让用户输入一句短提示词就能触发完整流程。
- 把发布单位从“一堆散落 skill”收敛成一个 bundle 目录。

## 入口拆分

主 skill：

- `$llm-wiki`

高频 wrapper：

- `$llm-wiki-fast`：一口气初始化新 LLM Wiki。
- `$llm-wiki-init`：分阶段初始化。
- `$llm-wiki-update`：增量更新 raw、raw-code 和受影响 wiki；也负责续跑、精修、代码 wiki 和 traceability 收口。
- `$llm-wiki-doctor`：只读诊断健康度、缺口和质量问题，集合原 audit 能力。
- `$llm-wiki-query`：按意图分流回答业务或代码问题；业务知识默认不展开大量代码证据。
- `$llm-wiki-query-plus`：同时回答业务/需求口径与代码实现证据。
- `$llm-wiki-image`：补充高价值图片证据。
- `$llm-wiki-add-wiki`：添加其他文档/wiki 目录到 raw 证据层。
- `$llm-wiki-add-code`：添加其他项目代码到 raw-code 证据层，并构建代码 wiki、能力页和必要 traceability。
- `$llm-wiki-update-skill`：更新本机安装的 llm-wiki skill bundle。

命名约定：

- skill name 和 display name 使用英文，例如 `llm-wiki-update`、`LLM Wiki Update`。
- description、short_description、default_prompt 使用中文。
- wrapper 正文保持很薄，只转发到 `$llm-wiki <command>`，避免复制主协议。

## 命令命名调整

为了降低用户心智负担：

- `resume`、`refine`、`build-code`、`code-trace` 合并进 `llm-wiki update`。
- `audit` 合并进 `llm-wiki doctor`。
- `ship` 不再作为二级入口暴露；提交、推送、发布走用户明确要求下的普通 git 流程。
- 新代码库接入仍使用 `llm-wiki add-code`。

## update 收口规则

`$llm-wiki-update` 应当默认一次性完成可安全自动完成的工作，而不是把同一轮的尾巴丢给“建议下一步”。

标准顺序：

1. 读取 `BUSINESS_CONTEXT.md` 和当前状态。
2. 优先执行项目内确定性更新入口，例如 `uv run python tools/update_wiki.py`。
3. 读取 `staging/update/latest.md` 和 `staging/update/latest.json`。
4. 刷新受影响 source、concept、entity、layer index、overview/index。
5. 如果同一轮影响代码证据，刷新受影响 codebase、capability 和 traceability。
6. 如果发现当前命令能安全完成的 `pending`、`stale`、source 精修、code-trace、health、graph 工作，应继续完成。
7. 只有遇到 blocker，或用户明确要求只做诊断/确定性阶段时，才建议后续继续 `llm-wiki update`。

这条规则避免出现这种体验：

```text
你刚执行 update，然后它建议你再执行 update。
```

正确口径是：

```text
当前 update 能做的，就在当前 update 内做完。
```

## add-wiki

`$llm-wiki-add-wiki` 用于把其他文档、wiki 目录或 wiki URL 接入当前 LLM Wiki：

- 目标层：`raw/`
- 证据类型：业务、产品、需求、运营、规则、接口文档等文本证据
- 必须保留来源信息
- 输入为 wiki URL 时，先尝试根据 URL 和平台元数据推导 RSS/feed URL
- 如果 RSS/feed URL 无法推导，必须明确告诉用户并要求用户手动输入对应 RSS；用户不输入则保留为空，该来源后续自动更新不可完成
- 不在原始目录原地改写证据
- 遇到 raw 目录冲突、来源授权不清、canonical entity 需要改变时停下确认

完成后进入常规 update：

```text
add-wiki -> update -> affected source/concept/entity refinement -> health -> graph
```

## add-code

`$llm-wiki-add-code` 用于把其他项目代码接入当前 LLM Wiki：

- 目标层：`raw-code/<codebase_id>/`
- 证据类型：源码、README、AGENTS、OpenSpec、接口契约、配置、任务、消息、数据访问等实现证据
- 不混入 `raw/`
- codebase_id 从仓库名或目录名生成，冲突时停下确认
- 复制 secrets、依赖目录、构建产物或覆盖已有 codebase 前必须确认

完成后进入代码 wiki：

```text
add-code -> build-code -> capability links -> code-trace when relevant -> health -> graph
```

## 发布方式

发布单位是一个 skill bundle 仓库，而不是每个 skill 一个仓库。

推荐目录：

```text
llm-wiki-skill/
  README.md
  install.sh
  INSTRUCTION_AND_RELEASE_PLAN.md
  skills/
    llm-wiki/
    llm-wiki-update/
    llm-wiki-doctor/
    ...
```

安装方式：

```bash
./install.sh --copy --backup
```

开发方式：

```bash
./install.sh --link --backup
```

这样别人只需要 clone 一个仓库，就能安装全部入口。

安装脚本默认安全优先：如果目标 skill 已存在，会拒绝覆盖。使用 `--dry-run` 预览，使用 `--backup` 备份旧目录后安装，只有明确传 `--force` 才会删除旧目录。

## engine-v0.1.0（发布切片）

**标签：** Git tag `engine-v0.1.0` 打在 `llm-wiki-skill` 仓库；对应 **manifest + RSS + 确定性更新链** 契约冻结。

**包含：**

- `skills/llm-wiki/assets/project-template/` 下标准工具链：`tools/update_wiki.py`、`tools/build_wiki.py`、`tools/health.py`、`tools/build_graph.py`、`tools/rss_sync.py`、`config/rss-feeds.yaml` 示例。
- KB 根目录 **`kb.manifest.yaml`** 声明引擎版本、证据开关、RSS 阶段与可选覆盖。
- Gateway **`agent-gateway/config/knowledge-bases.yaml`** 必须与各 KB 的 manifest **交叉校验**（`capabilities`、`evidence.*`）；对齐规则见 `knowledge-base` 设计规格 `docs/superpowers/specs/2026-05-11-multi-knowledge-base-upgrade-design.md`。

**`kb.manifest.yaml` 示例（冻结字段）：**

```yaml
engine_version: "engine-v0.1.0"

capabilities:
  - wiki.query
  - wiki.update

evidence:
  raw: true
  raw_code: true

phases:
  rss_sync: false

rss_config_path: "config/rss-feeds.yaml"

overrides:
  # update_command: ["uv", "run", "python", "tools/custom_update.py"]
  # skip_phases: ["ai_pass"]
  # env:
  #   UV_CACHE_DIR: "/tmp/uv-cache"
```

**Gateway 提示：** 运维验收时对比仓库内 `kb.manifest.yaml` 与 Gateway 注册表中同名 `kbId` 的配置；漂移时应在 Job `issues[]` 中可见，而非静默失败。

## 后续维护原则

- 主协议只改 `skills/llm-wiki/`。
- wrapper 只在新增/改名/调整触发说明时修改。
- 每次修改后运行 skill validator。
- 如果新增项目级工具脚本，应放在具体 LLM Wiki 项目内；不要把一次性项目 workflow 硬塞进通用 skill，除非它已经成为稳定通用能力。
