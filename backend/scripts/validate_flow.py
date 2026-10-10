# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""P1 闭环验收：配方缩放 -> 建批次 -> 产出入账(自动FEFO发料) -> 谱系核对。

用法：cd backend && venv/bin/python scripts/validate_flow.py
使用 TestClient 在进程内跑，不监听端口、不起常驻服务。
"""
from fastapi.testclient import TestClient

from app.main import app


def show(title, data):
    print(f"--- {title} ---")
    print(data)


with TestClient(app) as c:
    show("health", c.get("/api/health").json())

    # 登录拿 token（A2/A8 后业务端点需鉴权；种子已建 admin/admin123）
    login = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    if login.get("code") != 200:
        raise SystemExit(f"登录失败，无法继续验收: {login}")
    H = {"Authorization": f"Bearer {login['data']['access_token']}"}

    recipes = c.get("/api/v1/recipes", headers=H).json()["data"]
    recipe_id = recipes[0]["id"]
    show("recipe", f"id={recipe_id} code={recipes[0]['code']} status={recipes[0]['status']}")

    scale = c.get(f"/api/v1/recipes/{recipe_id}/scale", params={"qty": 1000}, headers=H).json()
    comps = scale["data"]["components"]
    show("scale(1000L)", [(x["material_id"], str(x["planned_qty"])) for x in comps])

    mats = c.get("/api/v1/materials", headers=H).json()["data"]
    whs = c.get("/api/v1/warehouses", headers=H).json()["data"]
    wh_rm = whs[0]["id"]
    sugar = next(m for m in mats if m["code"] == "RM-SUGAR")

    fefo = c.get(
        "/api/v1/stock/fefo-preview",
        params={"warehouse_id": wh_rm, "material_id": sugar["id"], "qty": 100},
        headers=H,
    ).json()
    show("FEFO 预演(白砂糖 100kg)", [(p["lot_no"], str(p["take_qty"])) for p in fefo["data"]["plan"]])

    b = c.post(
        "/api/v1/batches",
        json={"recipe_id": recipe_id, "planned_qty": 1000, "warehouse_id": wh_rm},
        headers=H,
    ).json()
    show("create batch", f"code={b['code']} no={b['data']['batch_no']} status={b['data']['status']}")
    batch_id = b["data"]["id"]

    dispenses = [
        {
            "component_id": x["component_id"],
            "material_id": x["material_id"],
            "planned_qty": str(x["planned_qty"]),
            "actual_qty": str(x["planned_qty"]),
            "uom_id": x["uom_id"],
            "tol_pct": str(x["tol_pct"]),
        }
        for x in comps
    ]

    done = c.post(
        f"/api/v1/batches/{batch_id}/complete",
        json={"warehouse_id": wh_rm, "produced_qty": 980, "dispenses": dispenses, "auto_issue": True},
        headers=H,
    ).json()
    show("complete batch", f"code={done['code']} msg={done['msg']}")

    if done["code"] != 200:
        raise SystemExit("过账失败，终止验收")

    d = done["data"]
    show("consumed", d["consumed"])
    show("deviations", d["deviations"])
    show("produced lot", f"id={d['produced_lot_id']} no={d['produced_lot_no']}")

    g = c.get(f"/api/v1/stock/genealogy/{d['produced_lot_id']}", headers=H).json()
    show("谱系 parents", g["data"]["parents"])

    lots = c.get("/api/v1/stock/lots", params={"material_id": sugar["id"]}, headers=H).json()["data"]
    show("白砂糖批次结余", [(l["lot_no"], str(l["qty"]), l["status"]) for l in lots])

    print("\n>>> P1 闭环验收通过（配方->批次->过账->FEFO->谱系）")