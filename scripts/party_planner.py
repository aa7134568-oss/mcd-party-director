#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-party-director / party_planner.py
-------------------------------------
派对方案的确定性计算引擎：人数配比 -> 菜单选品 -> 券/积分抵扣优化 -> 三档方案对比。

设计契约（重要）：
  1. 不提供 --menu 时，脚本只输出「份数配比 + 预算分配比例」，绝不编造餐品和价格，
     价格字段留空等待 MCP 真实返回。
  2. 提供 --menu 时，所有价格来自该文件，脚本只做组合与算术，不做预测。
  3. 券组合用枚举法（n <= 16）求最优，保证结果是全局最优而非贪心近似。

零第三方依赖，Python 3.9+ 可直接运行。
"""

import argparse
import json
import sys
from itertools import combinations
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# 1. 人数配比模型
# --------------------------------------------------------------------------
# 系数含义：每 1 位宾客需要的「份数」。1.0 = 每人一份。
# 数据来源：团餐配餐常见经验值 + 儿童食量折减，属可解释的公开经验参数，非 MCP 数据。
AGE_PROFILE = {
    "kid": {          # 3-12 岁
        "main": 0.75, "side": 1.2, "dessert": 0.6, "drink": 1.0,
        "note": "儿童食量约成人 75%，但小食（薯条/麦乐鸡）消耗远高于主食，甜品按 60% 配。"
    },
    "student": {      # 13-22 岁
        "main": 1.0, "side": 1.3, "dessert": 0.7, "drink": 1.1,
        "note": "学生群体小食与饮品需求偏高，主食 1:1 即可。"
    },
    "adult": {        # 23+ 岁
        "main": 1.0, "side": 0.9, "dessert": 0.5, "drink": 1.0,
        "note": "成人主食需求稳定，甜品需求偏低，可按 50% 配。"
    },
    "mixed": {        # 混合年龄
        "main": 0.95, "side": 1.1, "dessert": 0.6, "drink": 1.05,
        "note": "混合人群取加权中位，甜品与主食略降，小食略升。"
    },
}

# 场景调整：在年龄系数基础上再乘一层场景权重
SCENE_WEIGHT = {
    "birthday":  {"dessert": 1.25, "side": 1.0,  "note": "生日场景甜品/蛋糕需求上浮 25%"},
    "team":      {"main": 1.05, "drink": 1.15,  "note": "团建场景主食与饮品需求略高"},
    "tasting":   {"main": 0.6, "side": 1.4, "dessert": 1.1, "note": "品鉴会重小食轻主食"},
    "friends":   {"side": 1.2, "drink": 1.2,   "note": "朋友局小食与饮品上浮"},
}

# 预算分配比例（餐饮 / 装饰 / 伴手礼 / 机动）
BUDGET_SPLIT = {
    "birthday": {"food": 0.62, "decor": 0.15, "gift": 0.15, "buffer": 0.08},
    "team":     {"food": 0.80, "decor": 0.05, "gift": 0.05, "buffer": 0.10},
    "tasting":  {"food": 0.85, "decor": 0.05, "gift": 0.00, "buffer": 0.10},
    "friends":  {"food": 0.78, "decor": 0.07, "gift": 0.05, "buffer": 0.10},
}

# 三档方案的配比缩放因子：对「建议备货」再乘一层，重新走完整计价
VARIANTS = {
    "经济": {"scale": {"main": 1.0, "side": 0.8, "dessert": 0.5, "drink": 1.0},
             "取舍": "主食保底，小食减 20%，甜品减半（改单点或取消）"},
    "推荐": {"scale": {},
             "取舍": "按配比模型满配，券与积分按最优组合抵扣"},
    "豪华": {"scale": {"main": 1.1, "side": 1.3, "dessert": 1.2, "drink": 1.1},
             "取舍": "全品类上浮 10%-30%，追加伴手礼与装饰预算"},
}


def _ceil(x: float) -> int:
    import math
    return math.ceil(x)


CATEGORY_ALIAS = {
    "main":    ["主食", "汉堡", "堡", "卷", "饭", "main"],
    "side":    ["小食", "小吃", "snack", "side", "麦乐鸡", "薯条", "鸡块"],
    "dessert": ["甜品", "甜点", "冰激凌", "冰淇淋", "派", "dessert", "蛋糕"],
    "drink":   ["饮品", "饮料", "drink", "beverage", "可乐", "咖啡", "奶"],
}


def classify(name: str, category: str = "") -> Optional[str]:
    """把餐品归入 main / side / dessert / drink，无法归类返回 None。"""
    blob = f"{category or ''}{name or ''}".lower()
    for key, kws in CATEGORY_ALIAS.items():
        if any(kw.lower() in blob for kw in kws):
            return key
    return None


def compute_portions(people: int, age: str, scene: str) -> Dict[str, Any]:
    """计算各品类应备份数（向上取整，宁可略余不可短缺）。"""
    import math
    prof = AGE_PROFILE.get(age, AGE_PROFILE["mixed"])
    sw = SCENE_WEIGHT.get(scene, {})
    out = {}
    for cat in ("main", "side", "dessert", "drink"):
        base = prof[cat]
        weight = sw.get(cat, 1.0)
        raw = people * base * weight
        out[cat] = {
            "系数": round(base * weight, 3),
            "理论份数": round(raw, 2),
            "建议备货": math.ceil(raw),
        }
    out["_note"] = prof["note"] + (" " + sw.get("note", "") if sw.get("note") else "")
    return out


# --------------------------------------------------------------------------
# 2. 菜单解析
# --------------------------------------------------------------------------
def load_menu(path: str) -> List[Dict[str, Any]]:
    """支持两种结构：
         A: {"items":[{name,price,category}]}
         B: {"categories":[{"name":..,"items":[..]}]}
         C: [ {name,price,category}, ... ]
       也接受 query-meals 原始返回中的 data 结构做尽力解析。
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    items: List[Dict[str, Any]] = []
    node = raw.get("data", raw) if isinstance(raw, dict) else raw

    def walk(obj, cat_hint=""):
        if isinstance(obj, list):
            for x in obj:
                walk(x, cat_hint)
        elif isinstance(obj, dict):
            if "categories" in obj and isinstance(obj["categories"], list):
                for c in obj["categories"]:
                    walk(c.get("items", []), c.get("name", ""))
            elif "items" in obj and isinstance(obj["items"], list):
                walk(obj["items"], obj.get("name", cat_hint))
            elif "name" in obj:
                items.append({
                    "name": obj.get("name", ""),
                    "price": _to_float(obj.get("price", obj.get("amount", obj.get("salePrice")))),
                    "code": obj.get("code", obj.get("mealCode", "")),
                    "category": obj.get("category", cat_hint),
                })

    walk(node)
    return [i for i in items if i["name"]]


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("¥", "").replace("元", "").strip())
    except ValueError:
        return None


