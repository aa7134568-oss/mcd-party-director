<div align="center">

<img src="./assets/banner.png" alt="麦麦派对总导演 McParty Director" width="100%">

# 🍔 麦麦派对总导演 · McParty Director

**把一场麦当劳派对，当成一个项目来交付。**

WBS 分解 · 选址排期 · 预算精算 · 现场 Runbook · 风险登记 · 一键下单

[![MCP](https://img.shields.io/badge/MCP-McDonald's%20China-FFC72C?logo=mcdonalds&logoColor=black)](https://github.com/M-China/mcd-mcp-server)
[![Built with WorkBuddy](https://img.shields.io/badge/Built%20with-WorkBuddy-0052D9)](https://www.workbuddy.cn)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Contest](https://img.shields.io/badge/2026%20麦当劳程序员创意开发大赛-参赛作品-DA291C)](https://github.com/M-China/mcd-developer-innovation-challenge)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

</div>

一个基于 **麦当劳中国官方 MCP** 的创意 Skill：你说一句「给孩子办个生日会」，
它交付的是一份**能直接落地的项目包**——WBS 分解、选址排期、预算精算、现场 Runbook、风险登记表，
最后通过官方 MCP 完成真实预约下单。

2026 麦当劳程序员创意开发大赛参赛作品 · 由 **WorkBuddy** 辅助开发。

---

## ✨ 为什么是它

市面上的麦当劳 MCP 项目大多在做「点餐助手」：选品、算价、下单。
而麦当劳 MCP 里有一组**几乎没人深挖**的能力——**主题活动（派对 / 生日会 / 品鉴会）工具链**：

```
query-party-city → query-party-store → query-partystore-date
    → query-partystore-session → party-order-create
```

这组能力对应的是麦当劳真实的**高毛利线下场景**，但拿到工具列表的人往往只把它当「查个场次」。
本项目的做法：**用项目管理的方法论，把一场派对当项目交付。**

| 别人做的 | 本项目做的 |
| --- | --- |
| 帮你点一顿 | 帮你办一场（12 人 / 3 小时 / 有流程有风险预案） |
| 推荐套餐 | 按人数与年龄层算配比，输出备货份数 |
| 算总价 | 券组合**枚举求全局最优** + 积分抵扣 + 三档真实重算 |
| 对话给建议 | 输出 WBS、分钟级 Runbook、风险登记表 |
| 调 MCP 拿数据 | MCP 拿数 + 本地确定性脚本算决策，**零幻觉** |

---

## 🎬 它能做什么

### 1. 需求 Intake
一次最多问 4 个问题：城市 / 人数 / 预算 / 日期偏好。能从原话提取的绝不问。

### 2. 可行性侦察（真实 MCP 只读）
按 `now-time-info → query-party-city → query-party-store → query-partystore-date
→ query-partystore-session → campaign-calendar → query-my-account/query-my-coupons`
顺序侦察，**每步真实结果都给用户看**。

> **优雅降级**：若某城市/门店尚未开放派对预约，明确告知并自动切换到
> `query-nearby-stores + query-meals + calculate-price` 的团餐路线，绝不假装成功。

### 3. 方案精算（确定性脚本）
```bash
python scripts/party_planner.py \
  --people 12 --age kid --scene birthday --budget 800 \
  --menu menu.json --coupons coupons.json --points 3000 --points-value 30
```

真实输出片段：

```
【备货配比】
  主食  系数 0.75   理论 9.0    → 建议备货 9
  小食  系数 1.2    理论 14.4   → 建议备货 15
  甜品  系数 0.75   理论 9.0    → 建议备货 9
  饮品  系数 1.0    理论 12.0   → 建议备货 12

【报价】
  原价小计   ¥405.0
  券抵扣     -¥28.0  (枚举求全局最优)
  积分抵扣   -¥30.0
  实付       ¥347.0   人均 ¥28.92   预算占用 43.4%

【三档方案】
  经济  备货 {主食9, 小食12, 甜品5, 饮品12}  实付 ¥289.0  人均 ¥24.08
  推荐  备货 {主食9, 小食15, 甜品9, 饮品12}  实付 ¥347.0  人均 ¥28.92
  豪华  备货 {主食10, 小食19, 甜品11, 饮品14} 实付 ¥427.0  人均 ¥35.58
```

三档不是乘数缩放，**每一档都重新走一遍选品 + 券 + 积分的完整计价**。

### 4. 现场 Runbook
```bash
python scripts/runbook.py --start 14:00 --people 12 --age kid --scene birthday
```
输出分钟级时间轴、物料清单、风险登记表（含触发条件与应对动作）、WBS 分解。

### 5. 下单（必须确认）
展示完整确认单 → 等你明确说「下单」→ 才调 `party-order-create`。
返回支付链接后提醒：**支付需你本人在链接或麦当劳 App 完成，代理不代付。**

---

## 🚀 快速开始

### 1. 申请麦当劳 MCP Token
前往 [https://open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 手机号登录 → 右上角「控制台」→「激活」→ 复制 Token。

### 2. 配置 MCP 连接器

复制 [`mcp-config.example.json`](./mcp-config.example.json)，把占位符替换成你的 Token：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

- **WorkBuddy**：左侧边栏【专家·技能·连接器】→【连接器】→ 右上角【自定义连接器】→【配置 MCP】
- 其他客户端（Cursor / Cherry Studio / Trae / VSCode）配置方式相同，见[官方接入指南](https://github.com/M-China/mcd-mcp-server)

### 3. 安装本 Skill

**WorkBuddy 用户**（推荐）：
```bash
# 方式一：克隆到用户技能目录
git clone https://github.com/aa7134568-oss/mcd-party-director.git \
  ~/.workbuddy/skills/mcd-party-director

# 方式二：直接把 SKILL.md 所在目录放进技能目录
```

**其他 MCP 客户端**：把 `SKILL.md` 的内容作为 System Prompt 或 Skill 文件加载即可，脚本可独立运行。

### 4. 连通性自检
```bash
export MCD_MCP_TOKEN='你的Token'
python scripts/mcp_client.py tools      # 应列出全部工具
python scripts/mcp_client.py recon --out recon.json   # 派对可行性侦察
```

### 5. 直接开聊
> 「给孩子办个生日会，12 个小朋友，预算 800，周末下午」

---

## 📁 项目结构

```
mcd-party-director/
├── SKILL.md                    # Skill 主入口（工作流 / 红线 / 输出风格）
├── README.md                   # 本文件
├── CONTEST_DECLARATION.md      # 参赛声明
├── MCP_INTEGRATION.md          # MCP 接入与调用链路说明
├── mcp-config.example.json     # 脱敏配置（仅占位符）
├── workbuddy.md                # WorkBuddy 开发上下文（专项奖励）
├── assets/
│   └── banner.png / banner.svg # 项目封面（矢量源 + 位图）
├── scripts/
│   ├── party_planner.py        # 人数配比 / 券组合枚举 / 三档方案
│   ├── runbook.py              # 时间轴 / 物料 / 风险 / WBS
│   └── mcp_client.py           # MCP Streamable HTTP 客户端
├── references/
│   └── mcp_tools.md            # 官方 33 个工具速查
└── examples/
    ├── menu.sample.json        # 菜单结构示例
    ├── coupons.sample.json     # 券结构示例
    └── sample_session.md       # 完整对话样例
```

---

## 🎯 目标用户

- **家长**：想给孩子办麦当劳生日会，但不知道怎么预约、多少钱、现场怎么控场
- **行政 / HR**：需要组织 10-30 人团建或品鉴会，要有预算和流程能交差
- **年轻人**：朋友局、社团活动，想省心又想算清楚钱
- **开发者**：想看麦当劳 MCP 的 party 工具链能怎么被真正用起来

---

## 🛡️ 安全与合规

- 未经明确确认，**绝不创建任何订单**（`create-order` / `party-order-create`）
- Token 只从环境变量读取，**不出现在命令行参数、日志、输出或任何文件中**
- 支付由用户本人完成，代理不代付
- 手机号展示脱敏（`152****6666`）
- 涉及儿童活动时必须显式提示家长陪同与过敏原确认

---

## ⚠️ 免责声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
餐品信息、价格、场次余位、门店供应状态均以麦当劳官方渠道的实时结果为准。
项目的配比模型与预算比例为通用经验参数，仅供参考。

---

## 📄 License

MIT · 详见 [LICENSE](./LICENSE)

© 2026 McDonald's. All Rights Reserved. 麦当劳名称与商标归其权利人所有，本项目不构成任何商标授权。
