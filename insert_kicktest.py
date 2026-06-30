#!/usr/bin/env python3
"""insert_kicktest.py — Kick Types field map tab for all 35 scout HTML files.

Adds a separate "Kick Types" nav tab with:
- Vertical rugby field SVG (380x594)
- Kubota Spears (left) / Opponent (right) panels
- Match checkbox dropdown + type filter buttons
Data loaded from all 164 CSV files.
"""
import csv, glob, json, os, re

CSV_DIR   = "/Users/ktachikawa/Desktop/kubota-spears-analytics"
BIOUT_DIR = "/Users/ktachikawa/Desktop/BIoutput"
KUBOTA    = "Kubota Spears"

TEAM_SHORT = {
    'BlackRams Tokyo':              'BlackRams',
    'Kobelco Kobe Steelers':        'Steelers',
    'Kubota Spears':                'Spears',
    'Mie Honda Heat':               'Heat',
    'Mitsubishi Sagamihara Dynaboars': 'Dynaboars',
    'Saitama Wild Knights':         'WildKnights',
    'Shizuoka BlueRevs':            'BlueRevs',
    'Tokyo Sungoliath':             'Sungoliath',
    'Toshiba Brave Lupus Tokyo':    'BraveLupus',
    'Toyota Verblitz':              'Verblitz',
    'Urayasu D-Rocks':              'D-Rocks',
    'Yokohama Canon Eagles':        'Eagles',
}

COLS = {
    'Box':         '#38BDF8',
    'Bomb':        '#FB923C',
    'Territorial': '#86EFAC',
    'Touch Kick':  '#F472B6',
    'Low':         '#C084FC',
    'Chip':        '#FCD34D',
    'Cross Pitch': '#34D399',
}
TYPE_ORDER = ['Box', 'Bomb', 'Territorial', 'Touch Kick', 'Low', 'Chip', 'Cross Pitch']

