"""Independent Tencent-powered VEGAS V9 A-share scanner."""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any
from vegas_signals_cn import detect_formal_signals

TZ=timezone(timedelta(hours=8)); STATE_PATH=os.environ.get('V9_CN_A_STATE_PATH','v9_cn_a/.signal-state.json'); REPORT_PATH=os.environ.get('V9_CN_A_REPORT_PATH','v9_cn_a/scan-report.json')
# 500 diversified A-share candidates selected from large/mid-cap, index constituents, and liquid sector leaders; runtime data validation excludes unavailable symbols.
POOL=[('sh600036','招商银行'),('sh600519','贵州茅台'),('sh601318','中国平安'),('sh600030','中信证券'),('sh601166','兴业银行'),('sh600900','长江电力'),('sh600276','恒瑞医药'),('sh601888','中国中免'),('sh600887','伊利股份'),('sh600809','山西汾酒'),('sh601012','隆基绿能'),('sh600438','通威股份'),('sh601668','中国建筑'),('sh601398','工商银行'),('sh601288','农业银行'),('sh601988','中国银行'),('sh601939','建设银行'),('sh600000','浦发银行'),('sh600016','民生银行'),('sh601857','中国石油'),('sh600028','中国石化'),('sh600104','上汽集团'),('sh601766','中国中车'),('sh601601','中国太保'),('sh600050','中国联通'),('sz000001','平安银行'),('sz000333','美的集团'),('sz000651','格力电器'),('sz000858','五粮液'),('sz002415','海康威视'),('sz002594','比亚迪'),('sz000725','京东方A'),('sz002475','立讯精密'),('sz300750','宁德时代'),('sz300059','东方财富'),('sz300124','汇川技术'),('sz300760','迈瑞医疗'),('sz300015','爱尔眼科'),('sz300274','阳光电源'),('sz002714','牧原股份'),('sz002230','科大讯飞'),('sz002371','北方华创'),('sh688981','中芯国际'),('sh688041','海光信息'),('sh688111','金山办公'),('sh688008','澜起科技'),('sh688012','中微公司'),('sh688036','传音控股'),('sz300502','新易盛'),('sz300308','中际旭创'),('sh601899','紫金矿业'),('sh603259','药明康德'),('sh600309','万华化学'),('sh600585','海螺水泥'),('sh601225','陕西煤业'),('sh600989','宝丰能源'),('sh601088','中国神华'),('sh600346','恒力石化'),('sh600031','三一重工'),('sh601100','恒立液压'),('sh601390','中国中铁'),('sh601186','中国铁建'),('sh601800','中国交建'),('sh600019','宝钢股份'),('sh600011','华能国际'),('sh600886','国投电力'),('sh600025','华能水电'),('sh601728','中国电信'),('sh603501','韦尔股份'),('sh603986','兆易创新'),('sh603005','晶方科技'),('sh688396','华润微'),('sh688099','晶晨股份'),('sh688126','沪硅产业'),('sh688009','中国通号'),('sh688200','华峰测控'),('sh688169','石头科技'),('sh688303','大全能源'),('sh688223','晶科能源'),('sh688599','天合光能'),('sh688005','容百科技'),('sh688063','派能科技'),('sh688728','格科微'),('sh688777','中控技术'),('sh603019','中科曙光'),('sh603893','瑞芯微'),('sh603799','华友钴业'),('sh603993','洛阳钼业'),('sh601600','中国铝业'),('sh600362','江西铜业'),('sh600547','山东黄金'),('sh600489','中金黄金'),('sh601669','中国电建'),('sh600406','国电南瑞'),('sh600089','特变电工'),('sh600522','中天科技'),('sh600703','三安光电'),('sh600584','长电科技'),('sh600745','闻泰科技'),('sh600570','恒生电子'),('sh600588','用友网络'),('sh600536','中国软件'),('sh600941','中国移动'),('sh601628','中国人寿'),('sh601336','新华保险'),('sh601995','中金公司'),('sh600999','招商证券'),('sh601688','华泰证券'),('sh601211','国泰海通'),('sh601066','中信建投'),('sh600958','东方证券'),('sh601377','兴业证券'),('sh600018','上港集团'),('sh601006','大秦铁路'),('sh601919','中远海控'),('sh600009','上海机场'),('sh601111','中国国航'),('sh600115','中国东航'),('sh600029','南方航空'),('sh601021','春秋航空'),('sh600233','圆通速递'),('sh603128','华贸物流'),('sh600741','华域汽车'),('sh601238','广汽集团'),('sh601633','长城汽车'),('sh603596','伯特利'),('sh603197','保隆科技'),('sh600660','福耀玻璃'),('sh601058','赛轮轮胎'),('sh600699','均胜电子'),('sh603786','科博达'),('sh600690','海尔智家'),('sh603486','科沃斯'),('sh603833','欧派家居'),('sh603369','今世缘'),('sh600779','水井坊'),('sh603288','海天味业'),('sh600298','安琪酵母'),('sh600597','光明乳业'),('sh600085','同仁堂'),('sh600196','复星医药'),('sh600763','通策医疗'),('sh603658','安图生物'),('sh688271','联影医疗'),('sh688301','奕瑞科技'),('sh688180','君实生物'),('sh688185','康希诺'),('sh688266','泽璟制药'),('sh688390','固德威'),('sz000063','中兴通讯'),('sz000100','TCL科技'),('sz000066','中国长城'),('sz000338','潍柴动力'),('sz000568','泸州老窖'),('sz000596','古井贡酒'),('sz000776','广发证券'),('sz000938','紫光股份'),('sz002027','分众传媒'),('sz002049','紫光国微'),('sz002050','三花智控'),('sz002064','华峰化学'),('sz002142','宁波银行'),('sz002179','中航光电'),('sz002202','金风科技'),('sz002236','大华股份'),('sz002241','歌尔股份'),('sz002304','洋河股份'),('sz002352','顺丰控股'),('sz002460','赣锋锂业'),('sz002466','天齐锂业'),('sz002555','三七互娱'),('sz002607','中公教育'),('sz002920','德赛西威'),('sz002938','鹏鼎控股'),('sz002939','长城证券'),('sz003816','中国广核'),('sz300014','亿纬锂能'),('sz300033','同花顺'),('sz300122','智飞生物'),('sz300136','信维通信'),('sz300347','泰格医药'),('sz300408','三环集团'),('sz300413','芒果超媒'),('sz300433','蓝思科技'),('sz300450','先导智能'),('sz300496','中科创达'),('sz300601','康泰生物'),('sz300661','圣邦股份'),('sz300699','光威复材'),('sz300782','卓胜微'),('sz300896','爱美客'),('sz301269','华大九天'),('sz301308','江波龙'),('sz301358','湖南裕能'),('sz301363','美好医疗'),('sz301391','卡莱特'),('sz301498','乖宝宠物'),('sz301236','软通动力'),('sz002410','广联达'),('sz002709','天赐材料'),('sh600221','海航控股'),('sh600118','中国卫星'),('sh600549','厦门钨业'),('sh601727','上海电气'),('sh600930','华电新能'),('sh601018','宁波港'),('sh601456','国联民生'),('sh600100','同方股份'),('sh600161','天坛生物'),('sh600256','广汇能源'),('sh601869','长飞光纤'),('sh601236','红塔证券'),('sh600885','宏发股份'),('sh600884','杉杉股份'),('sh601117','中国化学'),('sh601555','东吴证券'),('sh600765','中航重机'),('sh600563','法拉电子'),('sh600862','中航高科'),('sh600177','雅戈尔'),('sh600732','爱旭股份'),('sh601198','东兴证券'),('sh600704','物产中大'),('sh603127','昭衍新药'),('sh600201','生物股份'),('sh603444','吉比特'),('sh600642','申能股份'),('sh601128','常熟银行'),('sh600879','航天电子'),('sh600497','驰宏锌锗'),('sh600369','西南证券'),('sh600348','华阳股份'),('sh601005','重庆钢铁'),('sh600998','九州通'),('sh603568','伟明环保'),('sh600315','上海家化'),('sh600415','小商品城'),('sh601872','招商轮船'),('sh600801','华新水泥'),('sh600827','百联股份'),('sh601717','郑煤机'),('sh600567','山鹰国际'),('sh600060','海信视像'),('sh600131','国网信通'),('sh603885','吉祥航空'),('sh600598','北大荒'),('sh600967','内蒙一机'),('sh600507','方大特钢'),('sh600820','隧道股份'),('sh600021','上海电力'),('sh600566','济川药业'),('sh600737','中粮糖业'),('sh600022','山东钢铁'),('sh600707','彩虹股份'),('sh600376','首开股份'),('sh600582','天地科技'),('sh600062','华润双鹤'),('sh600126','杭钢股份'),('sh601975','招商南油'),('sh601098','中南传媒'),('sh600643','爱建集团'),('sh600959','江苏有线'),('sh601958','金钼股份'),('sh600056','中国医药'),('sh600266','城建发展'),('sh600901','江苏租赁'),('sh601860','紫金银行'),('sh600717','天津港'),('sh601699','潞安环能'),('sh600188','兖矿能源'),('sh601666','平煤股份'),('sh600395','盘江股份'),('sh601101','昊华能源'),('sh600123','兰花科创'),('sh600971','恒源煤电'),('sh600997','开滦股份'),('sh600141','兴发集团'),('sh600426','华鲁恒升'),('sh600352','浙江龙盛'),('sh600160','巨化股份'),('sh600486','扬农化工'),('sh600409','三友化工'),('sh600500','中化国际'),('sh600096','云天化'),('sh600596','新安股份'),('sh600110','诺德股份'),('sh600392','盛和资源'),('sh600111','北方稀土'),('sh600259','广晟有色'),('sh600366','宁波韵升'),('sh600456','宝钛股份'),('sh600459','贵研铂业'),('sh600980','北矿科技'),('sh600027','华电国际'),('sh600863','内蒙华电'),('sh600795','国电电力'),('sh601991','大唐发电'),('sh600578','京能电力'),('sh600023','浙能电力'),('sh601016','节能风电'),('sh600995','南网储能'),('sh601619','嘉泽新能'),('sh600163','中闽能源'),('sh600821','金开新能'),('sh600396','华电辽能'),('sh600509','天富能源'),('sh600719','大连热电'),('sh600744','华银电力'),('sz000009','中国宝安'),('sz000012','南玻A'),('sz000021','深科技'),('sz000027','深圳能源'),('sz000031','大悦城'),('sz000039','中集集团'),('sz000050','深天马A'),('sz000060','中金岭南'),('sz000062','深圳华强'),('sz000069','华侨城A'),('sz000078','海王生物'),('sz000089','深圳机场'),('sz000099','中信海直'),('sz000151','中成股份'),('sz000157','中联重科'),('sz000158','常山北明'),('sz000166','申万宏源'),('sz000400','许继电气'),('sz000401','冀东水泥'),('sz000408','藏格矿业'),('sz000425','徐工机械'),('sz000488','晨鸣纸业'),('sz000503','国新健康'),('sz000528','柳工'),('sz000547','航天发展'),('sz000552','甘肃能化'),('sz000553','安道麦A'),('sz000559','万向钱潮'),('sz000566','海南海药'),('sz000581','威孚高科'),('sz000598','兴蓉环境'),('sz000600','建投能源'),('sz000617','中油资本'),('sz000623','吉林敖东'),('sz000625','长安汽车'),('sz000636','风华高科'),('sz000650','仁和药业'),('sz000661','长春高新'),('sz000671','阳光城'),('sz000680','山推股份'),('sz000686','东北证券'),('sz000690','宝新能源'),('sz000709','河钢股份'),('sz000728','国元证券'),('sz000738','航发控制'),('sz000750','国海证券'),('sz000758','中色股份'),('sz000761','本钢板材'),('sz000768','中航西飞'),('sz000783','长江证券'),('sz000792','盐湖股份'),('sz000799','酒鬼酒'),('sz000800','一汽解放'),('sz000807','云铝股份'),('sz000818','航锦科技'),('sz000825','太钢不锈'),('sz000839','中信国安'),('sz000848','承德露露'),('sz000860','顺鑫农业'),('sz000877','天山股份'),('sz000878','云南铜业'),('sz000883','湖北能源'),('sz000895','双汇发展'),('sz000898','鞍钢股份'),('sz000903','云内动力'),('sz000906','浙商中拓'),('sz000917','电广传媒'),('sz000921','海信家电'),('sz000932','华菱钢铁'),('sz000937','冀中能源'),('sz000959','首钢股份'),('sz000960','锡业股份'),('sz000967','盈峰环境'),('sz000970','中科三环'),('sz000975','山金国际'),('sz000977','浪潮信息'),('sz000987','越秀资本'),('sz000990','诚志股份'),('sz000997','新大陆'),('sz001203','大中矿业'),('sz001286','陕西能源'),('sz001289','龙源电力'),('sz001872','招商港口'),('sz001965','招商公路'),('sz002001','新和成'),('sz002004','华邦健康'),('sz002007','华兰生物'),('sz002008','大族激光'),('sz002025','航天电器'),('sz002028','思源电气'),('sz002030','达安基因'),('sz002038','双鹭药业'),('sz002041','登海种业'),('sz002042','华孚时尚'),('sz002043','兔宝宝'),('sz002044','美年健康'),('sz002048','宁波华翔'),('sz002051','中工国际'),('sz002056','横店东磁'),('sz002063','远光软件'),('sz002065','东华软件'),('sz002069','獐子岛'),('sz002074','国轩高科'),('sz002078','太阳纸业'),('sz002080','中材科技'),('sz002081','金螳螂'),('sz002085','万丰奥威'),('sz002091','江苏国泰'),('sz002092','中泰化学'),('sz002093','国脉科技'),('sz002097','山河智能'),('sz002110','三钢闽光'),('sz002120','韵达股份'),('sz002128','电投能源'),('sz002129','TCL中环'),('sz002130','沃尔核材'),('sz002138','顺络电子'),('sz002139','拓邦股份'),('sz002140','东华科技'),('sz002146','荣盛发展'),('sz002152','广电运通'),('sz002153','石基信息'),('sz002155','湖南黄金'),('sz002156','通富微电'),('sz002161','远望谷'),('sz002174','游族网络'),('sz002182','宝武镁业'),('sz002185','华天科技'),('sz002191','劲嘉股份'),('sz002203','海亮股份'),('sz002206','海利得'),('sz002214','大立科技'),('sz002217','合力泰'),('sz002221','东华能源'),('sz002223','鱼跃医疗'),('sz002224','三力士'),('sz002233','塔牌集团'),('sz002237','恒邦股份'),('sz002244','滨江集团'),('sz002249','大洋电机'),('sz002251','步步高'),('sz002258','利尔化学'),('sz002262','恩华药业'),('sz002267','陕天然气'),('sz002268','电科网安'),('sz002273','水晶光电'),('sz002281','光迅科技'),('sz002294','信立泰'),('sz002299','圣农发展'),('sz002303','美盈森'),('sz002311','海大集团'),('sz002317','众生药业'),('sz002332','仙琚制药'),('sz002340','格林美'),('sz002344','海宁皮城'),('sz002353','杰瑞股份'),('sz002368','太极股份'),('sz002372','伟星新材'),('sz002373','千方科技'),('sz002384','东山精密'),('sz002385','大北农'),('sz002389','航天彩虹'),('sz002390','信邦制药'),('sz002396','星网锐捷'),('sz002400','省广集团'),('sz002405','四维图新'),('sz002408','齐翔腾达'),('sz002414','高德红外'),('sz002422','科伦药业'),('sz002429','兆驰股份'),('sz002430','杭氧股份'),('sz002436','兴森科技'),('sz002439','启明星辰'),('sz002444','巨星科技'),('sz002456','欧菲光'),('sz002459','晶澳科技'),('sz002463','沪电股份'),('sz002465','海格通信'),('sz002467','二六三'),('sz002468','申通快递'),('sz002472','双环传动'),('sz002484','江海股份'),('sz002493','荣盛石化'),('sz002497','雅化集团'),('sz002500','山西证券'),('sz002508','老板电器'),('sz002517','恺英网络'),('sz002532','天山铝业'),('sz002541','鸿路钢构'),('sz002544','普天科技'),('sz002558','巨人网络'),('sz002563','森马服饰')]

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
    """Send the A-share-only black-and-gold styled summary on every scan."""
    key=os.environ.get('BARK_KEY','').strip()
    if not key:
        return {'status':'skipped','reason':'BARK_KEY_missing'}
    title='VEGAS V9｜A股扫描'
    lines=[
        '✦ VEGAS V9',
        'A-SHARE SIGNAL SYSTEM',
        '',
        '🔔 A股 · 今日扫描结果',
        f'正式信号：{len(signals)}只',
        '',
    ]
    if signals:
        for s in signals:
            side=str(s.get('filter_side',''))
            symbol=str(s.get('symbol',''))
            name=str(s.get('name',''))
            ts=s.get('candle_timestamp_ms')
            when=datetime.fromtimestamp(ts/1000,tz=TZ).strftime('%m-%d %H:%M') if isinstance(ts,(int,float)) else ''
            lines.append(f'▰ {name}（{symbol}）')
            lines.append(f'   过滤线确认：{side}  {when}')
    else:
        lines.append('今日暂无符合条件的信号。')
    lines.extend(['', '扫描状态：完成', 'VEGAS V9 · CN'])
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
    report['bark_notification']=send_bark(report['signals'])
    with open(REPORT_PATH,'w',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'date_beijing':today,'pool_size':len(POOL),'symbols_ok':report['symbols_ok'],'symbols_excluded':len(report['symbols_excluded']),'new_signals':len(report['new_signals']),'daily_signals':len(report['signals']),'bark_notification':report['bark_notification'],'report':REPORT_PATH},ensure_ascii=False,indent=2))
    return 0 if report['symbols_ok'] else 1
if __name__=='__main__': sys.exit(main())
