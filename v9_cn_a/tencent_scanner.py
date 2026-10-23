"""Independent Tencent-powered VEGAS V9 A-share scanner."""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any
from vegas_signals_cn import detect_formal_signals

TZ=timezone(timedelta(hours=8)); STATE_PATH=os.environ.get('V9_CN_A_STATE_PATH','v9_cn_a/.signal-state.json'); REPORT_PATH=os.environ.get('V9_CN_A_REPORT_PATH','v9_cn_a/scan-report.json')
# 50 representative liquid names; validated per run, invalid/unavailable data is excluded.
POOL=[('sh600036','招商银行'),('sh600519','贵州茅台'),('sh601318','中国平安'),('sh600030','中信证券'),('sh601166','兴业银行'),('sh600900','长江电力'),('sh600276','恒瑞医药'),('sh601888','中国中免'),('sh600887','伊利股份'),('sh600809','山西汾酒'),('sh601012','隆基绿能'),('sh600438','通威股份'),('sh601668','中国建筑'),('sh601398','工商银行'),('sh601288','农业银行'),('sh601988','中国银行'),('sh601939','建设银行'),('sh600000','浦发银行'),('sh600016','民生银行'),('sh601857','中国石油'),('sh600028','中国石化'),('sh600104','上汽集团'),('sh601766','中国中车'),('sh601601','中国太保'),('sh600050','中国联通'),('sz000001','平安银行'),('sz000333','美的集团'),('sz000651','格力电器'),('sz000858','五粮液'),('sz002415','海康威视'),('sz002594','比亚迪'),('sz000725','京东方A'),('sz002475','立讯精密'),('sz300750','宁德时代'),('sz300059','东方财富'),('sz300124','汇川技术'),('sz300760','迈瑞医疗'),('sz300015','爱尔眼科'),('sz300274','阳光电源'),('sz002714','牧原股份'),('sz002230','科大讯飞'),('sz002371','北方华创'),('sh688981','中芯国际'),('sh688041','海光信息'),('sh688111','金山办公'),('sh688008','澜起科技'),('sh688012','中微公司'),('sh688036','传音控股'),('sz300502','新易盛'),('sz300308','中际旭创')]

def fetch(code:str)->list[dict[str,Any]]:
    # Tencent mirrors differ in DNS reachability across hosted runners; try both.
    params=urllib.parse.urlencode({'param':f'{code},m60,,800'})
    errors=[]
    payload=None
    for host in ('ifzq.gtimg.cn','web.ifzq.gtimg.cn'):
        url=f'https://{host}/appstock/app/kline/mkline?{params}'
        req=urllib.request.Request(url,headers={
            'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
            'Referer':'https://gu.qq.com/',
            'Accept':'application/json,text/plain,*/*',
            'Connection':'close',
        })
        try:
            with urllib.request.urlopen(req,timeout=20) as r:
                raw=r.read().decode('utf-8','replace')
            candidate=json.loads(raw)
            if not isinstance(candidate,dict) or not isinstance(candidate.get('data'),dict):
                raise ValueError(f'Unexpected Tencent response from {host}')
            payload=candidate
            break
        except Exception as e:
            errors.append(f'{host}: {type(e).__name__}: {e}')
    if payload is None:
        raise RuntimeError('Tencent endpoints unavailable; '+' | '.join(errors))
    stock=(payload.get('data') or {}).get(code) or {}
    rows=stock.get('m60') or (stock.get('data') or {}).get('m60') or []
    out=[]
    def parse_time(value:Any)->int:
        # Tencent has returned both formatted dates and compact numeric timestamps.
        if isinstance(value,(int,float)) or (isinstance(value,str) and value.strip().isdigit() and len(value.strip())>=10):
            n=int(value)
            if n>10**12: return n
            if n>10**9: return n*1000
        s=str(value).strip()
        for fmt,nchars in (('%Y-%m-%d %H:%M:%S',19),('%Y-%m-%d %H:%M',16),('%Y/%m/%d %H:%M',16),('%Y-%m-%d',10),('%Y%m%d%H%M',12),('%Y%m%d',8)):
            try: return int(datetime.strptime(s[:nchars],fmt).replace(tzinfo=TZ).timestamp()*1000)
            except ValueError: pass
        raise ValueError(f'Unsupported Tencent candle timestamp: {s[:50]!r}')

    def number(value:Any)->float:
        # Some Tencent responses encode numeric fields as strings with whitespace.
        return float(str(value).strip().replace(',',''))

    for row in rows:
        try:
            if isinstance(row,dict):
                date=row.get('datetime',row.get('date',row.get('time')))
                o=number(row.get('open')); cl=number(row.get('close'))
                hi=number(row.get('high')); lo=number(row.get('low'))
                vol=number(row.get('volume',0))
            elif isinstance(row,(list,tuple)) and len(row)>=5:
                date=row[0]
                # Tencent standard order: time, open, close, high, low, volume, ...
                o,cl,hi,lo=map(number,row[1:5]); vol=number(row[5]) if len(row)>5 else 0
            else:
                continue
            ts=parse_time(date)
            if min(o,cl,hi,lo)<=0 or hi<max(o,cl) or lo>min(o,cl) or lo>hi: continue
            out.append({'timestamp_ms':ts,'open':o,'close':cl,'high':hi,'low':lo,'volume':vol,'closed':ts+3600000<=int(time.time()*1000)})
        except (ValueError,TypeError,IndexError,OverflowError): continue
    out.sort(key=lambda x:x['timestamp_ms'])
    # Do not silently reject a symbol just because Tencent returns fewer bars:
    # the Vegas engine itself determines whether enough history exists.
    if len(out)<1:
        sample=repr(rows[0])[:240] if rows else '<empty>'
        raise ValueError(f'No valid hourly candles returned; raw m60 rows={len(rows)}; first_row={sample}')
    return out

