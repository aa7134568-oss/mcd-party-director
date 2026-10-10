# MCP 接入说明

本文档说明本项目**实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值**。

---

## 1. 接入的 MCP Server

| 项目 | 值 |
| --- | --- |
| 服务方 | 麦当劳中国（M-China）官方 MCP 服务 |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| 协议版本 | `2025-06-18`（官方说明：仅支持该版本及之前） |
| 限流 | 每 Token 600 次/分钟，超限返回 429 |
| 官方仓库 | https://github.com/M-China/mcd-mcp-server |
| 开放平台 | https://open.mcd.cn/mcp |
| 配置示例 | [`mcp-config.example.json`](./mcp-config.example.json)（仅含占位符，无真实凭据） |

---

## 2. 实际调用的 Tools

本项目共调用麦当劳 MCP 的 **12 个 Tool**，覆盖「时间 → 活动 → 选址 → 排期 → 选品 → 计价 → 权益 → 下单 → 复盘」完整链路。

### 2.1 核心链路：主题活动（本项目重点使用的能力）

| Tool | 在派对流程中的作用 | 何时调用 |
| --- | --- | --- |
| `query-party-city` | 查询主题活动开放的城市列表，判断用户所在城市能否办 | 侦察第一步 |
| `query-party-store` | 查询指定城市下可承办派对的门店 | 城市确认后 |
| `query-partystore-date` | 查询指定门店的可预约日期 | 门店确认后 |
| `query-partystore-session` | 查询指定日期的场次与余位 | 日期确认后 |
| `party-order-create` | 创建主题活动订单 | **仅当用户明确确认后** |

这组工具是麦当劳 MCP 于 2026-07（v1.0.7）新增的能力，对应麦当劳真实的**生日会 / 品鉴会 / 主题活动**线下场景。本项目是围绕这组能力做深度产品化的实现，而非简单罗列。

### 2.2 环境与决策

| Tool | 作用 |
| --- | --- |
| `now-time-info` | 获取当前时间，计算「距活动还有几天」，驱动筹备倒计时 |
| `campaign-calendar` | 查询当月营销活动日历，判断派对能否蹭上营销节点（如限定周边、联名活动） |

### 2.3 选品与计价

| Tool | 作用 |
| --- | --- |
| `query-nearby-stores` | 派对路线不可用时的降级：查询附近门店 |
| `query-meals` | 拉取门店可售菜单，导出为 JSON 供 `party_planner.py` 计算 |
| `query-meal-detail` | 查看套餐组成与默认选项（确认是否含过敏原、能否替换） |
| `calculate-price` | 计算商品金额、配送费、优惠金额与应付总价 |

### 2.4 权益与下单

| Tool | 作用 |
| --- | --- |
| `query-my-account` | 查询积分账户（可用 / 累计 / 冻结 / 即将过期），用于积分抵扣测算 |
| `query-my-coupons` | 查询卡包优惠券，导出为 JSON 供券组合枚举优化 |
| `create-order` | 降级路线（普通团餐）下单 |
| `query-order` | 下单后查询订单状态与配送信息 |
| `query-my-coupons` / `auto-bind-coupons` | 卡包盘点 / 一键领券，在方案阶段把能领的券先领到手 |

> 未在流程中使用的工具（如 `mall-*` 积分商城、`draw-lottery` 抽奖等）不在本项目范围内，
> 故未调用，避免无关权限与无关数据。

---

## 3. 调用流程

### 3.1 主流程（派对路线）

```
用户输入「给孩子办生日会，12人，800块，周末下午」
        │
        ▼
  ┌─────────────────────────────────────────┐
  │ ① now-time-info      拿当前时间         │ ← 只读
  │ ② query-party-city   城市是否开放        │ ← 只读
  │ ③ query-party-store  该城市可承办门店    │ ← 只读
  │ ④ query-partystore-date   可预约日期    │ ← 只读
  │ ⑤ query-partystore-session 场次与余位   │ ← 只读
  │ ⑥ campaign-calendar  能否蹭营销节点      │ ← 只读
  │ ⑦ query-my-account / query-my-coupons   │ ← 只读
  └─────────────────────────────────────────┘
        │  真实数据落盘为 JSON
        ▼
  ┌─────────────────────────────────────────┐
  │ party_planner.py                        │
  │  · 人数×年龄×场景 → 备货配比            │
  │  · 菜单选品（按配比挑最省）             │
  │  · 券组合枚举 → 全局最优抵扣            │
  │  · 积分抵扣 → 实付 / 人均 / 预算占用    │
  │  · 三档方案（每档独立重算）             │
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │ runbook.py                              │
  │  · 分钟级时间轴 · 物料清单               │
  │  · 风险登记表 · WBS 分解                │
  └─────────────────────────────────────────┘
        │
        ▼  展示完整确认单
  ┌─────────────────────────────────────────┐
  │ 用户明确说「下单」                      │  ← 硬闸门
  └─────────────────────────────────────────┘
        │
        ▼
  party-order-create → 返回订单与支付链接（用户自行支付）
        │
        ▼
  query-order  跟踪订单状态
```

