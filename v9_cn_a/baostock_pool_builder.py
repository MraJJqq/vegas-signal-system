"""Build a recommended 2,000-stock A-share universe ranked by recent Baostock turnover.
Initial pool build is triggered by the workflow; later refreshes can be run manually.
"""
from __future__ import annotations
import json, os, re, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import baostock as bs

TZ=ZoneInfo("Asia/Shanghai")
OUT=Path(os.environ.get("V9_CN_A_POOL_PATH","v9_cn_a/baostock-stock-pool.json"))
TARGET=2000
LOOKBACK=35
PAUSE=float(os.environ.get("BAOSTOCK_REQUEST_PAUSE","0.08"))

def main():
    today=datetime.now(TZ).date()
    start=(today-timedelta(days=LOOKBACK)).isoformat()
    end=today.isoformat()
    login=bs.login()
    if login.error_code!="0":
        raise RuntimeError(f"Baostock login failed: {login.error_code} {login.error_msg}")
    ranked=[]; errors=0
    try:
        rs=bs.query_all_stock(end)
        if rs.error_code!="0":
            raise RuntimeError(f"query_all_stock failed: {rs.error_code} {rs.error_msg}")
        universe=[]
        while rs.next():
            row=dict(zip(rs.fields,rs.get_row_data()))
            code=row.get("code","")
            name=row.get("code_name","")
            # Ordinary Shanghai/Shenzhen A-shares only; exclude B-shares, indices and Beijing listings.
            if not re.fullmatch(r"(sh|sz)\.(?:600|601|603|605|688|000|001|002|003|300|301)\d{3}",code):
                continue
            if row.get("tradeStatus")!="1" or not name.strip():
                continue
            universe.append((code,name.strip()))
        print(f"Eligible active A-shares: {len(universe)}")
        for i,(code,name) in enumerate(universe,1):
            try:
                hist=bs.query_history_k_data_plus(code,"date,code,close,volume,amount",start_date=start,end_date=end,frequency="d",adjustflag="3")
                if hist.error_code!="0":
                    raise RuntimeError(f"{hist.error_code}: {hist.error_msg}")
                amounts=[]; valid_days=0
                while hist.next():
                    row=dict(zip(hist.fields,hist.get_row_data()))
                    try:
                        amount=float(row["amount"] or 0)
                        close=float(row["close"] or 0)
                        if close>0 and amount>0:
                            amounts.append(amount); valid_days+=1
                    except (ValueError,TypeError):
                        continue
                if valid_days>=5:
                    # Favor recent turnover and require sufficient observations; avoid one-day spikes.
                    avg=sum(amounts[-20:])/len(amounts[-20:])
                    ranked.append({"code":code,"name":name,"avg_daily_amount":round(avg,2),"valid_days":valid_days})
            except Exception as exc:
                errors+=1
                if errors<=20: print(f"SKIP {code} {name}: {exc}")
            if i%100==0: print(f"[{i}/{len(universe)}] ranked={len(ranked)} errors={errors}")
            time.sleep(PAUSE)
    finally:
        bs.logout()
    ranked.sort(key=lambda x:(x["avg_daily_amount"],x["valid_days"]),reverse=True)
    selected=ranked[:TARGET]
    if len(selected)<TARGET:
        raise RuntimeError(f"Only {len(selected)} valid stocks; refusing to write a pool smaller than {TARGET}.")
    result={
      "provider":"Baostock","generated_at":datetime.now(TZ).isoformat(),
      "ranking":"descending average daily traded amount over recent available daily bars",
      "lookback_start":start,"lookback_end":end,"eligible_active_a_shares":len(universe),
      "ranked_with_valid_data":len(ranked),"selected_count":len(selected),
      "failed_or_insufficient_data":errors,"stocks":[{"code":x["code"],"name":x["name"],"avg_daily_amount":x["avg_daily_amount"]} for x in selected]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="stocks"},ensure_ascii=False,indent=2))
    print(f"Saved {len(selected)} stocks to {OUT}")
    return 0
if __name__=="__main__": raise SystemExit(main())
