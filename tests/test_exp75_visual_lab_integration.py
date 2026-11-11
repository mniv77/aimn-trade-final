"""Read-only EXP74/75 Visual Laboratory integration regression test."""
import json
from pathlib import Path

from flask import Flask
from kiss_backtest_routes import register_kiss_backtest_routes


def test_exp75_visual_lab_integration():
    app=Flask(__name__)
    register_kiss_backtest_routes(app)
    client=app.test_client()
    response=client.get("/api/aimn_visual_lab/exp74_75?symbol=NVDA")
    assert response.status_code==200, response.get_data(as_text=True)[:400]
    data=response.get_json()
    assert data["status"]=="success"
    assert data["source"]=="frozen_research_candles"
    static=json.loads(Path("static/aimn_visual_lab/aimn_nvda_candles.json").read_text())
    research=json.loads(Path("kiss/visual_research/aimn_nvda_candles.json").read_text())
    assert len(data["candle_timestamps"])==len(static)==len(research)==4680
    assert all(a["timestamp"]==b["timestamp"]==t
               for a,b,t in zip(static,research,data["candle_timestamps"]))
    for name in ("EXP74","EXP75"):
        trades=data["experiments"][name]["trades"]
        assert len(trades)==45,(name,len(trades))
        assert all(t["entry_time"] in data["candle_timestamps"] and
                   t["exit_time"] in data["candle_timestamps"] for t in trades)
    denied=client.get("/api/aimn_visual_lab/exp74_75?symbol=TSLA")
    assert denied.status_code==400
    print("EXP74/75 Visual Lab read-only route and 4680 candle alignment: OK")


if __name__=="__main__":
    test_exp75_visual_lab_integration()
