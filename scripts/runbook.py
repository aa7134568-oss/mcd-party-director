#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-party-director / runbook.py
-------------------------------
生成派对现场 Runbook：分钟级时间轴 + 物料清单 + 风险登记表 + WBS 分解。

纯确定性生成，不依赖网络与 MCP。零第三方依赖，Python 3.9+。
"""

import argparse
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

# --------------------------------------------------------------------------
# 时间轴模板：offset 为相对开场时间的分钟数（负数=开场前）
# --------------------------------------------------------------------------
TIMELINE = {
    "birthday": [
        (-30, "场地确认", "到店核对接待区、座位安排、电源与插座，确认预留区域"),
        (-20, "物料到位", "装饰、横幅、餐具、湿巾、急救小包摆放到位"),
        (-10, "签到准备", "签到表/笔、伴手礼分装、儿童名贴"),
        (0,   "开场迎宾", "主持人开场，家长签到，儿童入座，说明活动流程与安全须知"),
        (10,  "破冰游戏", "按年龄层分组，5-8 人一组，安排第一轮互动"),
        (35,  "上餐", "主食与小食上齐，优先儿童份，确认过敏原"),
        (55,  "主环节", "生日仪式：点蜡烛、唱生日歌、切蛋糕"),
        (75,  "自由社交", "拍照区开放，伴手礼发放"),
        (95,  "收尾清场", "垃圾分类、遗留物品清点、场地还原确认"),
        (110, "复盘交接", "与店方确认无遗留，家长签退"),
    ],
    "team": [
        (-20, "场地确认", "确认预定区域、投影/电源、桌位排布"),
        (-10, "物料到位", "名牌、签到二维码、分组卡"),
        (0,   "开场", "主持人介绍流程与目标，10 分钟破冰"),
        (15,  "分组任务", "按人数分组，发布团队任务"),
        (45,  "上餐", "套餐分发，确认忌口"),
        (70,  "成果展示", "各组 3 分钟汇报"),
        (95,  "自由交流", "自由 networking"),
        (115, "收尾", "场地还原、合影"),
    ],
    "tasting": [
        (-25, "场地确认", "确认试吃台、餐具、饮水与吐骨碟"),
        (-15, "样品准备", "按品类分区摆放，标注编号与名称"),
        (0,   "开场说明", "介绍品鉴规则与评分维度"),
        (10,  "第一轮品鉴", "小食与主食品鉴，填写评分卡"),
        (45,  "第二轮品鉴", "甜品与饮品尝鲜"),
        (70,  "点评汇总", "汇总评分，现场公布结果"),
        (90,  "收尾", "清理试吃台，回收评分卡"),
    ],
    "friends": [
        (-15, "场地确认", "确认座位与拼桌安排"),
        (0,   "集合开场", "点名、确认到场人数"),
        (10,  "上餐", "按清单分发，确认忌口"),
        (40,  "互动环节", "桌游/话题卡/合影"),
        (80,  "加单窗口", "按需追加小食饮品"),
        (110, "收尾", "AA 结算、场地还原"),
    ],
}

MATERIALS = {
    "birthday": ["生日横幅/背景板", "儿童餐具与湿巾", "一次性桌布", "点蜡烛打火机",
                 "切蛋糕刀具", "伴手礼袋 ×人数", "急救小包", "备用垃圾袋",
                 "拍照道具", "签到表与笔"],
    "team": ["桌牌与名牌", "签到二维码", "分组卡", "投影/转接线",
             "计分表", "备用充电宝", "合影背景"],
    "tasting": ["试吃餐具", "吐骨碟", "饮用水", "评分卡与笔",
                "品类编号牌", "湿巾", "垃圾桶"],
    "friends": ["拼桌指示牌", "湿巾纸巾", "共享餐具", "合影道具"],
}

RISKS_BASE = [
    ("到场人数波动", "实际到场少于确认人数 15% 以上",
     "按「备货配比」的 90% 下单，开场后 30 分钟按实际人数加单"),
    ("场次售罄", "目标日期场次已约满",
     "提前 3-7 天锁定；备选 2 个相邻日期与 1 个备选门店"),
    ("过敏与忌口", "宾客对花生/海鲜/乳制品过敏",
     "签到时逐条确认，方案中标注含过敏原餐品，优先单点替代套餐"),
    ("儿童走失/受伤", "儿童离开指定区域或磕碰",
     "设 1 名专职看护，明确集合点；急救小包随身；提前告知店方"),
    ("出餐延误", "高峰时段出餐超 20 分钟",
     "开场前 30 分钟到店预沟通；小食先上垫场，主食后补"),
]

RISKS_EXTRA = {
    "birthday": [("蛋糕与甜品冲突", "自带蛋糕与门店政策冲突",
                  "提前致电门店确认是否允许自带蛋糕及冷藏条件")],
    "team": [("预算审批延迟", "报销流程未在活动前完成",
              "提前 5 个工作日提交预算单，保留电子发票")],
    "tasting": [("样品不足", "品鉴份数少于品鉴人数",
                 "按人数 1.2 倍备样，设置补样窗口")],
    "friends": [("AA 结算纠纷", "分摊金额难以整除",
                 "下单前统一收款，明确人均金额并公示明细")],
}

WBS = {
    "筹备期": ["需求确认（人数/预算/日期/忌口）", "城市与门店调研（MCP 查询）",
               "可预约日期与场次锁定", "菜单拉取与配比精算", "券与积分抵扣测算",
               "物料采购清单确认"],
    "活动当天": ["到场前 30 分钟场地确认", "物料摆放与签到准备",
                 "开场与流程主持", "上餐与加单", "主环节执行", "收尾清场"],
    "收尾": ["费用结算与发票", "照片与反馈回收", "遗留物品清点", "复盘记录归档"],
}


def parse_start(s: str) -> datetime:
    today = datetime.now().date()
    h, m = s.split(":")
    return datetime.combine(today, datetime.min.time()) + timedelta(hours=int(h), minutes=int(m))


def build(args) -> Dict[str, Any]:
    start = parse_start(args.start)
    tl = TIMELINE.get(args.scene, TIMELINE["friends"])

    # 人数规模调整：人数越多，签到与清场时间越长
    extra = 0
    if args.people > 20:
        extra = 10
    elif args.people > 10:
        extra = 5

    rows: List[Dict[str, Any]] = []
    for off, phase, desc in tl:
        if off < 0:
            off -= extra
        t = start + timedelta(minutes=off)
        rows.append({
            "时间": t.strftime("%H:%M"),
            "偏移": f"{off:+d}min",
            "阶段": phase,
            "动作": desc,
            "负责人": args.owner,
        })

    risks = RISKS_BASE + RISKS_EXTRA.get(args.scene, [])
    return {
        "输入": {"开场时间": args.start, "人数": args.people,
                "年龄层": args.age, "场景": args.scene},
        "时间轴": rows,
        "物料清单": MATERIALS.get(args.scene, MATERIALS["friends"]),
        "风险登记表": [{"风险": r, "触发条件": c, "应对动作": a} for r, c, a in risks],
        "WBS": WBS,
        "备注": (f"人数 {args.people} 人，签到与清场已预留额外 {extra} 分钟。"
                 if extra else "按标准时长编排。"),
    }


def render(d: Dict[str, Any]) -> str:
    L = []
    i = d["输入"]
    L.append("=" * 62)
    L.append(f"🎬 派对 Runbook  |  {i['开场时间']} 开场 · {i['人数']} 人 · {i['场景']}")
    L.append("=" * 62)

    L.append("\n【时间轴】")
    L.append(f"  {'时间':<7}{'偏移':<9}{'阶段':<12}动作")
    for r in d["时间轴"]:
        L.append(f"  {r['时间']:<7}{r['偏移']:<9}{r['阶段']:<12}{r['动作']}")

    L.append("\n【物料清单】")
    for m in d["物料清单"]:
        L.append(f"  · {m}")

    L.append("\n【风险登记表】")
    for i2, r in enumerate(d["风险登记表"], 1):
        L.append(f"  {i2}. {r['风险']}")
        L.append(f"     触发：{r['触发条件']}")
        L.append(f"     应对：{r['应对动作']}")

    L.append("\n【WBS 分解】")
    for phase, tasks in d["WBS"].items():
        L.append(f"  [{phase}]")
        for t in tasks:
            L.append(f"      - {t}")

    L.append(f"\n  备注：{d['备注']}")
    L.append("\n" + "=" * 62)
    L.append("确认无误我就下单，改动直接说。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="麦麦派对总导演 · Runbook 生成器")
    ap.add_argument("--start", default="14:00", help="开场时间 HH:MM")
    ap.add_argument("--people", type=int, required=True, help="宾客人数")
    ap.add_argument("--age", choices=["kid", "student", "adult", "mixed"], default="mixed")
    ap.add_argument("--scene", choices=list(TIMELINE), default="friends")
    ap.add_argument("--owner", default="待指派", help="负责人占位")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = build(a)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render(d))


if __name__ == "__main__":
    main()