# ─── JS template (uses __PLACEHOLDER__ for data injection) ───────────────────
_JS_TEMPLATE = r"""(function(){
  const ALL_KICKS=__ALL_KICKS__;
  const MATCHES=__MATCHES__;
  const COLS=__COLS__;
  const TYPE_ORDER=__TYPE_ORDER__;
  const DEF='#9CA3AF';
  const CONT=new Set(['Box','Bomb','Territorial','Cross Pitch','Chip']);
  const RET=new Set(['Own Player - Collected','Pressure Error','Pressure in Touch','Collected Bounce']);
  const IG=27,FLDH=540,SW=380;
  let selFxids=new Set([__LAST_FXID__]);
  let selType='All';
  function fy(x){return IG+(1-Math.max(0,Math.min(100,x))/100)*FLDH;}
  function fx(y){return Math.max(0,Math.min(70,y))/70*SW;}
  function col(t){return COLS[t]||DEF;}
  function getKicks(tm){
    return ALL_KICKS.filter(k=>k.tm===tm&&selFxids.has(k.f)&&(selType==='All'||k.t===selType));
  }
  function renderSVG(kicks,svgId){
    const NS='http://www.w3.org/2000/svg';
    const g=document.getElementById(svgId+'-dots');
    if(!g)return;
    g.innerHTML='';
    kicks.forEach(k=>{
      const c=document.createElementNS(NS,'circle');
      c.setAttribute('cx',fx(k.y).toFixed(1));
      c.setAttribute('cy',fy(k.x).toFixed(1));
      c.setAttribute('r',6);
      c.setAttribute('fill',col(k.t));
      c.setAttribute('fill-opacity',0.75);
      c.setAttribute('stroke','rgba(0,0,0,.2)');
      c.setAttribute('stroke-width',0.6);
      g.appendChild(c);
    });
  }
  function calcStats(kicks){
    const tot=kicks.length;
    const ds=kicks.filter(k=>k.m>0);
    const totmV=ds.reduce((a,k)=>a+k.m,0);
    const totm=ds.length?Math.round(totmV)+'m':'–';
    const avg=ds.length?(totmV/ds.length).toFixed(1)+'m':'–';
    const ct5=kicks.filter(k=>CONT.has(k.t));
    const rt=ct5.filter(k=>RET.has(k.r));
    const rp=ct5.length?(rt.length/ct5.length*100).toFixed(1)+'%':'–';
    const ct2=kicks.filter(k=>k.t==='Box'||k.t==='Bomb');
    const cont=ct2.length;
    const atk=kicks.filter(k=>k.t==='Cross Pitch'||k.t==='Chip'||k.t==='Low').length;
    return {tot,totm,avg,rp,cont,atk};
  }
  function setEl(id,v){const e=document.getElementById(id);if(e)e.textContent=v;}
  function barChart(kicks,wrapId){
    const wrap=document.getElementById(wrapId);
    if(!wrap)return;
    const cnt={};
    kicks.forEach(k=>{cnt[k.t]=(cnt[k.t]||0)+1;});
    const tot=kicks.length||1;
    const items=[];
    TYPE_ORDER.forEach(t=>{if(cnt[t])items.push([t,cnt[t]]);});
    Object.entries(cnt).forEach(([t,n])=>{if(!TYPE_ORDER.includes(t))items.push([t,n]);});
    if(!items.length){wrap.innerHTML='<div style="height:26px;border-radius:3px;background:#E5E7EB;margin-bottom:6px"></div>';return;}
    const segs=items.map(([t,n])=>{
      const c=COLS[t]||DEF;const pct=n/tot*100;
      const txt=pct>=7?Math.round(pct)+'%':'';
      return '<div title="'+t+': '+pct.toFixed(1)+'% ('+n+')" style="flex:'+pct.toFixed(2)+';background:'+c+
             ';height:100%;min-width:3px;display:flex;align-items:center;justify-content:center;'+
             'font-size:10px;font-weight:700;color:rgba(0,0,0,.75);overflow:hidden;white-space:nowrap">'+txt+'</div>';
    }).join('');
    const legs=items.map(([t,n])=>{
      const c=COLS[t]||DEF;const pct=n/tot*100;
      return '<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:#111827;margin-right:8px;margin-bottom:4px;white-space:nowrap">'+
             '<span style="width:10px;height:10px;border-radius:50%;background:'+c+';flex-shrink:0"></span>'+
             '<b>'+t+'</b> <span style="color:#6B7280">'+Math.round(pct)+'% ('+n+')</span></span>';
    }).join('');
    wrap.innerHTML='<div style="display:flex;height:26px;border-radius:4px;overflow:hidden;margin-bottom:8px">'+segs+'</div>'+
                   '<div style="display:flex;flex-wrap:wrap">'+legs+'</div>';
  }
  function getOppLabel(){
    const opps=[...selFxids].map(f=>{const m=MATCHES.find(x=>x.f===f);return m?m.os:''}).filter(Boolean);
    const uniq=[...new Set(opps)];
    if(!uniq.length)return'Opponent(s)';
    if(uniq.length===1)return uniq[0];
    return uniq.length<=3?uniq.join(' / '):'Opponents ('+uniq.length+' teams)';
  }
  function updateMatchLabel(){
    const sel=[...selFxids];
    const el=document.getElementById('kt3-mlabel');
    if(!el)return;
    if(sel.length===0){el.textContent='(none selected)';return;}
    if(sel.length===1){
      const m=MATCHES.find(x=>x.f===sel[0]);
      el.textContent=m?'R'+m.rn+' vs '+m.os:'1 match';
    }else{el.textContent=sel.length+' matches selected';}
  }
  function render(){
    const kk=getKicks('k');
    const ok=getKicks('o');
    renderSVG(kk,'kt3-kub-svg');
    renderSVG(ok,'kt3-opp-svg');
    const ks=calcStats(kk);const os=calcStats(ok);
    setEl('kt3-kub-tot',ks.tot);setEl('kt3-kub-totm',ks.totm);
    setEl('kt3-kub-avg',ks.avg);setEl('kt3-kub-ret',ks.rp);
    setEl('kt3-kub-cont',ks.cont);setEl('kt3-kub-atk',ks.atk);
    setEl('kt3-opp-tot',os.tot);setEl('kt3-opp-totm',os.totm);
    setEl('kt3-opp-avg',os.avg);setEl('kt3-opp-ret',os.rp);
    setEl('kt3-opp-cont',os.cont);setEl('kt3-opp-atk',os.atk);
    const kkAll=ALL_KICKS.filter(k=>k.tm==='k'&&selFxids.has(k.f));
    const okAll=ALL_KICKS.filter(k=>k.tm==='o'&&selFxids.has(k.f));
    barChart(kkAll,'kt3-kub-bar-wrap');
    barChart(okAll,'kt3-opp-bar-wrap');
    const hdr=document.getElementById('kt3-opp-hdr');
    if(hdr)hdr.textContent=getOppLabel();
  }
  window.kt3ToggleDrop=function(e){
    e.stopPropagation();
    const p=document.getElementById('kt3-mdrop-panel');
    p.style.display=p.style.display==='none'?'block':'none';
  };
  document.addEventListener('click',function(e){
    if(!e.target.closest('#kt3-mdrop-wrap')){
      const p=document.getElementById('kt3-mdrop-panel');
      if(p)p.style.display='none';
    }
  });
  window.kt3MatchChange=function(){
    selFxids=new Set();
    document.querySelectorAll('.kt3-mcb:checked').forEach(cb=>selFxids.add(+cb.value));
    updateMatchLabel();
    render();
  };
  window.kt3SelectAll=function(){
    document.querySelectorAll('.kt3-mcb').forEach(cb=>cb.checked=true);
    kt3MatchChange();
  };
  window.kt3ClearAll=function(){
    document.querySelectorAll('.kt3-mcb').forEach(cb=>cb.checked=false);
    kt3MatchChange();
  };
  window.kt3TypeFilter=function(type){
    selType=type;
    document.querySelectorAll('.kt3-fbtn').forEach(b=>{
      const active=b.dataset.t===type;
      b.style.background=active?'#374151':'#F9FAFB';
      b.style.color=active?'#fff':'#374151';
      b.style.fontWeight=active?'700':'400';
    });
    render();
  };
  render();
})();"""


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_all_kicks():
    """Read all 164 CSVs, return (matches_dict, kicks_list).

    matches_dict: {fxid: {rn, os}}  — Kubota Spears matches only
    kicks_list:   list of dicts {f, tm, x, y, ex, t, r, m, rn}
    """
    matches = {}   # fxid → {rn, os}
    kicks   = []

    for fpath in sorted(glob.glob(os.path.join(CSV_DIR, "*.csv"))):
        try:
            with open(fpath, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    home = row.get('homeTeamName', '')
                    away = row.get('awayTeamName', '')
                    if KUBOTA not in (home, away):
                        continue
                    if row.get('actionName') != 'Kick':
                        continue
                    raw_x = row.get('x_coord', '')
                    raw_y = row.get('y_coord', '')
                    if not raw_x or not raw_y:
                        continue
                    try:
                        x = float(raw_x)
                        y = float(raw_y)
                        fxid = int(float(row['FXID']))
                        rn   = int(float(row.get('roundNumber', 0) or 0))
                    except (ValueError, TypeError, KeyError):
                        continue

                    if fxid not in matches:
                        opp = away if home == KUBOTA else home
                        matches[fxid] = {
                            'rn': rn,
                            'os': TEAM_SHORT.get(opp, opp[:10]),
                        }

                    try:
                        ex = float(row.get('x_coord_end') or 0)
                    except (ValueError, TypeError):
                        ex = 0.0
                    try:
                        m = float(row.get('Metres') or 0)
                    except (ValueError, TypeError):
                        m = 0.0

                    t = (row.get('ActionTypeName') or '').strip()
                    r = (row.get('ActionResultName') or '').strip()
                    tm = 'k' if row.get('teamName') == KUBOTA else 'o'

                    kicks.append({
                        'f': fxid, 'tm': tm,
                        'x': round(x, 1), 'y': round(y, 1),
                        'ex': round(ex, 1),
                        't': t, 'r': r,
                        'm': round(m, 1),
                        'rn': rn,
                    })
        except Exception as e:
            print(f"  [WARN] {os.path.basename(fpath)}: {e}")

    return matches, kicks


# ─── HTML builders ────────────────────────────────────────────────────────────

_SVG_FIELD = (
    '<svg id="__SID__" viewBox="0 0 380 594" overflow="visible" '
    'style="width:100%;max-width:380px;display:block;margin:0 auto;'
    'border-radius:8px;overflow:visible" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="380" height="594" fill="#4d8a28"/>'
    '<rect x="0" y="0" width="380" height="27" fill="#3d7520"/>'
    '<rect x="0" y="567" width="380" height="27" fill="#3d7520"/>'
    # 10 alternating stripes 54px each
    '<rect x="0" y="27.0" width="380" height="54.0" fill="#4d8a28"/>'
    '<rect x="0" y="81.0" width="380" height="54.0" fill="#5a9e2f"/>'
    '<rect x="0" y="135.0" width="380" height="54.0" fill="#4d8a28"/>'
    '<rect x="0" y="189.0" width="380" height="54.0" fill="#5a9e2f"/>'
    '<rect x="0" y="243.0" width="380" height="54.0" fill="#4d8a28"/>'
    '<rect x="0" y="297.0" width="380" height="54.0" fill="#5a9e2f"/>'
    '<rect x="0" y="351.0" width="380" height="54.0" fill="#4d8a28"/>'
    '<rect x="0" y="405.0" width="380" height="54.0" fill="#5a9e2f"/>'
    '<rect x="0" y="459.0" width="380" height="54.0" fill="#4d8a28"/>'
    '<rect x="0" y="513.0" width="380" height="54.0" fill="#5a9e2f"/>'
    # Side lines
    '<line x1="0" y1="27" x2="0" y2="567" stroke="white" stroke-width="1.5"/>'
    '<line x1="380" y1="27" x2="380" y2="567" stroke="white" stroke-width="1.5"/>'
    # Try lines
    '<line x1="0" y1="27" x2="380" y2="27" stroke="white" stroke-width="2"/>'
    '<line x1="0" y1="567" x2="380" y2="567" stroke="white" stroke-width="2"/>'
    # 22m lines
    '<line x1="0" y1="448.2" x2="380" y2="448.2" stroke="rgba(255,255,255,.75)" stroke-width="1.3"/>'
    '<line x1="0" y1="145.8" x2="380" y2="145.8" stroke="rgba(255,255,255,.75)" stroke-width="1.3"/>'
    # 10m lines (dashed)
    '<line x1="0" y1="351.0" x2="380" y2="351.0" stroke="rgba(255,255,255,.5)" stroke-width="1" stroke-dasharray="5,4"/>'
    '<line x1="0" y1="243.0" x2="380" y2="243.0" stroke="rgba(255,255,255,.5)" stroke-width="1" stroke-dasharray="5,4"/>'
    # Halfway
    '<line x1="0" y1="297.0" x2="380" y2="297.0" stroke="white" stroke-width="2"/>'
    # Labels
    '<text x="5" y="463.2" font-size="16" font-family="sans-serif" fill="rgba(255,255,255,.9)" font-weight="500">22</text>'
    '<text x="5" y="366.0" font-size="16" font-family="sans-serif" fill="rgba(255,255,255,.9)" font-weight="500">10</text>'
    '<text x="5" y="312.0" font-size="16" font-family="sans-serif" fill="rgba(255,255,255,.9)" font-weight="500">50</text>'
    '<text x="5" y="258.0" font-size="16" font-family="sans-serif" fill="rgba(255,255,255,.9)" font-weight="500">10</text>'
    '<text x="5" y="160.8" font-size="16" font-family="sans-serif" fill="rgba(255,255,255,.9)" font-weight="500">22</text>'
    # Direction labels
    '<text x="370" y="18" font-size="14" font-weight="800" font-family="sans-serif" fill="white" text-anchor="end">ATTACK ↑</text>'
    '<text x="370" y="580" font-size="14" font-weight="800" font-family="sans-serif" fill="white" text-anchor="end">OWN ↓</text>'
    # Goal posts (attack end)
    '<line x1="165" y1="0" x2="165" y2="27" stroke="white" stroke-width="2.5"/>'
    '<line x1="215" y1="0" x2="215" y2="27" stroke="white" stroke-width="2.5"/>'
    '<line x1="165" y1="12" x2="215" y2="12" stroke="white" stroke-width="2.5"/>'
    # Goal posts (own end)
    '<line x1="165" y1="497" x2="165" y2="567" stroke="white" stroke-width="2.5"/>'
    '<line x1="215" y1="497" x2="215" y2="567" stroke="white" stroke-width="2.5"/>'
    '<line x1="165" y1="552" x2="215" y2="552" stroke="white" stroke-width="2.5"/>'
    # Scale arrow
    '<line x1="388" y1="448.2" x2="388" y2="153" stroke="white" stroke-width="1.2" opacity="0.35"/>'
    '<polygon points="385.5,153 390.5,153 388,147" fill="white" opacity="0.35"/>'
    '<g id="__SID__-dots"></g>'
    '</svg>'
)


def _stat_box(box_id, label, sub=''):
    sub_html = f'<div style="font-size:7px;color:#9CA3AF;margin-top:1px">{sub}</div>' if sub else ''
    return (
        f'<div style="flex:1;background:white;border:1px solid #E5E7EB;border-radius:6px;'
        f'padding:6px 4px;text-align:center;min-width:52px">'
        f'<div id="{box_id}" style="font-family:Oswald,sans-serif;font-size:16px;'
        f'font-weight:700;color:#111827;line-height:1.1">–</div>'
        f'<div style="font-size:7.5px;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:.05em;margin-top:2px;line-height:1.2">{label}</div>'
        + sub_html + '</div>'
    )


def _panel(side, label, border_color):
    sid = 'kub' if side == 'k' else 'opp'
    svg = _SVG_FIELD.replace('__SID__', f'kt3-{sid}-svg')
    hdr = (
        f'<div style="font-family:Oswald,sans-serif;font-size:11px;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;color:{border_color};'
        f'border-bottom:2px solid {border_color}44;margin-bottom:8px" '
        f'id="kt3-{sid}-hdr">{label}</div>'
    )
    stats = (
        f'<div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap">'
        + _stat_box(f'kt3-{sid}-tot',  'Total Kicks')
        + _stat_box(f'kt3-{sid}-totm', 'Total Metres')
        + _stat_box(f'kt3-{sid}-avg',  'Avg Distance')
        + _stat_box(f'kt3-{sid}-ret',  'Contest Ret%', '5 types')
        + _stat_box(f'kt3-{sid}-cont', 'Contest Kicks', 'Box &amp; Bomb')
        + _stat_box(f'kt3-{sid}-atk',  'Attacking Kicks', 'XP / Chip / Low')
        + '</div>'
    )
    return (
        f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:6px">'
        + hdr + svg + stats
        + f'<div id="kt3-{sid}-bar-wrap"></div>'
        + '</div>'
    )


def build_kicktest_section(matches, kicks, max_round):
    """Build the complete <div id="kicktest"> section for a given max_round."""
    valid_fxids = {fxid for fxid, info in matches.items() if info['rn'] <= max_round}
    if not valid_fxids:
        return '<div id="kicktest" class="section"><p style="padding:20px">No data</p></div>'

    valid_matches = sorted(
        [(fxid, matches[fxid]) for fxid in valid_fxids],
        key=lambda x: x[1]['rn']
    )
    valid_kicks = [k for k in kicks if k['f'] in valid_fxids]

    last_fxid  = valid_matches[-1][0]
    last_info  = valid_matches[-1][1]
    def_label  = f'R{last_info["rn"]} vs {last_info["os"]}'

    # JSON data arrays (compact)
    kicks_json   = json.dumps(
        [{'f': k['f'], 'tm': k['tm'], 'x': k['x'], 'y': k['y'],
          'ex': k['ex'], 't': k['t'], 'r': k['r'], 'm': k['m'], 'q': 0}
         for k in valid_kicks],
        separators=(',', ':')
    )
    matches_json = json.dumps(
        [{'f': fxid, 'rn': info['rn'], 'os': info['os']} for fxid, info in valid_matches],
        separators=(',', ':')
    )
    cols_json  = json.dumps(COLS, separators=(',', ':'))
    order_json = json.dumps(TYPE_ORDER, separators=(',', ':'))

    # JS script (substitute placeholders)
    js = (_JS_TEMPLATE
          .replace('__ALL_KICKS__', kicks_json)
          .replace('__MATCHES__',   matches_json)
          .replace('__COLS__',      cols_json)
          .replace('__TYPE_ORDER__', order_json)
          .replace('__LAST_FXID__', str(last_fxid)))

    # Match checkboxes
    mcbs = ''
    for fxid, info in valid_matches:
        chk = ' checked' if fxid == last_fxid else ''
        mcbs += (
            f'<label style="display:flex;align-items:center;gap:6px;font-size:10.5px;'
            f'color:#374151;padding:3px 0;cursor:pointer">'
            f'<input type="checkbox" class="kt3-mcb" value="{fxid}"{chk} '
            f'onchange="kt3MatchChange()"/>'
            f'R{info["rn"]} vs {info["os"]}</label>'
        )

    # Type filter buttons
    type_btns = ''
    for t in ['All'] + TYPE_ORDER:
        if t == 'All':
            sty = 'background:#374151;color:#fff;font-weight:700'
        else:
            sty = 'background:#F9FAFB;color:#374151;font-weight:400'
        type_btns += (
            f'<button class="kt3-fbtn" data-t="{t}" onclick="kt3TypeFilter(\'{t}\')" '
            f'style="padding:4px 10px;border:1px solid #D1D5DB;border-radius:4px;'
            f'font-size:10px;cursor:pointer;{sty};transition:all .15s">{t}</button>'
        )

    # Color legend
    legend = ' '.join(
        f'<span style="display:inline-flex;align-items:center;gap:3px;font-size:9.5px;color:#374151">'
        f'<span style="width:9px;height:9px;border-radius:50%;background:{COLS[t]};flex-shrink:0"></span>'
        f'{t}</span>'
        for t in TYPE_ORDER
    )

    return (
        f'<div id="kicktest" class="section">\n'
        f'<div style="padding:14px 20px">\n'
        f'  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;'
        f'padding-bottom:9px;border-bottom:2px solid #E5E7EB">\n'
        f'    <div style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;'
        f'letter-spacing:.1em;text-transform:uppercase;color:#374151">'
        f'Kicking ▸ Field Map — Kubota Spears Season 2026</div>\n'
        f'    <div style="font-size:9px;color:#9CA3AF;margin-left:auto">'
        f'座標系 x: 0=自陣 / 100=敵陣 · 上=攻撃方向</div>\n'
        f'  </div>\n'
        f'  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">\n'
        f'    <div style="font-size:10px;font-weight:700;color:#6B7280;white-space:nowrap">試合:</div>\n'
        f'    <div id="kt3-mdrop-wrap" style="position:relative;display:inline-block">\n'
        f'      <button id="kt3-mdrop-btn" onclick="kt3ToggleDrop(event)"\n'
        f'        style="border:1px solid #D1D5DB;border-radius:6px;padding:5px 12px;background:white;\n'
        f'               font-size:11px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;white-space:nowrap">\n'
        f'        &#128197; <span id="kt3-mlabel">{def_label}</span>'
        f'<span style="color:#9CA3AF">&#9660;</span>\n'
        f'      </button>\n'
        f'      <div id="kt3-mdrop-panel"\n'
        f'        style="display:none;position:absolute;top:calc(100% + 4px);left:0;z-index:2000;\n'
        f'               background:white;border:1px solid #E5E7EB;border-radius:8px;padding:10px;\n'
        f'               min-width:240px;max-height:320px;overflow-y:auto;\n'
        f'               box-shadow:0 4px 16px rgba(0,0,0,.12)">\n'
        f'        <div style="display:flex;gap:6px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #F3F4F6">\n'
        f'          <button onclick="kt3SelectAll()" style="flex:1;font-size:10px;padding:3px 6px;border:1px solid #D1D5DB;border-radius:4px;cursor:pointer;background:#F9FAFB">All</button>\n'
        f'          <button onclick="kt3ClearAll()" style="flex:1;font-size:10px;padding:3px 6px;border:1px solid #D1D5DB;border-radius:4px;cursor:pointer;background:#F9FAFB">Clear</button>\n'
        f'        </div>\n'
        f'        {mcbs}\n'
        f'      </div>\n'
        f'    </div>\n'
        f'    <div style="font-size:10px;font-weight:700;color:#6B7280;white-space:nowrap;margin-left:8px">種別:</div>\n'
        f'    <div style="display:flex;gap:5px;flex-wrap:wrap">{type_btns}</div>\n'
        f'  </div>\n'
        f'  <div style="display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap">{legend}</div>\n'
        f'  <div style="display:flex;gap:20px">\n'
        f'    {_panel("k", "Kubota Spears", "#F97316")}\n'
        f'    {_panel("o", "Opponent(s)", "#DC2626")}\n'
        f'  </div>\n'
        f'</div>\n'
        f'<script>\n{js}\n</script>\n'
        f'</div>\n'
    )


# ─── File processor ───────────────────────────────────────────────────────────

def process_file(fpath, matches, kicks):
    """Insert or replace kicktest section in one HTML file."""
    m = re.search(r'_R(\d+)\.html$', fpath)
    if not m:
        return False
    max_round = int(m.group(1))

    with open(fpath, encoding='utf-8') as f:
        content = f.read()

    new_section = build_kicktest_section(matches, kicks, max_round)

    KT  = '<div id="kicktest" class="section">'
    LO  = '<div id="lo" class="section">'
    SP  = '<div id="sp" class="section">'

    if KT in content:
        # Replace existing kicktest section
        kt_i = content.index(KT)
        # Find next top-level section after kicktest
        next_marker = None
        for marker in [LO, SP]:
            try:
                idx = content.index(marker, kt_i + 1)
                if next_marker is None or idx < next_marker:
                    next_marker = idx
            except ValueError:
                pass
        if next_marker is None:
            return False
        content = content[:kt_i] + new_section + content[next_marker:]
    elif LO in content:
        lo_i = content.index(LO)
        content = content[:lo_i] + new_section + content[lo_i:]
    elif SP in content:
        sp_i = content.index(SP)
        content = content[:sp_i] + new_section + content[sp_i:]
    else:
        return False

    # Add nav button "Kick Types" after "Kicking" button if missing
    if "showSection('kicktest'" not in content:
        kick_btn = ">Kicking</button>"
        if kick_btn in content:
            idx = content.index(kick_btn) + len(kick_btn)
            nav = '<button class="nav-btn" style="color:#6D28D9" onclick="showSection(\'kicktest\',this)">Kick Types</button>'
            content = content[:idx] + nav + content[idx:]

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

_cache = {'matches': None, 'kicks': None}

def process_file_cached(fpath):
    """Wrapper for rugby_bi.py integration: loads data once, caches for subsequent calls."""
    if _cache['matches'] is None:
        _cache['matches'], _cache['kicks'] = load_all_kicks()
    return process_file(fpath, _cache['matches'], _cache['kicks'])


def main():
    print("Loading kick data from CSVs...")
    matches, kicks = load_all_kicks()
    print(f"  {len(matches)} Kubota matches, {len(kicks)} kick events")

    done = 0
    for fname in sorted(os.listdir(BIOUT_DIR)):
        if not (fname.startswith("scout_Spears_vs_") and fname.endswith(".html")):
            continue
        fpath = os.path.join(BIOUT_DIR, fname)
        if process_file(fpath, matches, kicks):
            print(f"  ✓ {fname}")
            done += 1
        else:
            print(f"  ✗ SKIP {fname}")

    print(f"\nDone: {done} files updated.")


if __name__ == "__main__":
    main()
