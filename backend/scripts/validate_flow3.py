# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""P2 合规验收：HACCP/CCP 判定、杀菌时间-温度告警、CIP、CoA 放行锁死、异常看板。

用法：cd backend && PYTHONPATH=. venv/bin/python scripts/validate_flow3.py
进程内 TestClient，不监听端口、不起常驻服务。
"""
import time
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app

STAMP = time.strftime("%H%M%S")


def j(resp):
    return resp.json()


with TestClient(app) as c:
    # A2/A8 后业务端点需鉴权；种子已建 admin/admin123
    login = j(c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}))
    if login.get("code") != 200:
        raise SystemExit(f"登录失败，无法继续验收: {login}")
    c.headers["Authorization"] = f"Bearer {login['data']['access_token']}"

    uoms = {u["code"]: u for u in j(c.get("/api/v1/uoms"))["data"]}
    mats = {m["code"]: m for m in j(c.get("/api/v1/materials"))["data"]}
    wh_rm = j(c.get("/api/v1/warehouses"))["data"][0]["id"]

    print("===== 1. HACCP 关键控制点（种子）=====")
    ccps = {x["code"]: x for x in j(c.get("/api/v1/ccps"))["data"]}
    for code, x in ccps.items():
        print(f"  {code} {x['name']} 限值[{x['limit_min']}, {x['limit_max']}] critical={x['critical']}")
    ccp01 = ccps["CCP-01"]["id"]

    print("===== 2. 杀菌时间-温度记录 + 越限告警 =====")
    r = j(c.post("/api/v1/temp-logs", json={"ccp_id": ccp01, "temp_c": "90", "stage": "hold", "station": "杀菌罐-1"}))
    print(f"  90℃ : in_range={r['data']['in_range']} alert={r['data']['alert_raised']}")
    r = j(c.post("/api/v1/temp-logs", json={"ccp_id": ccp01, "temp_c": "80.5", "stage": "hold", "station": "杀菌罐-1"}))
    print(f"  80.5℃(越下限) : in_range={r['data']['in_range']} alert={r['data']['alert_raised']}")
    r = j(c.post("/api/v1/temp-logs", json={"ccp_id": ccp01, "temp_c": "97.2", "stage": "heat", "station": "杀菌罐-1"}))
    print(f"  97.2℃(越上限) : in_range={r['data']['in_range']} alert={r['data']['alert_raised']}")
    devs = j(c.get("/api/v1/ccp-records", params={"ccp_id": ccp01, "status": "deviation"}))["data"]
    print(f"  自动生成的 CCP 偏差记录数 : {len(devs)}")

    print("===== 3. CCP 监控记录（人工判定）=====")
    r = j(c.post("/api/v1/ccp-records", json={"ccp_id": ccp01, "measured_value": "92"}))
    print(f"  92℃ : status={r['data']['status']}")
    r = j(c.post("/api/v1/ccp-records", json={"ccp_id": ccp01, "measured_value": "78"}))
    print(f"  78℃ : status={r['data']['status']} note={r['data']['deviation_note']}")

    print("===== 4. CIP 清洗记录 =====")
    t0 = datetime.now()
    r = j(c.post("/api/v1/cip-logs", json={
        "station": "杀菌罐-1", "cip_type": "tank",
        "start_at": t0.isoformat(), "end_at": (t0 + timedelta(minutes=45)).isoformat(),
        "caustic_conc_pct": "2.0", "caustic_temp_c": "80", "final_rinse_ph": "7.2", "rinse_conductivity": "12",
    }))
    print(f"  合格 CIP : result={r['data']['result']} duration={r['data']['duration_min']}min")
    r = j(c.post("/api/v1/cip-logs", json={
        "station": "杀菌罐-1", "cip_type": "tank",
        "start_at": t0.isoformat(), "end_at": (t0 + timedelta(minutes=20)).isoformat(),
        "final_rinse_ph": "9.5", "rinse_conductivity": "58",
    }))
    print(f"  不合格 CIP : result={r['data']['result']}")

    print("===== 5. CoA 放行 + 批次锁死 =====")
    sugar = mats["RM-SUGAR"]["id"]

    def new_lot(tag):
        return j(c.post("/api/v1/stock/lots", json={
            "warehouse_id": wh_rm, "material_id": sugar, "lot_no": f"COA{STAMP}{tag}",
            "qty": "100", "uom_id": uoms["KG"]["id"], "status": "received",
        }))["data"]

    lot1 = new_lot("A")
    coa1 = j(c.post("/api/v1/coa", json={
        "material_id": sugar, "lot_id": lot1["id"], "direction": "incoming",
        "items": [{"name": "水分", "spec": "<=0.5%", "value": "0.2%", "result": "pass"}],
    }))["data"]
    print(f"  建检验单 : {coa1['coa_no']} result={coa1['result']} lot_status_before={lot1['status']}")
    d = j(c.post(f"/api/v1/coa/{coa1['id']}/decide", json={"result": "pass", "released_by": 1}))["data"]
    print(f"  放行 : result={d['result']} locked={d['locked']} lot_status={d['lot_status']}")
    lot_after = next(l for l in j(c.get("/api/v1/stock/lots", params={"material_id": sugar}))["data"] if l["id"] == lot1["id"])
    print(f"  库存批状态 : {lot_after['status']}")
    r = j(c.post(f"/api/v1/coa/{coa1['id']}/decide", json={"result": "fail"}))
    print(f"  重复判定 : code={r['code']} msg={r['msg']}")
    r = j(c.post("/api/v1/coa", json={"material_id": sugar, "lot_id": lot1["id"]}))
    print(f"  已放行批再建检验单 : code={r['code']} msg={r['msg']}")

    lot2 = new_lot("B")
    coa2 = j(c.post("/api/v1/coa", json={"material_id": sugar, "lot_id": lot2["id"]}))["data"]
    d = j(c.post(f"/api/v1/coa/{coa2['id']}/decide", json={"result": "fail", "released_by": 1}))["data"]
    print(f"  不合格放行 : result={d['result']} locked={d['locked']} lot_status={d['lot_status']}")

    lot3 = new_lot("C")
    coa3 = j(c.post("/api/v1/coa", json={"material_id": sugar, "lot_id": lot3["id"]}))["data"]
    d = j(c.post(f"/api/v1/coa/{coa3['id']}/decide", json={"result": "hold"}))["data"]
    print(f"  暂扣(hold) : result={d['result']} locked={d['locked']} lot_status={d['lot_status']}")
    d = j(c.post(f"/api/v1/coa/{coa3['id']}/decide", json={"result": "pass", "released_by": 1}))["data"]
    print(f"  复判放行 : result={d['result']} locked={d['locked']} lot_status={d['lot_status']}")

    print("===== 6. 合规异常看板 =====")
    a = j(c.get("/api/v1/compliance/alerts"))["data"]
    print(f"  CCP 偏差={len(a['ccp_deviations'])} 温度越限={len(a['temp_out_of_range'])} "
          f"CIP 不合格={len(a['cip_failed'])} CoA 不合格={len(a['coa_failed'])} 合计={a['total']}")

    print("\n>>> P2 合规验收完成")