# --------------------------------------------------------------------------
# 3. 选品：按目标份数在候选里挑最省钱的（等价时挑最贵的？不，挑最便宜且够用）
# --------------------------------------------------------------------------
def pick_items(items: List[Dict], need: Dict[str, int]) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict]] = {"main": [], "side": [], "dessert": [], "drink": []}
    unclassified = []
    for it in items:
        key = classify(it["name"], it.get("category", ""))
        if key and it.get("price") is not None:
            buckets[key].append(it)
        else:
            unclassified.append(it)

    picked, subtotal, missing = [], 0.0, {}
    for cat, target in need.items():
        cand = sorted(buckets[cat], key=lambda x: x["price"])   # 便宜优先
        got, cost = 0, 0.0
        for c in cand:
            while got < target:
                picked.append({"品类": cat, "名称": c["name"], "单价": c["price"],
                               "数量": 1, "编码": c.get("code", "")})
                cost += c["price"]
                got += 1
            if got >= target:
                break
        if got < target:
            missing[cat] = {"需求": target, "菜单可用": got,
                            "说明": "菜单中该品类可选数量不足，需补充或减少该品类配比"}
        subtotal += cost
    return {"清单": picked, "小计": round(subtotal, 2), "缺口": missing,
            "未分类": [i["name"] for i in unclassified][:10]}