### 3.2 降级流程（派对路线不可用）

当 `query-party-city` / `query-party-store` 返回空，或门店尚未开放派对预约时：

```
query-nearby-stores → query-meals → query-meal-detail
    → calculate-price → （确认后）create-order → query-order
```

降级会**明确告知用户**「该门店暂未开放派对预约，改用团餐方案」，不静默失败、不假装成功。

---

## 4. 业务价值

| 维度 | 没有本 Skill | 有本 Skill |
| --- | --- | --- |
| 信息获取 | 用户自己打电话问门店能不能办、哪天有场 | 一次对话拉齐城市/门店/日期/场次/余位 |
| 备货决策 | 拍脑袋点，常出现不够吃或剩一堆 | 按人数 × 年龄 × 场景算配比，给出具体份数 |
| 成本控制 | 不知道券能不能叠加、积分怎么用 | 券组合**枚举求全局最优**，积分一并抵扣 |
| 方案选择 | 只有「点这个」或「点那个」 | 三档方案，每档真实重算，含人均与预算占用 |
| 现场执行 | 到场才想起来没买蜡烛 | Runbook 给到分钟级流程 + 物料清单 |
| 风险应对 | 出事才处理 | 风险登记表预先给出触发条件与应对动作 |
| 对麦当劳 | 派对工具链少人使用 | 把 party 工具链产品化，带动高毛利线下场景 |

**核心业务价值**：把麦当劳 MCP 的「派对工具链」从「能查场次」变成「能交付一场派对」，
同时用确定性脚本承接所有算术，避免 LLM 心算导致的报价错误。

---

## 5. 关键实现细节

### 5.1 券组合为什么用枚举而不是贪心
券数量通常 ≤ 10，枚举 2^n 完全可行，且**保证全局最优**。
约束条件真实反映业务规则：

- `stackable=false` 的券**不可与任何券同用**，且最多用一张
- 券门槛以「原价小计」判断（保守策略）
- 抵扣总额不超过小计

> 开发过程中这里踩过一个坑：最初只限制「不可叠加券最多一张」，
> 导致出现「不可叠加券 + 两张可叠加券」的**非法组合**被判为最优（-¥43）。
> 修正后正确排除，最优解为两张可叠加券（-¥28）。详见 `scripts/party_planner.py`。

### 5.2 价格单位（官方坑点）
- **只有 `calculate-price` 返回的价格是「分」**（无引号整数），展示前需除以 100
- `query-meals` / `query-meal-detail` / `create-order` / `query-order` 及商城订单返回的金额已是「元」字符串，**直接展示，不要再除**
- 积分字段（`points`、`totalPoints` 等）不做金额换算

### 5.3 零幻觉原则
- 未提供菜单时，脚本**只输出备货配比与预算分配比例，绝不编造餐品与价格**
- 所有价格、门店、场次、券、积分均来自 MCP 真实返回
- 算不出来就明确说算不出来

### 5.4 错误处理
| 错误码 | 含义 | 处理 |
| --- | --- | --- |
| 401 | Token 无效/过期 | 提示到控制台重新激活，不重试 |
| 429 | 触发限流（600 次/分钟） | 指数退避重试（1s → 2s），并在脚本内加调用间隔 |

### 5.5 Token 安全
- 只从环境变量 `MCD_MCP_TOKEN` 读取，**绝不作为命令行参数**（避免出现在 `ps` 与 shell history）
- 不写入任何文件、日志、输出
- 仓库中的 `mcp-config.example.json` 仅含占位符

---

## 6. 复现命令

```bash
# 0. 设置 Token（仅环境变量，不落盘）
export MCD_MCP_TOKEN='你的Token'

# 1. 连通性自检
python scripts/mcp_client.py tools

# 2. 派对可行性侦察
python scripts/mcp_client.py recon --out recon.json

# 3. 导出门店菜单
python scripts/mcp_client.py call query-meals \
  --args '{"storeCode":"门店编码"}' --out menu.json

# 4. 导出卡包券
python scripts/mcp_client.py call query-my-coupons --out coupons.json

# 5. 精算
python scripts/party_planner.py --people 12 --age kid --scene birthday \
  --budget 800 --menu menu.json --coupons coupons.json \
  --points 3000 --points-value 30

# 6. 出 Runbook
python scripts/runbook.py --start 14:00 --people 12 --age kid --scene birthday
```

> 第 5 步的 `--points-value` 需按麦当劳官方积分规则提供；不提供时脚本**不做任何抵扣假设**，
> 保持零幻觉。

---

## 7. 参考

- 官方 MCP 仓库：https://github.com/M-China/mcd-mcp-server
- 开放平台：https://open.mcd.cn/mcp
- MCP 服务规则：https://cdn.mcd.cn/cms/pages/MCPServerRules.html
- 工具速查：见 [`references/mcp_tools.md`](./references/mcp_tools.md)