def send_bark(signals:list[dict[str,Any]])->dict[str,Any]:
    key=os.environ.get('BARK_KEY','').strip()
    if not signals:
        return {'status':'skipped','reason':'no_new_signals'}
    if not key:
        return {'status':'skipped','reason':'BARK_KEY_missing'}
    title='VEGAS V9 A股新信号'
    lines=[]
    for s in signals:
        side=str(s.get('filter_side',''))
        symbol=str(s.get('symbol',''))
        name=str(s.get('name',''))
        ts=s.get('candle_timestamp_ms')
        when=datetime.fromtimestamp(ts/1000,tz=TZ).strftime('%m-%d %H:%M') if isinstance(ts,(int,float)) else ''
        lines.append(f"{name} {symbol} | {side} | {when}")
    body='\n'.join(lines)
    url='https://api.day.app/'+urllib.parse.quote(key,safe='')+'/'+urllib.parse.quote(title,safe='')+'/'+urllib.parse.quote(body,safe='')
    req=urllib.request.Request(url,headers={'User-Agent':'VEGAS-V9-CN-A/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=15) as resp:
            payload=resp.read().decode('utf-8','replace')
            if resp.status < 200 or resp.status >= 300:
                raise RuntimeError(f'Bark HTTP {resp.status}: {payload[:200]}')
        try: parsed=json.loads(payload)
        except json.JSONDecodeError: parsed={}
        if isinstance(parsed,dict) and parsed.get('code') not in (None, 200):
            raise RuntimeError(f'Bark rejected push: {payload[:200]}')
        return {'status':'sent','signals':len(signals)}
    except Exception as e:
        return {'status':'failed','error':f'{type(e).__name__}: {e}'}

def main()->int:
    today=datetime.now(TZ).date().isoformat()
    try:
        with open(STATE_PATH,encoding='utf-8') as f: state=json.load(f)
    except (OSError,json.JSONDecodeError): state={}
    daily=state.get('__daily_formal_signals__',{})
    if daily.get('date')!=today: daily={'date':today,'signals':[]}
    bykey={(s.get('symbol'),s.get('candle_timestamp_ms'),s.get('filter_side')):s for s in daily.get('signals',[]) if isinstance(s,dict)}
    report={'started_at_utc':datetime.now(timezone.utc).isoformat(),'source':'Tencent public A-share hourly K-line','timeframe':'1H','pool_size':len(POOL),'symbols_ok':0,'symbols_excluded':[],'results':[],'new_signals':[],'signals':[]}
    for code,name in POOL:
        try:
            candles=fetch(code); symbol=code.upper(); signals=detect_formal_signals(symbol,candles,state.setdefault(symbol,{}))
            for s in signals:
                if datetime.fromtimestamp(s['candle_timestamp_ms']/1000,tz=TZ).date().isoformat()==today:
                    s['name']=name; bykey[(s['symbol'],s['candle_timestamp_ms'],s['filter_side'])]=s; report['new_signals'].append(s)
            report['symbols_ok']+=1; report['results'].append({'code':code,'name':name,'data_available':True,'candles':len(candles),'latest_closed_candle_ms':max((c['timestamp_ms'] for c in candles if c['closed']),default=None)})
        except Exception as e:
            report['symbols_excluded'].append({'code':code,'name':name,'reason':str(e)}); report['results'].append({'code':code,'name':name,'data_available':False,'error':str(e)})
    report['signals']=list(bykey.values()); state['__daily_formal_signals__']={'date':today,'signals':report['signals']}
    os.makedirs(os.path.dirname(STATE_PATH),exist_ok=True); tmp=STATE_PATH+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f: json.dump(state,f,ensure_ascii=False,indent=2)
    os.replace(tmp,STATE_PATH); os.makedirs(os.path.dirname(REPORT_PATH),exist_ok=True)
    report['bark_notification']=send_bark(report['new_signals'])
    with open(REPORT_PATH,'w',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'date_beijing':today,'pool_size':len(POOL),'symbols_ok':report['symbols_ok'],'symbols_excluded':len(report['symbols_excluded']),'new_signals':len(report['new_signals']),'daily_signals':len(report['signals']),'bark_notification':report['bark_notification'],'report':REPORT_PATH},ensure_ascii=False,indent=2))
    return 0 if report['symbols_ok'] else 1
if __name__=='__main__': sys.exit(main())
