# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""P1 第二增量验收：UoM 密度换算 / 配方快照免疫 / 合批拆批谱系 / 负库存开关。

用法：cd backend && PYTHONPATH=. venv/bin/python scripts/validate_flow2.py
进程内 TestClient，不监听端口、不起常驻服务。
"""
import time
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models.proc import RecipeComponent

STAMP = time.strftime("%H%M%S")


def j(resp):
    return resp.json()


with TestClient(app) as c:
    uoms = {u["code"]: u for u in j(c.get("/api/v1/uoms"))["data"]}
    mats = {m["code"]: m for m in j(c.get("/api/v1/materials"))["data"]}
    wh_rm = j(c.get("/api/v1/warehouses"))["data"][0]["id"]
    recipe_id = j(c.get("/api/v1/recipes"))["data"][0]["id"]

    print("===== 1. UoM 动态换算（闸3）=====")
    r = j(c.get("/api/v1/uom/convert", params={"qty": "2", "from_uom_id": uoms["KG"]["id"], "to_uom_id": uoms["G"]["id"]}))
    print(f"  2 KG -> G : {r['data']['result']}  mode={r['data']['mode']}")
    r = j(c.get("/api/v1/uom/convert", params={"qty": "5", "from_uom_id": uoms["L"]["id"], "to_uom_id": uoms["KG"]["id"], "material_id": mats["RM-WATER"]["id"]}))
    print(f"  5 L -> KG (纯水, 密度1.0) : {r['data']['result']}  mode={r['data']['mode']}  density={r['data']['density_kg_l']}")
    r = j(c.get("/api/v1/uom/convert", params={"qty": "5", "from_uom_id": uoms["L"]["id"], "to_uom_id": uoms["KG"]["id"], "material_id": mats["RM-SUGAR"]["id"]}))
    print(f"  5 L -> KG (白砂糖, 无密度) : code={r['code']} msg={r['msg']}")

    print("===== 2. 配方快照免疫（闸4）=====")
    batch = j(c.post("/api/v1/batches", json={"recipe_id": recipe_id, "planned_qty": 500, "warehouse_id": wh_rm}))["data"]
    bid = batch["id"]
    print(f"  批次 {batch['batch_no']} status={batch['status']}")
    r = j(c.get(f"/api/v1/batches/{bid}/dispense-plan"))
    print(f"  发布前取应投清单 : code={r['code']} msg={r['msg']}")
    rel = j(c.post(f"/api/v1/batches/{bid}/release"))["data"]
    print(f"  发布 : status={rel['status']} recipe_version={rel['recipe_version']} has_snapshot={rel['has_snapshot']}")
    plan1 = j(c.get(f"/api/v1/batches/{bid}/dispense-plan"))["data"]
    before = [(l["material_id"], str(l["planned_qty"])) for l in plan1["lines"]]
    print(f"  快照应投 : {before}")

    db = SessionLocal()
    try:
        comp = db.scalars(
            select(RecipeComponent).where(RecipeComponent.recipe_id == recipe_id).order_by(RecipeComponent.id.asc())
        ).first()
        old_ratio = comp.ratio_pct
        comp.ratio_pct = Decimal("55")
        db.commit()
        print(f"  >> 已把配方成分 {comp.material_id} 比例从 {old_ratio}% 改为 55%")
    finally:
        db.close()

    plan2 = j(c.get(f"/api/v1/batches/{bid}/dispense-plan"))["data"]
    after = [(l["material_id"], str(l["planned_qty"])) for l in plan2["lines"]]
    print(f"  改配方后应投 : {after}")
    print(f"  >>> 快照免疫: {'通过（未受影响）' if before == after else '失败（被配方改动污染）'}")

    db = SessionLocal()
    try:
        comp = db.scalars(
            select(RecipeComponent).where(RecipeComponent.recipe_id == recipe_id).order_by(RecipeComponent.id.asc())
        ).first()
        comp.ratio_pct = old_ratio
        db.commit()
    finally:
        db.close()

    print("===== 3. 合批 / 拆批 + 谱系（闸2）=====")
    sugar = mats["RM-SUGAR"]["id"]
    ids = []
    for i, qty in enumerate(["100", "250"], start=1):
        lot = j(c.post("/api/v1/stock/lots", json={
            "warehouse_id": wh_rm, "material_id": sugar, "lot_no": f"MGT{STAMP}{i}",
            "qty": qty, "uom_id": uoms["KG"]["id"], "status": "released",
        }))["data"]
        ids.append(lot["id"])
    print(f"  收到两个待合批批次: {ids}")

    mg = j(c.post("/api/v1/stock/lots/merge", json={"lot_ids": ids, "lot_no": f"MGC{STAMP}"}))
    print(f"  合批 : code={mg['code']} child={mg['data']['child_lot_no']} qty={mg['data']['merged_qty']}")
    child = mg["data"]["child_lot_id"]
    g = j(c.get(f"/api/v1/stock/genealogy/{child}"))["data"]
    print(f"  合批谱系 parents : {[(p['lot_id'], p['op_type'], str(p['amount'])) for p in g['parents']]}")

    sp = j(c.post(f"/api/v1/stock/lots/{child}/split", json={"parts": [{"qty": "100"}, {"qty": "150"}]}))
    print(f"  拆批 : code={sp['code']} parent剩余={sp['data']['parent_remaining']} children={[(x['lot_no'], x['qty']) for x in sp['data']['children']]}")
    g2 = j(c.get(f"/api/v1/stock/genealogy/{child}"))["data"]
    print(f"  拆批谱系 children : {[(x['lot_id'], x['op_type'], str(x['amount'])) for x in g2['children']]}")

    print("===== 4. 快照外物料阻断（闸4 强化）=====")
    other = j(c.post("/api/v1/materials", json={
        "code": f"RM-OTHER-{STAMP}", "name": "临时物料", "base_uom_id": uoms["KG"]["id"],
    }))["data"]
    o_lot = j(c.post("/api/v1/stock/lots", json={
        "warehouse_id": wh_rm, "material_id": other["id"], "lot_no": f"OT{STAMP}",
        "qty": "100", "uom_id": uoms["KG"]["id"], "status": "released",
    }))["data"]
    payload = {
        "warehouse_id": wh_rm, "produced_qty": "490", "auto_issue": False,
        "dispenses": [{"material_id": other["id"], "planned_qty": "5", "actual_qty": "5",
                       "uom_id": uoms["KG"]["id"], "lot_id": o_lot["id"]}],
    }
    r = j(c.post(f"/api/v1/batches/{bid}/complete", json=payload))
    print(f"  未放开 : code={r['code']} msg={r['msg']}")
    payload["allow_unplanned"] = True
    r = j(c.post(f"/api/v1/batches/{bid}/complete", json=payload))
    print(f"  放开后 : code={r['code']} msg={r['msg']} produced={r['data']['produced_lot_no'] if r['code'] == 200 else '-'}")

    print("===== 5. 负库存开关（闸5）=====")
    b2 = j(c.post("/api/v1/batches", json={"recipe_id": recipe_id, "planned_qty": 100000, "warehouse_id": wh_rm}))["data"]
    j(c.post(f"/api/v1/batches/{b2['id']}/release"))
    plan = j(c.get(f"/api/v1/batches/{b2['id']}/dispense-plan"))["data"]
    disps = [
        {"component_id": l["component_id"], "material_id": l["material_id"], "planned_qty": str(l["planned_qty"]),
         "actual_qty": str(l["planned_qty"]), "uom_id": l["uom_id"], "tol_pct": str(l["tol_pct"])}
        for l in plan["lines"]
    ]
    body = {"warehouse_id": wh_rm, "produced_qty": "99000", "dispenses": disps}
    settings.ALLOW_NEGATIVE_STOCK = False
    r = j(c.post(f"/api/v1/batches/{b2['id']}/complete", json=body))
    print(f"  严格模式(超量领料) : code={r['code']} msg={r['msg']}")
    settings.ALLOW_NEGATIVE_STOCK = True
    r = j(c.post(f"/api/v1/batches/{b2['id']}/complete", json=body))
    print(f"  放开负库存 : code={r['code']} msg={r['msg']}")
    settings.ALLOW_NEGATIVE_STOCK = False

    print("\n>>> P1 第二增量验收完成")