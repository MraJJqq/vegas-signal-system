"""Independent Tencent-powered VEGAS V9 A-share scanner."""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any
from vegas_signals_cn import detect_formal_signals

TZ=timezone(timedelta(hours=8)); STATE_PATH=os.environ.get('V9_CN_A_STATE_PATH','v9_cn_a/.signal-state.json'); REPORT_PATH=os.environ.get('V9_CN_A_REPORT_PATH','v9_cn_a/scan-report.json')
# 200 diversified liquid A-share candidates; invalid or unavailable data is excluded each run.
POOL=[('sh600036','招商银行'),('sh600519','贵州茅台'),('sh601318','中国平安'),('sh600030','中信证券'),('sh601166','兴业银行'),('sh600900','长江电力'),('sh600276','恒瑞医药'),('sh601888','中国中免'),('sh600887','伊利股份'),('sh600809','山西汾酒'),('sh601012','隆基绿能'),('sh600438','通威股份'),('sh601668','中国建筑'),('sh601398','工商银行'),('sh601288','农业银行'),('sh601988','中国银行'),('sh601939','建设银行'),('sh600000','浦发银行'),('sh600016','民生银行'),('sh601857','中国石油'),('sh600028','中国石化'),('sh600104','上汽集团'),('sh601766','中国中车'),('sh601601','中国太保'),('sh600050','中国联通'),('sz000001','平安银行'),('sz000333','美的集团'),('sz000651','格力电器'),('sz000858','五粮液'),('sz002415','海康威视'),('sz002594','比亚迪'),('sz000725','京东方A'),('sz002475','立讯精密'),('sz300750','宁德时代'),('sz300059','东方财富'),('sz300124','汇川技术'),('sz300760','迈瑞医疗'),('sz300015','爱尔眼科'),('sz300274','阳光电源'),('sz002714','牧原股份'),('sz002230','科大讯飞'),('sz002371','北方华创'),('sh688981','中芯国际'),('sh688041','海光信息'),('sh688111','金山办公'),('sh688008','澜起科技'),('sh688012','中微公司'),('sh688036','传音控股'),('sz300502','新易盛'),('sz300308','中际旭创'),('sh601899','紫金矿业'),('sh603259','药明康德'),('sh600309','万华化学'),('sh600585','海螺水泥'),('sh601225','陕西煤业'),('sh600989','宝丰能源'),('sh601088','中国神华'),('sh600346','恒力石化'),('sh600031','三一重工'),('sh601100','恒立液压'),('sh601390','中国中铁'),('sh601186','中国铁建'),('sh601800','中国交建'),('sh600019','宝钢股份'),('sh600011','华能国际'),('sh600886','国投电力'),('sh600025','华能水电'),('sh601728','中国电信'),('sh603501','韦尔股份'),('sh603986','兆易创新'),('sh603005','晶方科技'),('sh688396','华润微'),('sh688099','晶晨股份'),('sh688126','沪硅产业'),('sh688009','中国通号'),('sh688200','华峰测控'),('sh688169','石头科技'),('sh688303','大全能源'),('sh688223','晶科能源'),('sh688599','天合光能'),('sh688005','容百科技'),('sh688063','派能科技'),('sh688728','格科微'),('sh688777','中控技术'),('sh603019','中科曙光'),('sh603893','瑞芯微'),('sh603799','华友钴业'),('sh603993','洛阳钼业'),('sh601600','中国铝业'),('sh600362','江西铜业'),('sh600547','山东黄金'),('sh600489','中金黄金'),('sh601669','中国电建'),('sh600406','国电南瑞'),('sh600089','特变电工'),('sh600522','中天科技'),('sh600703','三安光电'),('sh600584','长电科技'),('sh600745','闻泰科技'),('sh600570','恒生电子'),('sh600588','用友网络'),('sh600536','中国软件'),('sh600941','中国移动'),('sh601628','中国人寿'),('sh601336','新华保险'),('sh601995','中金公司'),('sh600999','招商证券'),('sh601688','华泰证券'),('sh601211','国泰海通'),('sh601066','中信建投'),('sh600958','东方证券'),('sh601377','兴业证券'),('sh600018','上港集团'),('sh601006','大秦铁路'),('sh601919','中远海控'),('sh600009','上海机场'),('sh601111','中国国航'),('sh600115','中国东航'),('sh600029','南方航空'),('sh601021','春秋航空'),('sh600233','圆通速递'),('sh603128','华贸物流'),('sh600741','华域汽车'),('sh601238','广汽集团'),('sh601633','长城汽车'),('sh603596','伯特利'),('sh603197','保隆科技'),('sh600660','福耀玻璃'),('sh601058','赛轮轮胎'),('sh600699','均胜电子'),('sh603786','科博达'),('sh600690','海尔智家'),('sh603486','科沃斯'),('sh603833','欧派家居'),('sh603369','今世缘'),('sh600779','水井坊'),('sh603288','海天味业'),('sh600298','安琪酵母'),('sh600597','光明乳业'),('sh600085','同仁堂'),('sh600196','复星医药'),('sh600763','通策医疗'),('sh603658','安图生物'),('sh688271','联影医疗'),('sh688301','奕瑞科技'),('sh688180','君实生物'),('sh688185','康希诺'),('sh688266','泽璟制药'),('sh688390','固德威'),('sz000063','中兴通讯'),('sz000100','TCL科技'),('sz000066','中国长城'),('sz000338','潍柴动力'),('sz000568','泸州老窖'),('sz000596','古井贡酒'),('sz000776','广发证券'),('sz000938','紫光股份'),('sz002027','分众传媒'),('sz002049','紫光国微'),('sz002050','三花智控'),('sz002064','华峰化学'),('sz002142','宁波银行'),('sz002179','中航光电'),('sz002202','金风科技'),('sz002236','大华股份'),('sz002241','歌尔股份'),('sz002304','洋河股份'),('sz002352','顺丰控股'),('sz002460','赣锋锂业'),('sz002466','天齐锂业'),('sz002555','三七互娱'),('sz002607','中公教育'),('sz002920','德赛西威'),('sz002938','鹏鼎控股'),('sz002939','长城证券'),('sz003816','中国广核'),('sz300014','亿纬锂能'),('sz300033','同花顺'),('sz300122','智飞生物'),('sz300136','信维通信'),('sz300347','泰格医药'),('sz300408','三环集团'),('sz300413','芒果超媒'),('sz300433','蓝思科技'),('sz300450','先导智能'),('sz300496','中科创达'),('sz300601','康泰生物'),('sz300661','圣邦股份'),('sz300699','光威复材'),('sz300782','卓胜微'),('sz300896','爱美客'),('sz301269','华大九天'),('sz301308','江波龙'),('sz301358','湖南裕能'),('sz301363','美好医疗'),('sz301391','卡莱特'),('sz301498','乖宝宠物'),('sz301236','软通动力'),('sz002410','广联达'),('sz002709','天赐材料')]

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