# --------------------------------------------------------------------------
# 4. 券组合优化（枚举，n<=16 保证全局最优）
# --------------------------------------------------------------------------
def optimize_coupons(coupons: List[Dict], subtotal: float) -> Dict[str, Any]:
    usable = []
    for c in coupons:
        val = _to_float(c.get("value", c.get("discount", c.get("amount"))))
        if val is None:
            continue
        thr = _to_float(c.get("minSpend", c.get("threshold", 0))) or 0.0
        usable.append({"name": c.get("name", "券"), "value": val, "min": thr,
                       "stackable": bool(c.get("stackable", True))})

    if not usable:
        return {"选中": [], "抵扣": 0.0, "说明": "无可用券"}

    non_stack = [c for c in usable if not c["stackable"]]
    stack = [c for c in usable if c["stackable"]]

    best = {"combos": [], "save": 0.0}
    n = len(usable)
    if n <= 16:
        for r in range(1, n + 1):
            for combo in combinations(usable, r):
                # 不可叠加券（stackable=false）不可与任何券同用，且最多用一张
                non_stack_in = [x for x in combo if not x["stackable"]]
                if len(non_stack_in) > 1:
                    continue
                if non_stack_in and len(combo) > 1:
                    continue
                total = sum(x["value"] for x in combo)
                # 门槛校验：券门槛以「原价小计」判断（保守）
                if any(subtotal < x["min"] for x in combo):
                    continue
                if total > best["save"]:
                    best = {"combos": list(combo), "save": total}
    else:
        # 超量时退化为「按价值/门槛比」贪心，并明确标注非最优
        ranked = sorted(usable, key=lambda x: -x["value"] / max(x["min"], 1))
        acc = []
        for x in ranked:
            if subtotal >= x["min"] and (x["stackable"] or not any(not y["stackable"] for y in acc)):
                acc.append(x)
        best = {"combos": acc, "save": sum(x["value"] for x in acc), "非最优": True}

    # 抵扣不超过小计
    save = min(best["save"], subtotal)
    return {
        "选中": [{"名称": x["name"], "抵扣": x["value"], "门槛": x["min"]} for x in best["combos"]],
        "抵扣": round(save, 2),
        "枚举规模": n,
        "说明": "枚举求全局最优" if n <= 16 else "券数量过多，退化为贪心（非最优）",
    }


def apply_points(subtotal_after_coupon: float, points: int,
                 points_value: Optional[float]) -> Dict[str, Any]:
    """积分抵扣。points_value 需由用户或 MCP 提供（如不明确则为 None，不做假设）。"""
    if points_value is None:
        return {"可用积分": points, "抵扣": 0.0,
                "说明": "未提供积分抵扣规则（--points-value），不做任何抵扣假设。"}
    used = min(points_value, subtotal_after_coupon)
    return {"可用积分": points, "可抵扣金额": round(points_value, 2),
            "实际抵扣": round(used, 2),
            "说明": "积分抵扣规则以麦当劳官方为准，此处按传入值计算"}


