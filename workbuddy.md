# WorkBuddy 开发上下文

> 本文件记录本项目使用**腾讯 WorkBuddy 智能体**进行开发的真实上下文，
> 用于参与「麦当劳程序员创意开发大赛」WorkBuddy 专项奖励核验。

---

## 一、开发方式说明

本项目由参赛者在 **WorkBuddy** 中通过自然语言对话驱动开发完成：
从赛事调研、选题查重、架构设计、代码编写、脚本调试到参赛文档生成，
全部在 WorkBuddy 会话内完成，WorkBuddy 负责实际的工具调用与文件读写。

**开发环境**（WorkBuddy 托管运行时）：
- Python 3.13.12（`C:\Users\123\.workbuddy\binaries\python\versions\3.13.12\python.exe`）
- Git 2.55.0
- 依赖策略：仅 Python 标准库，零第三方依赖，保证任何环境可直接运行

---

## 二、开发过程记录（真实时序）

### 阶段 1 · 赛事与能力调研

用户提出需求后，WorkBuddy 执行：

1. **网络调研**：搜索「麦当劳 MCP 大赛」「McDonald's China MCP」，确认
   - 官方 MCP 仓库：`M-China/mcd-mcp-server`
   - 活动仓库：`M-China/mcd-developer-innovation-challenge`
2. **读取官方 README**：提取完整 33 个 MCP 工具清单、接入地址 `https://mcp.mcd.cn`、
   鉴权方式、限流规则（600 次/分钟）、错误码（401/429）
3. **读取活动规则** `activityGuidelines.md`：确认
   - 活动时间 2026-10-09 10:30 ~ 2026-10-25 23:59
   - 必需文件：`README.md`、`CONTEST_DECLARATION.md`、`MCP_INTEGRATION.md`、
     `mcp-config.example.json`、`workbuddy.md`
   - WorkBuddy 专项奖励 3000 积分的获取条件
   - 官方 Issue 提交格式
4. **读取参赛声明模板** `CONTEST_DECLARATION.md`

### 阶段 2 · 选题查重（关键决策）

WorkBuddy 通过 GitHub API 抓取活动仓库 **335 个**已提交参赛项目的名称，逐页解析统计，得出赛道分布：

| 赛道 | 撞车情况 |
| --- | --- |
| 省钱 / 精算 | 高度饱和（省钱助手、省钱军师、省钱精算局、麦门精算师 ×2、Saver、Budget Planner…） |
| 营养 / 健康 | 高度饱和（膳食师、心膳、轻食官、控卡、减脂期…） |
| 积分 | 已有 5 个（积分清算局、积分经济学、积分钱庄、积分猎人、锦鲤抽奖） |
| 人格 / 玄学 / 年鉴 | 已饱和 |
| **派对 / 主题活动** | **仅 2 个泛化项目，party 工具链未被深挖** |

**决策依据**：麦当劳 MCP 于 2026-07（v1.0.7）新增的
`query-party-city / query-party-store / query-partystore-date / query-partystore-session / party-order-create`
工具链几乎无人深度产品化。这是**差异化切入点**。

**最终定位**：把一场派对当项目交付 —— 融合项目管理方法论（WBS / Runbook / 风险登记），
既避开红海，又把「程序员节」的身份认同做进产品里。

### 阶段 3 · 代码开发

WorkBuddy 创建项目结构并编写：

| 文件 | 内容 |
| --- | --- |
| `SKILL.md` | Skill 主入口：五幕工作流、安全红线、输出风格、价格单位坑点 |
| `scripts/party_planner.py` | 人数配比模型、菜单选品、券组合枚举优化、积分抵扣、三档方案 |
| `scripts/runbook.py` | 分钟级时间轴、物料清单、风险登记表、WBS |
| `scripts/mcp_client.py` | MCP Streamable HTTP 客户端（含 SSE 解析、401/429 处理、Token 环境变量安全读取） |

### 阶段 4 · 调试与修正（真实发现的问题）

WorkBuddy 运行脚本并**实际发现并修复了两个缺陷**：

