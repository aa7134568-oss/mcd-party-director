# 麦当劳 MCP 工具速查

来源：[M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server) README（截至 v1.0.9）

## 🎯 本项目实际调用（12 个）

| Tool | 用途 | 备注 |
| --- | --- | --- |
| `now-time-info` | 获取当前时间 | 计算筹备倒计时 |
| `query-party-city` | 主题活动可参与城市列表 | **派对链路起点** |
| `query-party-store` | 指定城市下可承办门店 | |
| `query-partystore-date` | 指定门店可预约日期 | |
| `query-partystore-session` | 指定日期可预约场次 | |
| `party-order-create` | 创建主题活动订单 | ⚠️ 需用户确认 |
| `campaign-calendar` | 当月营销活动日历 | 判断是否蹭上节点 |
| `query-nearby-stores` | 查询附近门店 | 降级路线 |
| `query-meals` | 门店可售菜单 | 导出菜单 JSON |
| `query-meal-detail` | 餐品详情（套餐组成/默认选项） | 确认过敏原、可替换项 |
| `calculate-price` | 价格计算 | ⚠️ 返回单位「分」 |
| `query-my-account` | 积分账户 | 可用/累计/冻结/即将过期 |
| `query-my-coupons` | 我的优惠券 | 导出券 JSON |
| `query-order` | 查询订单详情 | 下单后跟踪 |

## 📋 官方全部工具（33 个）

### 营养
| Tool | 说明 |
| --- | --- |
| `list-nutrition-foods` | 餐品营养信息列表（toon 紧凑格式） |

### 地址与门店
| Tool | 说明 |
| --- | --- |
| `delivery-query-addresses` | 可配送地址列表 |
| `delivery-create-address` | 新增配送地址 |
| `delivery-query-stores` | 外送场景可配送门店 |
| `query-nearby-stores` | 附近门店 |

### 团餐
| Tool | 说明 |
| --- | --- |
| `query-meal-assistance` | 查询助餐服务（企业团餐） |

### 券
| Tool | 说明 |
| --- | --- |
| `query-store-coupons` | 当前门店可用券 |
| `available-coupons` | 麦麦省券列表 |
| `auto-bind-coupons` | 麦麦省一键领券 |
| `query-my-coupons` | 我的优惠券 |

### 点餐
| Tool | 说明 |
| --- | --- |
| `query-meals` | 门店可售餐品列表 |
| `query-meal-detail` | 餐品详情 |
| `calculate-price` | 价格计算 |
| `create-order` | 创建订单 |
| `cancel-order` | 取消订单 |
| `query-order` | 订单详情 |
| `order-list` | 历史订单 |

### 活动与积分
| Tool | 说明 |
| --- | --- |
| `campaign-calendar` | 活动日历 |
| `query-my-account` | 我的积分 |
| `now-time-info` | 当前时间 |

### 积分商城
| Tool | 说明 |
| --- | --- |
| `mall-points-products` | 商城商品列表 |
| `mall-product-detail` | 商品详情 |
| `mall-create-order` | 积分兑换下单 |
| `mall-order-list` | 商城订单列表 |
| `mall-order-detail` | 商城订单详情 |

### 积分抽奖
| Tool | 说明 |
| --- | --- |
| `query-lottery-info` | 抽奖活动信息 |
| `draw-lottery` | 执行一次抽奖 |
| `query-my-prizes` | 我的奖品 |

### 主题活动（派对）
| Tool | 说明 |
| --- | --- |
| `query-party-city` | 主题活动城市列表 |
| `query-party-store` | 主题活动门店列表 |
| `query-partystore-date` | 可预约日期 |
| `query-partystore-session` | 可预约场次 |
| `party-order-create` | 主题活动下单 |

---

## ⚠️ 单位坑（必读）

| 来源 | 单位 | 处理 |
| --- | --- | --- |
| `calculate-price` 价格字段 | **分**（无引号整数） | 展示前 ÷ 100 |
| `query-meals` / `query-meal-detail` / `create-order` / `query-order` / 商城订单 | **元**（字符串） | 直接展示，不要再除 |
| `points` / `totalPoints` 等积分字段 | 积分 | 不做金额换算 |

## 🔒 错误码

| code | 原因 | 处理 |
| --- | --- | --- |
| 401 | Token 无效/过期/未提供 | 检查 Authorization 头，重新激活 |
| 429 | 超 600 次/分钟 | 降低频率，指数退避重试 |

## 📌 其他注意

- 仅支持 MCP Version `2025-06-18` 及之前
- 仅中国大陆地区（不含港澳台）
- 不支持更换套餐单品（`query-meal-detail` 定制能力有限）
- 创建订单返回支付链接，支付需用户自行完成