# --------------------------------------------------------------------------
# 5. 主流程
# --------------------------------------------------------------------------
def build_plan(args) -> Dict[str, Any]:
    people = args.people
    portions = compute_portions(people, args.age, args.scene)
    need = {k: v["建议备货"] for k, v in portions.items() if k != "_note"}

    split = BUDGET_SPLIT.get(args.scene, BUDGET_SPLIT["friends"])
    budget = args.budget
    budget_plan = {k: round(budget * v, 2) for k, v in split.items()}

    result: Dict[str, Any] = {
        "输入": {"人数": people, "年龄层": args.age, "场景": args.scene, "预算": budget},
        "备货配比": portions,
        "预算分配": budget_plan,
        "预算分配说明": "餐饮 / 装饰 / 伴手礼 / 机动预留，比例按场景预设",
    }

    if not args.menu:
        result["价格"] = None
        result["状态"] = "仅配比（未提供菜单）"
        result["下一步"] = ("请先用 MCP 的 query-meals 拉取门店菜单，"
                            "存为 JSON 后加 --menu 参数重跑以获得真实报价")
        return result

    items = load_menu(args.menu)
    picked = pick_items(items, need)
    subtotal = picked["小计"]

    coupons = []
    if args.coupons:
        with open(args.coupons, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        coupons = cdata.get("coupons", cdata) if isinstance(cdata, dict) else cdata

    copt = optimize_coupons(coupons, subtotal)
    after_coupon = round(subtotal - copt["抵扣"], 2)
    popt = apply_points(after_coupon, args.points, args.points_value)
    final = round(after_coupon - popt.get("实际抵扣", 0.0), 2)

    result["价格"] = {
        "原价小计": subtotal,
        "券抵扣": copt,
        "积分抵扣": popt,
        "实付": final,
        "人均": round(final / people, 2) if people else None,
        "预算占用": f"{round(final / budget * 100, 1)}%" if budget else None,
        "是否超预算": final > budget,
    }
    result["清单"] = picked["清单"]
    if picked["缺口"]:
        result["缺口告警"] = picked["缺口"]
    if picked["未分类"]:
        result["未归类餐品（前10）"] = picked["未分类"]

    # 三档方案：按不同配比因子重新走一遍「选品 + 券 + 积分」，得到真实报价而非缩放估算
    variants = {}
    for vname, v in VARIANTS.items():
        vneed = {cat: _ceil(people * portions[cat]["系数"] * v["scale"].get(cat, 1.0))
                 for cat in ("main", "side", "dessert", "drink")}
        vpicked = pick_items(items, vneed)
        vsub = vpicked["小计"]
        vcoupon = optimize_coupons(coupons, vsub)
        v_after = round(vsub - vcoupon["抵扣"], 2)
        vp = apply_points(v_after, args.points, args.points_value)
        vfinal = round(v_after - vp.get("实际抵扣", 0.0), 2)
        variants[vname] = {
            "备货": vneed,
            "原价": vsub,
            "券抵扣": vcoupon["抵扣"],
            "积分抵扣": vp.get("实际抵扣", 0.0),
            "实付": vfinal,
            "人均": round(vfinal / people, 2) if people else None,
            "取舍": v["取舍"],
            "是否超预算": vfinal > budget,
        }
    result["三档方案"] = variants
    result["推荐档"] = args.variant if args.variant in variants else "推荐"
    result["状态"] = "完整方案"
    return result


def render(plan: Dict[str, Any]) -> str:
    """人类可读渲染。"""
    L = []
    inp = plan["输入"]
    L.append("=" * 62)
    L.append(f"🍔 麦麦派对方案  |  {inp['人数']} 人 · {inp['年龄层']} · {inp['场景']} · 预算 ¥{inp['预算']}")
    L.append("=" * 62)

    L.append("\n【备货配比】")
    for cat, v in plan["备货配比"].items():
        if cat == "_note":
            continue
        cn = {"main": "主食", "side": "小食", "dessert": "甜品", "drink": "饮品"}[cat]
        L.append(f"  {cn}  系数 {v['系数']:<6} 理论 {v['理论份数']:<6} → 建议备货 {v['建议备货']}")
    L.append(f"  依据：{plan['备货配比']['_note']}")

    L.append("\n【预算分配】")
    cn_map = {"food": "餐饮", "decor": "装饰", "gift": "伴手礼", "buffer": "机动预留"}
    for k, v in plan["预算分配"].items():
        L.append(f"  {cn_map.get(k, k):<6} ¥{v}")

    if plan.get("价格") is None:
        L.append("\n【价格】未提供菜单，不出报价。")
        L.append(f"  下一步：{plan['下一步']}")
        L.append("\n" + "=" * 62)
        return "\n".join(L)

    p = plan["价格"]
    L.append("\n【报价】")
    L.append(f"  原价小计   ¥{p['原价小计']}")
    L.append(f"  券抵扣     -¥{p['券抵扣']['抵扣']}  ({p['券抵扣']['说明']})")
    for c in p["券抵扣"]["选中"]:
        L.append(f"      · {c['名称']}  -¥{c['抵扣']}（满 ¥{c['门槛']}）")
    if p["积分抵扣"].get("实际抵扣"):
        L.append(f"  积分抵扣   -¥{p['积分抵扣']['实际抵扣']}")
    else:
        L.append(f"  积分抵扣   未启用（{p['积分抵扣']['说明']}）")
    L.append(f"  {'─' * 30}")
    L.append(f"  实付       ¥{p['实付']}   人均 ¥{p['人均']}   预算占用 {p['预算占用']}")
    if p["是否超预算"]:
        L.append("  ⚠️ 超出预算，建议下调小食/甜品配比或改选经济档")

    if plan.get("清单"):
        L.append("\n【选品清单】")
        agg: Dict[str, Dict] = {}
        for it in plan["清单"]:
            agg.setdefault(it["名称"], {"数量": 0, "单价": it["单价"], "品类": it["品类"]})
            agg[it["名称"]]["数量"] += 1
        for name, v in agg.items():
            L.append(f"  {v['品类']:<8} {name:<22} ×{v['数量']:<3} @¥{v['单价']}")

    if plan.get("缺口告警"):
        L.append("\n⚠️ 【缺口告警】")
        for k, v in plan["缺口告警"].items():
            L.append(f"  {k}: 需求 {v['需求']}，菜单仅 {v['菜单可用']} — {v['说明']}")

    L.append(f"\n【三档方案】（推荐：{plan.get('推荐档', '推荐')}）")
    for k, v in plan["三档方案"].items():
        flag = " ⚠️超预算" if v["是否超预算"] else ""
        L.append(f"  {k}  备货 {v['备货']}  原价 ¥{v['原价']} → 实付 ¥{v['实付']}"
                 f"  人均 ¥{v['人均']}{flag}")
        L.append(f"       取舍：{v['取舍']}")

    L.append("\n" + "=" * 62)
    L.append("确认无误我就下单，改动直接说。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="麦麦派对总导演 · 方案精算引擎")
    ap.add_argument("--people", type=int, required=True, help="宾客人数")
    ap.add_argument("--age", choices=list(AGE_PROFILE), default="mixed", help="年龄层")
    ap.add_argument("--scene", choices=list(BUDGET_SPLIT), default="friends", help="场景")
    ap.add_argument("--budget", type=float, required=True, help="总预算（元）")
    ap.add_argument("--menu", help="菜单 JSON 路径（来自 query-meals）")
    ap.add_argument("--coupons", help="优惠券 JSON 路径（来自 query-my-coupons）")
    ap.add_argument("--points", type=int, default=0, help="可用积分")
    ap.add_argument("--points-value", type=float, default=None,
                    help="积分可抵扣金额（元）；不传则不假设抵扣规则")
    ap.add_argument("--variant", choices=list(VARIANTS), default="推荐",
                    help="指定推荐档位（默认 推荐）")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    a = ap.parse_args()

    if a.people <= 0:
        sys.exit("人数必须为正整数")
    if a.budget <= 0:
        sys.exit("预算必须为正数")

    plan = build_plan(a)
    print(json.dumps(plan, ensure_ascii=False, indent=2) if a.json else render(plan))


if __name__ == "__main__":
    main()