1. **券叠加约束错误**
   - 现象：输出「生日专享15元（不可叠加）+ 满50减8 + 满100减20 = -¥43」的**非法组合**
   - 原因：原代码只限制「不可叠加券最多一张」，未限制「不可叠加券不可与其他券同用」
   - 修复：增加 `if non_stack_in and len(combo) > 1: continue`
   - 复测：最优解正确变为两张可叠加券 `-¥28`

2. **三档方案是假的**
   - 现象：经济/豪华档用 `final × 0.8 / × 1.25` 乘数缩放，不是真实报价
   - 修复：为每档定义独立配比缩放因子，**重新走一遍选品 + 券 + 积分完整计价**
   - 复测：三档各自输出真实备货量与实付金额

3. **笔误修复**：`mcp_client.py` 中一行无效的 `argparse` 赋值语句，改为在文件顶部正常导入

### 阶段 5 · 验证

WorkBuddy 实跑通过：

```
# 有菜单 + 券 + 积分
python scripts/party_planner.py --people 12 --age kid --scene birthday --budget 300 \
  --menu examples/menu.sample.json --coupons examples/coupons.sample.json \
  --points 3000 --points-value 30
→ 原价 ¥405 → 券 -¥28 → 积分 -¥30 → 实付 ¥347，人均 ¥28.92，触发超预算告警 ✓

# 无菜单降级（零幻觉）
python scripts/party_planner.py --people 8 --budget 500
→ 仅输出配比与预算分配，明确提示「未提供菜单，不出报价」 ✓

# Runbook
python scripts/runbook.py --start 14:00 --people 12 --age kid --scene birthday
→ 10 步分钟级时间轴 + 10 项物料 + 6 条风险 + 三段 WBS ✓
```

### 阶段 6 · 参赛文档生成

WorkBuddy 生成比赛五件套：`README.md`、`CONTEST_DECLARATION.md`、
`MCP_INTEGRATION.md`、`mcp-config.example.json`、本文件 `workbuddy.md`。

---

## 三、WorkBuddy 在本项目中的具体作用

| 环节 | WorkBuddy 做了什么 |
| --- | --- |
| 赛事调研 | 网络检索 + 抓取 GitHub 官方仓库与活动规则原文 |
| 竞品查重 | 调 GitHub API 分页拉取 335 个参赛项目并解析统计 |
| 选题决策 | 基于数据给出差异化方向建议并被采纳 |
| 架构设计 | 确定「MCP 拿数据 + 本地脚本算决策」的零幻觉架构 |
| 代码编写 | 编写 3 个 Python 脚本 + SKILL.md，共约 900 行 |
| 调试纠错 | 实跑发现并修复券叠加约束、三档假报价、导入笔误 |
| 文档生成 | 按活动规则要求生成全套参赛文档 |
| 环境管理 | 使用 WorkBuddy 托管 Python 运行时，不污染系统环境 |

---

## 四、零幻觉架构说明（本项目的核心设计）

WorkBuddy 在设计时确立了一条硬原则：**LLM 不做算术，MCP 不做决策**。

```
MCP（真实数据）  →  本地脚本（确定性计算）  →  LLM（表达与组织）
   门店/菜单/券        配比/枚举/计价             方案呈现
```

- 所有数字来自 MCP 真实返回或脚本计算，**没有一处由模型凭记忆生成**
- 未提供菜单时脚本拒绝报价，只给配比（已在测试中验证）
- 券组合用枚举法保证全局最优，而非贪心近似

这一设计是为了避免 LLM 在涉及**真实金钱**的场景下产生幻觉报价。

---

## 五、声明

- 本项目**真实使用腾讯 WorkBuddy 智能体**开发，上述开发过程为真实记录
- 仓库中不含任何真实 Token、密钥或个人信息，`mcp-config.example.json` 仅含占位符
- 本项目为参赛作品，非麦当劳官方产品，亦非 WorkBuddy 官方产品

**申请参与 WorkBuddy 专项奖励（3000 积分）。**
