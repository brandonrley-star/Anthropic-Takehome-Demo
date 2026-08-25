/* Field Intelligence — view layer.
   Renders only what the API returns. No analysis happens in the browser. */
'use strict';

const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
/* Static builds (GitHub Pages) are served from a repository subpath such as
   /<repo>/, so nothing may be root-relative. The exporter writes window.FI_STATIC
   and a tree of .json files mirroring the API; every call site below is unchanged
   because the mapping happens here. Routing is hash-based, so the document URL
   never changes and plain relative paths always resolve against /<repo>/. */
const STATIC = typeof window !== 'undefined' && !!window.FI_STATIC;
const staticPath = p => {
  let s = p.replace(/^\//, '');
  if (s === 'api/ask/status') s = 'api/ask_status';
  return s + '.json';
};
const api = p => fetch(STATIC ? staticPath(p) : p).then(r => r.json());
const esc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const usd = n => { const v = Number(n) || 0;
  return '$' + (v && v < 1000
    ? v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})
    : Math.round(v).toLocaleString('en-US')); };
const S = { overview:null, baseline:null, findings:null, detail:{}, ask:null, filter:'all' };

/* Turn WO-2026-00571 into a clickable chip anywhere in prose. */
const linkWOs = t => esc(t).replace(/\b(WO-\d{4}-\d{5})\b/g,
  '<button class="woid" data-wo="$1">$1</button>');

/* ============================================================== OVERVIEW */
async function renderOverview(){
  const o = S.overview = S.overview || await api('/api/overview');
  const p = S.prov = S.prov || await api('/api/provenance');
  const c = o.commercial, v = o.verdict_counts;
  $('#v-overview').innerHTML = `
    <h2>Fleet Overview</h2>
    <p class="lede">Two years of technician field reports across the managed
      fleet, interpreted and triaged into decisions an asset management team
      can act on.</p>

    <div class="grid g4" style="margin-bottom:14px">
      <div class="stat"><div class="k">Work orders</div>
        <div class="v">${o.work_orders.toLocaleString()}</div>
        <div class="s">${esc(o.window)}</div></div>
      <div class="stat"><div class="k">Sites</div><div class="v">${o.sites}</div>
        <div class="s">${o.fleet_gw} GW under management</div></div>
      <div class="stat"><div class="k">Candidates generated</div>
        <div class="v">${o.candidates_total}</div>
        <div class="s">Patterns worth a second look</div></div>
      <div class="stat"><div class="k">Candidates examined</div>
        <div class="v">${o.candidates_examined}</div>
        <div class="s">Top 80% of estimated impact</div></div>
    </div>

    <div class="grid g3" style="margin-bottom:20px">
      <div class="stat hero" style="border-left:3px solid var(--esc)">
        <div class="k">Escalate</div><div class="v">${v.escalate}</div>
        <div class="s">Worth commercial action now</div></div>
      <div class="stat hero" style="border-left:3px solid var(--dep)">
        <div class="k">Deprioritize</div><div class="v">${v.deprioritize}</div>
        <div class="s">Real, but not worth acting on</div></div>
      <div class="stat hero" style="border-left:3px solid var(--dec)">
        <div class="k">Decline</div><div class="v">${v.decline}</div>
        <div class="s">Examined and found not to be a finding</div></div>
    </div>

    <h3>The analysis that produced these findings</h3>
    <div class="grid g4" style="margin-bottom:14px">
      <div class="stat"><div class="k">Cost of analysis</div>
        <div class="v">${usd(p.findings_cost_usd)}</div>
        <div class="s">To interpret and triage all ${o.work_orders.toLocaleString()} reports</div></div>
      <div class="stat"><div class="k">Original run time</div>
        <div class="v">~${p.analysis_minutes} min</div>
        <div class="s">Live model calls, 16-way concurrency</div></div>
      <div class="stat"><div class="k">Cost incurred to date</div>
        <div class="v" style="font-size:21px">${usd(c.incurred_low)}–${usd(c.incurred_high)}</div>
        <div class="s">${c.incurred_work_orders} work orders · ${c.labor_hours} labour hours</div></div>
      <div class="stat"><div class="k">Warranty recovery</div>
        <div class="v" style="font-size:21px">${usd(c.warranty_recoverable)}</div>
        <div class="s">Potentially recoverable from suppliers</div></div>
    </div>

    <div class="note" style="margin-bottom:12px">
      Claude interprets and evaluates the operational evidence.
      Deterministic code calculates financial impact from explicit assumptions.
    </div>
    ${STATIC ? `<div class="warn" style="margin-bottom:12px">
      This browser version replays previously completed Claude analysis from
      committed artifacts. No model calls are made by the hosted static site.
      Live Claude Q&amp;A is available when the project is run locally.
    </div>` : ''}
    <p class="small muted" style="margin-bottom:24px">
      The two cost figures above are realised spend on work already performed,
      de-duplicated across findings that share work orders. Forward-looking
      replacement exposure is reported on individual findings, where the
      population it applies to is stated, rather than aggregated here.
    </p>

    <div class="panel replay" id="replay-panel">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <h3 style="margin:0">Claude analysis</h3>
        <span class="pill plain">Replay of previously completed analysis</span>
        <button class="btn" id="btn-replay" style="margin-left:auto">Replay analysis</button>
      </div>
      <p class="small muted" style="margin-top:8px">
        These findings come from a real model run whose outputs are stored in this
        repository. The original run made ${p.stages.reduce((a,s)=>a+s.calls,0).toLocaleString()}
        API calls and cost ${usd(p.findings_cost_usd)}. Replaying it here costs $0
        and is instant — the analysis itself was not instantaneous.
      </p>
      <ol id="replay-steps" style="margin-top:14px">
        ${o.replay_steps.map(s=>`<li><span>${esc(s)}</span></li>`).join('')}
      </ol>
      <div id="replay-cta" style="display:none;margin-top:14px">
        <button class="btn" onclick="location.hash='#/findings'">Explore the analysis →</button>
      </div>
    </div>

    <details class="panel" style="margin-top:16px">
      <summary style="cursor:pointer;font-weight:600;font-size:14px">Analysis provenance</summary>
      <dl class="kv">
        <dt>Model</dt><dd class="mono">${esc(p.model)}</dd>
        <dt>Extraction</dt><dd>${esc(p.stage1_backend)} — live per-report model calls</dd>
        <dt>Reasoning</dt><dd>${esc(p.reasoning_backend)} — live hypothesis and verification calls</dd>
        <dt>Cost of this analysis</dt><dd>${usd(p.findings_cost_usd)}</dd>
        <dt>Total session spend</dt><dd>${usd(p.session_cost_usd)} <span class="muted small">(includes development and superseded runs)</span></dd>
        <dt>Cost to replay</dt><dd>$0.00 — results are stored locally</dd>
        <dt>Unclassified symptoms</dt><dd>${p.extraction_quality.symptom_unclassified_pct}% of reports</dd>
      </dl>
      <table><thead><tr><th>Stage</th><th class="num">Calls</th><th class="num">Cost</th></tr></thead>
        <tbody>${p.stages.map(s=>`<tr><td class="mono">${esc(s.stage)}</td>
          <td class="num">${s.calls.toLocaleString()}</td><td class="num">${usd(s.usd)}</td></tr>`).join('')}
        </tbody></table>
    </details>`;
  $('#btn-replay').onclick = runReplay;
}

function runReplay(){
  const items = $$('#replay-steps li');
  items.forEach(li => li.classList.remove('in','done'));
  $('#replay-cta').style.display = 'none';
  $('#btn-replay').disabled = true;
  items.forEach((li,i) => setTimeout(()=>{
    li.classList.add('in');
    if(i) items[i-1].classList.add('done');
    if(i === items.length-1){
      setTimeout(()=>{ li.classList.add('done');
        $('#replay-cta').style.display='block'; $('#btn-replay').disabled=false; }, 420);
    }
  }, 90 + i*420));
}

/* ============================================================== BASELINE */
async function renderBaseline(){
  const b = S.baseline = S.baseline || await api('/api/baseline');
  const trap = b.by_rate.find(r => r.site === 'Blackfoot Draw');
  const maxRaw = b.by_raw[0].tickets, maxRate = b.by_rate[0].rate;
  const bar = (rows, key, max, hiSite) => rows.slice(0,10).map(r=>`
    <div class="chart-row ${r.site===hiSite?'hi':''}">
      <div class="nm">${esc(r.site)}</div>
      <div class="bar" style="width:${Math.max(2,(r[key]/max)*310)}px"></div>
      <div class="vl">${key==='rate'?r.rate:r.tickets}</div>
    </div>`).join('');

  $('#v-baseline').innerHTML = `
    <h2>Baseline Analysis</h2>
    <p class="lede">Before any model is involved: how the fleet looks when you
      rank sites the way most reliability reviews do.</p>

    <div class="grid g2" style="margin-bottom:18px">
      <div class="panel">
        <h4>Raw ticket count</h4>
        ${bar(b.by_raw,'tickets',maxRaw,'Blackfoot Draw')}
        <p class="small muted" style="margin-top:12px">Blackfoot Draw does not
          appear — it ranks ${trap.raw_rank} of ${b.total_sites}.</p>
      </div>
      <div class="panel">
        <h4>Exposure-normalised incident rate <span class="muted">(per GW-month under contract)</span></h4>
        ${bar(b.by_rate,'rate',maxRate,'Blackfoot Draw')}
        <p class="small muted" style="margin-top:12px">Same fleet, same reports.
          Blackfoot Draw is now first.</p>
      </div>
    </div>

    <div class="panel" style="margin-bottom:18px;border-left:3px solid var(--esc)">
      <h3 style="margin-bottom:4px">Blackfoot Draw: rank ${trap.raw_rank} → rank ${trap.norm_rank}</h3>
      <p class="small muted" style="margin-bottom:12px">
        ${trap.tickets} tickets, ${trap.mw} MWdc, only ${trap.months} months under
        contract during the window. Raw counting reads a short contract as a
        healthy asset.</p>
      <table>
        <thead><tr><th>Site</th><th class="num">Tickets</th><th class="num">MWdc</th>
          <th class="num">Months</th><th class="num">Raw rank</th>
          <th class="num">Normalised rank</th><th>Reading</th></tr></thead>
        <tbody>${b.movers.map(r=>`
          <tr class="${r.site==='Blackfoot Draw'?'hi':''}">
            <td>${esc(r.site)}</td><td class="num">${r.tickets}</td>
            <td class="num">${r.mw}</td><td class="num">${r.months}</td>
            <td class="num">${r.raw_rank}</td><td class="num">${r.norm_rank}</td>
            <td class="small muted">${r.move>0?'understated by raw count':
              r.move<0?'overstated by raw count':'unchanged'}</td></tr>`).join('')}
        </tbody></table>
    </div>

    <div class="grid g2">
      <div class="note">
        Raw ticket counts are heavily influenced by site size and time under
        management. Exposure normalisation changes the answer.
      </div>
      <div class="panel" style="border-color:#C5D9D2;background:#F6FAF9">
        <span class="pill plain" style="background:#DCE9E5;color:var(--accent)">No AI required</span>
        <p class="small" style="margin-top:9px;color:var(--ink-2)">
          This step is deterministic analysis. Claude is reserved for questions
          that require interpretation of unstructured evidence.</p>
      </div>
    </div>
    <div style="margin-top:20px">
      <button class="btn" onclick="location.hash='#/findings'">See where Claude adds value →</button>
    </div>`;
}

/* ============================================================== FINDINGS */
const FEATURED = { 'CAND-003':'The refusal', 'CAND-006':'Adjacent cohort',
                   'CAND-017':'A signal counting cannot see' };

async function renderFindings(){
  const f = S.findings = S.findings || await api('/api/findings');
  const n = v => f.filter(x=>x.verdict===v).length;
  const shown = S.filter==='all' ? f : f.filter(x=>x.verdict===S.filter);
  const tab = (k,l) => `<button class="btn ghost sm ${S.filter===k?'on':''}"
    data-filter="${k}">${l}</button>`;

  $('#v-findings').innerHTML = `
    <h2>Claude Findings</h2>
    <p class="lede">${S.overview.candidates_examined} candidates examined. Each
      was tested against competing explanations and a matched control set before
      a verdict was reached.</p>
    <div class="filters">
      ${tab('all','All '+f.length)}${tab('escalate','Escalate '+n('escalate'))}
      ${tab('deprioritize','Deprioritize '+n('deprioritize'))}
      ${tab('decline','Decline '+n('decline'))}
      <span class="small muted" style="margin-left:auto">Select a finding to see its evidence</span>
    </div>
    <div class="cards">${shown.map(cardHTML).join('')}</div>`;

  $$('#v-findings [data-filter]').forEach(b =>
    b.onclick = () => { S.filter = b.dataset.filter; renderFindings(); });
  $$('#v-findings .card').forEach(c =>
    c.onclick = () => { location.hash = '#/finding/' + c.dataset.cid; });
}

function cardHTML(x){
  const feat = FEATURED[x.candidate_id];
  return `<article class="card ${feat?'feat':''}" data-cid="${x.candidate_id}">
    <div class="top">
      <span class="pill ${x.verdict}">${x.verdict}</span>
      <span class="small muted">${x.confidence} confidence</span>
      <span class="small muted mono">${x.candidate_id}</span>
      ${feat?`<span class="pill plain" style="background:var(--accent-soft);color:var(--accent)">${feat}</span>`:''}
    </div>
    <div class="hl">${esc(x.headline)}</div>
    <div class="meta">
      <span><b>${x.n_work_orders}</b> work orders</span>
      ${x.population?`<span><b>${x.population}</b> units at risk</span>`:''}
      ${x.incurred_high?`<span><b>${usd(x.incurred_low)}–${usd(x.incurred_high)}</b> incurred</span>`:''}
      ${x.warranty?`<span><b>${usd(x.warranty)}</b> warranty</span>`:''}
      <span class="muted">${esc(x.action_type.replace(/_/g,' '))}</span>
    </div>
  </article>`;
}

/* ================================================================ DETAIL */
async function renderDetail(cid){
  const d = S.detail[cid] = S.detail[cid] || await api('/api/finding/' + cid);
  if(d.error) { $('#v-findings').innerHTML = '<p>Unknown finding.</p>'; return; }
  const st = S.ask = S.ask || await api('/api/ask/status');
  const special = cid==='CAND-003' ? await comparePanel()
                : cid==='CAND-017' ? await washPanel(d) : '';

  $('#v-findings').innerHTML = `
    <button class="back" onclick="location.hash='#/findings'">← All findings</button>
    <div class="dhead">
      <span class="pill ${d.verdict}">${d.verdict}</span>
      <span class="small muted">${d.confidence} confidence</span>
      <span class="small muted mono">${d.candidate_id} · ranked ${d.rank} of ${S.overview.candidates_total}</span>
      <span class="small muted">${esc(d.kind.replace(/_/g,' '))}</span>
    </div>
    <div class="dhl">${esc(d.headline)}</div>

    <div class="grid g4" style="margin-bottom:20px">
      <div class="stat"><div class="k">Cluster size</div><div class="v">${d.n_work_orders}</div>
        <div class="s">work orders</div></div>
      <div class="stat"><div class="k">Population at risk</div>
        <div class="v">${d.population || '—'}</div>
        <div class="s">${d.population?'units not yet failed':'not established'}</div></div>
      <div class="stat"><div class="k">Cost incurred</div>
        <div class="v" style="font-size:20px">${usd(d.incurred_low)}–${usd(d.incurred_high)}</div>
        <div class="s">${d.cost_basis.labor_hours.toFixed(0)} labour hours</div></div>
      <div class="stat"><div class="k">Warranty recovery</div>
        <div class="v" style="font-size:20px">${d.warranty?usd(d.warranty):'—'}</div>
        <div class="s">${d.warranty?'potentially recoverable':'none identified'}</div></div>
    </div>

    ${special}

    <div class="panel" style="margin-bottom:14px">
      <h4>Recommended action</h4>
      <p style="font-size:14.5px">${esc(d.action)}</p>
    </div>

    <div class="grid g2" style="margin-bottom:14px">
      <div class="panel"><h4>Evidence supporting this verdict</h4>
        <p class="small" style="line-height:1.65;color:var(--ink-2)">${linkWOs(d.reasoning)}</p>
      </div>
      <div class="panel" style="border-left:3px solid var(--dep)">
        <h4>Evidence against it</h4>
        <p class="small" style="line-height:1.65;color:var(--ink-2)">${linkWOs(d.contradicting)}</p>
      </div>
    </div>

    <div class="panel" style="margin-bottom:14px">
      <h4>Population basis</h4>
      <p class="small" style="color:var(--ink-2)">${esc(d.population_detail.description||'—')}</p>
      <p class="small muted" style="margin-top:7px">${esc(d.population_detail.basis||'')}</p>
    </div>

    <div class="panel" style="margin-bottom:14px">
      <h4>Cited work orders (${d.supporting_wo_ids.length} of ${d.n_work_orders} in cluster)</h4>
      <div class="chips">${d.supporting_wo_ids.map(w=>
        `<button class="woid" data-wo="${w}">${w}</button>`).join('')}</div>
      <p class="small muted" style="margin-top:9px">Select any report to read the original technician narrative.</p>
    </div>

    <div class="ask" id="ask">
      <div style="display:flex;align-items:center;gap:9px">
        <h3 style="margin:0"><span class="livedot ${st.available?'':'off'}"></span>Ask Claude about this finding</h3>
        <span class="pill plain" style="margin-left:auto">${st.available?'Live · '+esc(st.model):'Unavailable'}</span>
      </div>
      <p class="small muted" style="margin-top:6px">Answers are drawn only from this
        finding and the ${d.supporting_wo_ids.length} work orders it cites.</p>
      ${st.available ? `
        <div class="qs" id="ask-qs"></div>
        <textarea id="ask-free" placeholder="Or ask your own question about this finding…"></textarea>
        <div style="margin-top:9px"><button class="btn sm" id="ask-go">Ask</button></div>
        <div id="ask-out"></div>`
      : `<div class="warn" style="margin-top:11px">${STATIC
           ? 'Live Claude Q&amp;A is available when the project is run locally.'
           : 'Live Claude Q&amp;A unavailable — core analysis is precomputed and remains fully accessible.'}</div>`}
    </div>

    <div style="margin-top:18px;display:flex;gap:9px">
      <button class="btn ghost sm" id="nav-prev">← Previous finding</button>
      <button class="btn ghost sm" id="nav-next">Next finding →</button>
    </div>`;

  if(st.available) wireAsk(d);
  await wireNav(cid);
}

async function wireNav(cid){
  // S.findings is empty when a finding URL is opened directly (the demo strip
  // does exactly that), so load it rather than dying on null.
  if(!S.findings) S.findings = await api('/api/findings');
  const list = S.findings.map(x=>x.candidate_id);
  const i = list.indexOf(cid);
  $('#nav-prev').onclick = () => location.hash = '#/finding/' + list[(i-1+list.length)%list.length];
  $('#nav-next').onclick = () => location.hash = '#/finding/' + list[(i+1)%list.length];
}

const SUGGEST = {
  decline:['Why did you decline this candidate?','What evidence would change your conclusion?',
           'Summarise this for an operations executive.','What should the customer investigate next?'],
  escalate:['Why is this worth escalating?','What is the strongest evidence for this finding?',
            'What would weaken this conclusion?','Summarise this for an operations executive.'],
  deprioritize:['Why is this real but not worth acting on now?','What would make this worth escalating?',
                'Summarise this for an operations executive.','What should the customer monitor?']
};

function wireAsk(d){
  const qs = $('#ask-qs'), out = $('#ask-out');
  (SUGGEST[d.verdict]||SUGGEST.escalate).forEach(q=>{
    const b = document.createElement('button');
    b.className = 'btn ghost sm'; b.textContent = q;
    b.onclick = () => send(q);
    qs.appendChild(b);
  });
  $('#ask-go').onclick = () => send($('#ask-free').value);
  const footer = r => `<p class="small muted" style="margin-top:7px">Answered live by
      ${esc(r.model)} from ${r.evidence_work_orders.length} cited work orders
      · ${r.usage.input_tokens.toLocaleString()} in / ${r.usage.output_tokens.toLocaleString()} out tokens</p>`;
  const fail = m => `<div class="warn" style="margin-top:14px">${esc(m)}</div>`;

  async function send(question){
    if(!question || !question.trim()) return;
    $$('#ask button').forEach(b=>b.disabled=true);
    out.innerHTML = `<div class="ans muted" id="ans-body">Reading ${d.supporting_wo_ids.length}
      cited work orders…</div>`;
    let acc = '';
    try{
      // Stream so the answer appears as it is written rather than after a pause.
      const res = await fetch('/api/ask/stream',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({candidate_id:d.candidate_id, question})});
      if(!res.ok || !res.body) throw new Error('stream unavailable');
      const rd = res.body.getReader(), dec = new TextDecoder();
      let buf = '', tail = null;
      for(;;){
        const {done, value} = await rd.read();
        if(done) break;
        buf += dec.decode(value, {stream:true});
        const parts = buf.split('\n\n'); buf = parts.pop();
        for(const p of parts){
          if(!p.startsWith('data: ')) continue;
          const m = JSON.parse(p.slice(6));
          if(m.delta){ acc += m.delta;
            $('#ans-body').classList.remove('muted');
            $('#ans-body').innerHTML = linkWOs(acc); }
          else tail = m;
        }
      }
      if(tail && tail.error) out.innerHTML = fail(tail.error);
      else if(tail) out.innerHTML = `<div class="ans">${linkWOs(acc)}</div>` + footer(tail);
    }catch(e){
      // Fall back to the single-shot endpoint if streaming is unavailable.
      try{
        const r = await fetch('/api/ask',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({candidate_id:d.candidate_id, question})}).then(r=>r.json());
        out.innerHTML = r.error ? fail(r.error)
          : `<div class="ans">${linkWOs(r.answer)}</div>` + footer(r);
      }catch(e2){ out.innerHTML = fail('Request failed: ' + e2.message); }
    }
    $$('#ask button').forEach(b=>b.disabled=false);
  }
}

/* --------------------------------------- DEMO MOMENT 1 + 2: the refusal */
async function comparePanel(){
  const [a,b,q3] = await Promise.all([
    api('/api/work_order/WO-2026-00571'),
    api('/api/work_order/WO-2026-00586'),
    api('/api/finding/CAND-006')]);
  const d3 = S.detail['CAND-003'];
  return `
  <div class="panel" style="margin-bottom:14px;border-left:3px solid var(--accent)">
    <h3>Initial signal</h3>
    <p class="small muted" style="margin-bottom:12px">A seemingly meaningful
      build-quarter anomaly: ${d3.units_in_cohort} units manufactured in
      ${esc(d3.dims.mfg_quarter)}, failing at
      ${d3.rate_per_unit} per unit against a peer median of ${d3.peer_median_rate}
      — a ${d3.lift}× apparent lift, ranked ${d3.rank} of ${S.overview.candidates_total}.</p>
    <h3>Claude verdict — <span style="color:var(--dec)">DECLINE</span></h3>
    <p class="small muted" style="margin-bottom:16px">The matched controls look
      materially similar to the suspected cohort.</p>

    <div class="split">
      <div class="wo member">
        <div class="pill escalate" style="margin-bottom:9px">Suspected cohort</div>
        <div class="id">${esc(a.wo_id)}</div>
        <div class="sub">${esc(a.site)} · ${esc(a.date)} · ${esc(a.asset_id)}
          · build week 20 <b>inside</b> 24Q2</div>
        <div class="nar">${esc(a.narrative)}</div>
      </div>
      <div class="wo control">
        <div class="pill decline" style="margin-bottom:9px">Matched control — one build week outside cohort</div>
        <div class="id">${esc(b.wo_id)}</div>
        <div class="sub">${esc(b.site)} · ${esc(b.date)} · ${esc(b.asset_id)}
          · build week 27 <b>outside</b> 24Q2</div>
        <div class="nar">${esc(b.narrative)}</div>
      </div>
    </div>
    <div class="note" style="margin-top:14px">
      Both reports describe the same afternoon thermal-derate behaviour, at
      different sites, on opposite sides of the suspected manufacturing boundary.
      The control narrative is the more detailed of the two. A build-window
      defect should not look like this.
    </div>
  </div>

  <div class="panel" style="margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <h3 style="margin:0">Adjacent cohort, opposite verdict</h3>
      <button class="btn sm" style="margin-left:auto"
        onclick="location.hash='#/finding/CAND-006'">Compare with adjacent 24Q3 cohort →</button>
    </div>
    <div class="split" style="margin-top:14px">
      <div class="wo" style="border-top:3px solid var(--dec)">
        <div class="pill decline" style="margin-bottom:9px">24Q2 · decline</div>
        <p class="small" style="color:var(--ink-2)">Controls show the same behaviour
          outside the boundary. ${d3.n_work_orders} work orders across roughly 18
          distinct assets — repeat visits, not a spreading defect.</p>
      </div>
      <div class="wo" style="border-top:3px solid var(--esc)">
        <div class="pill escalate" style="margin-bottom:9px">24Q3 · escalate</div>
        <p class="small" style="color:var(--ink-2)">Evidence converges on a shared
          causal chain: low airflow with clean filters → afternoon derating →
          power-stage thermal damage and hard faults.
          ${q3.population} units at risk, ${usd(q3.warranty)} warranty recovery in play.</p>
      </div>
    </div>
    <div class="note" style="margin-top:13px">
      Same equipment family. Adjacent manufacturing windows. Opposite conclusions
      based on the evidence.
    </div>
  </div>`;
}

/* ------------------------------- DEMO MOMENT 3: a signal counting can't see */
/* No invented time series. Two evidence groups, quoted from the reports the
   finding actually cites, plus the historical set the verification named as
   boilerplate. Every quote is verbatim; every ID is clickable. */
const WASH_HIST = ['WO-2025-00810','WO-2024-00049','WO-2024-00145','WO-2024-00194'];
const WASH_RECENT = ['WO-2025-00715','WO-2025-00856','WO-2025-01057','WO-2026-00620'];

async function washPanel(d){
  const [hist, recent] = await Promise.all([
    Promise.all(WASH_HIST.map(i=>api('/api/work_order/'+i))),
    Promise.all(WASH_RECENT.map(i=>api('/api/work_order/'+i)))]);
  const cited = new Set(d.supporting_wo_ids);
  const quote = w => `
    <div style="border-left:2px solid var(--line);padding:7px 0 7px 12px;margin-bottom:11px">
      <div style="font-size:13.5px;line-height:1.6;color:var(--ink-2)">“${esc(w.narrative)}”</div>
      <div class="small muted" style="margin-top:5px">
        <button class="woid" data-wo="${w.wo_id}">${w.wo_id}</button>
        ${esc(w.date)} · ${esc(w.technician_id)}
        ${cited.has(w.wo_id)?'<span class="pill plain" style="font-size:10px;padding:1px 6px">cited</span>':''}
      </div>
    </div>`;
  return `
  <div class="panel" style="margin-bottom:14px;border-left:3px solid var(--accent)">
    <h3>How the outcome of a repeated intervention changed</h3>
    <p class="small muted" style="margin-bottom:16px">
      There is no failure cluster here to count. Nothing broke. The signal is
      that the same maintenance action stopped producing the same result — and it
      exists only in what technicians wrote down.</p>

    <div class="split">
      <div class="wo" style="border-top:3px solid var(--dec)">
        <div class="pill decline" style="margin-bottom:4px">Historical reports</div>
        <div style="font-size:19px;font-weight:660;letter-spacing:-.02em;margin:8px 0 3px">
          ~5% recovery</div>
        <div class="small muted" style="margin-bottom:14px">repeatedly reported after a wash</div>
        ${hist.map(quote).join('')}
      </div>
      <div class="wo" style="border-top:3px solid var(--esc)">
        <div class="pill escalate" style="margin-bottom:4px">Recent reports</div>
        <div style="font-size:19px;font-weight:660;letter-spacing:-.02em;margin:8px 0 3px;color:var(--esc)">
          ~1–2% recovery</div>
        <div class="small muted" style="margin-bottom:14px">re-washing did not restore it; glass reported clean</div>
        ${recent.map(quote).join('')}
      </div>
    </div>

    <div class="grid g2" style="margin-top:16px">
      <div class="note"><b>What the evidence shows.</b> Two technicians
        independently tested the obvious explanation and ruled it out: on
        <button class="woid" data-wo="WO-2025-01057">WO-2025-01057</button> the crew
        re-washed two rows in case they had rushed the job and got the same ~1%;
        on <button class="woid" data-wo="WO-2026-00620">WO-2026-00620</button> the
        technician walked the block himself and recorded clean glass. If the
        deficit were soiling, washing would have removed it.</div>
      <div class="warn"><b>What it does not show.</b> This is directional evidence
        drawn from unstructured narratives, not measured telemetry. The historical
        ~5% figure appears as repeated boilerplate across several reports
        (<button class="woid" data-wo="WO-2024-00049">WO-2024-00049</button>,
        <button class="woid" data-wo="WO-2024-00145">WO-2024-00145</button>,
        <button class="woid" data-wo="WO-2024-00194">WO-2024-00194</button>), so
        the baseline is a template default rather than an independent measurement.
        The direction is credible; the exact magnitude is not.</div>
    </div>
    <p class="small muted" style="margin-top:13px">
      Blocks are as stated in each narrative. The finding also notes that the
      structured <span class="mono">asset_id</span> field contradicts the narrative
      on several of these reports — a data-quality issue it recommends fixing.</p>
  </div>`;
}

/* ============================================================== EVIDENCE */
async function renderEvidence(){
  const f = S.findings = S.findings || await api('/api/findings');
  const sel = S.evCid || 'CAND-003';
  const d = S.detail[sel] = S.detail[sel] || await api('/api/finding/'+sel);
  $('#v-evidence').innerHTML = `
    <h2>Evidence Explorer</h2>
    <p class="lede">Every conclusion traces back to the original field report it
      came from. Select a finding, then open any work order.</p>
    <div class="panel" style="margin-bottom:16px">
      <h4>Finding</h4>
      <select id="ev-sel" style="width:100%;padding:9px 11px;border:1px solid var(--line);
        border-radius:7px;font-family:inherit;font-size:13.5px;margin-bottom:12px">
        ${f.map(x=>`<option value="${x.candidate_id}" ${x.candidate_id===sel?'selected':''}>
          [${x.verdict}] ${esc(x.candidate_id)} — ${esc(x.label.slice(0,70))}</option>`).join('')}
      </select>
      <div class="dhead"><span class="pill ${d.verdict}">${d.verdict}</span>
        <span class="small muted">${d.confidence} confidence</span></div>
      <p style="font-size:14.5px;margin-top:8px">${esc(d.headline)}</p>
    </div>
    <div class="grid g2" style="margin-bottom:14px">
      <div class="panel"><h4>Evidence supporting the finding</h4>
        <div class="chips" style="margin-bottom:11px">${d.supporting_wo_ids.map(w=>
          `<button class="woid" data-wo="${w}">${w}</button>`).join('')}</div>
        <p class="small" style="color:var(--ink-2);line-height:1.6">${linkWOs(d.reasoning)}</p></div>
      <div class="panel" style="border-left:3px solid var(--dep)">
        <h4>Evidence against the finding</h4>
        <p class="small" style="color:var(--ink-2);line-height:1.6">${linkWOs(d.contradicting)}</p></div>
    </div>
    <div class="grid g2">
      <div class="panel"><h4>Population</h4>
        <p class="small" style="color:var(--ink-2)">${esc(d.population_detail.description||'—')}</p>
        <p class="small muted" style="margin-top:7px">${esc(d.population_detail.basis||'')}</p></div>
      <div class="panel"><h4>Recommended action</h4>
        <p class="small" style="color:var(--ink-2)">${esc(d.action)}</p></div>
    </div>`;
  $('#ev-sel').onchange = e => { S.evCid = e.target.value; renderEvidence(); };
}

/* ================================================================== HOW */
function renderHow(){
  const p = S.prov;
  const step = (t,d,ai) => `<div class="step ${ai?'ai':''}">
    <div class="t">${t}</div><div class="d">${d}</div></div>`;
  $('#v-how').innerHTML = `
    <h2>How It Works</h2>
    <p class="lede">Four stages. Two of them use a model; two of them deliberately
      do not.</p>
    <div class="flow">
      ${step('2,398 technician reports','Unstructured free text, as written in the field')}
      <div class="arr">↓</div>
      ${step('Claude extraction','Interpret messy technician language into consistent fields',1)}
      <div class="arr">↓</div>
      ${step('Deterministic aggregation','Normalise by exposure and identify candidate patterns')}
      <div class="arr">↓</div>
      ${step('Claude hypothesis generation','Generate competing explanations, including benign ones',1)}
      <div class="arr">↓</div>
      ${step('Claude verification','Test findings against evidence and matched controls',1)}
      <div class="arr">↓</div>
      ${step('Business action','Escalate / deprioritize / decline')}
    </div>
    <div class="note" style="max-width:620px;margin:22px auto 0">
      Financial impact is deterministic, not model-generated. The model supplies
      quantities — units, hours, MWh. Code applies costs from stated assumptions.
    </div>
    <details class="panel" style="max-width:620px;margin:16px auto 0">
      <summary style="cursor:pointer;font-weight:600;font-size:14px">Technical details</summary>
      <dl class="kv">
        <dt>Model</dt><dd class="mono">${esc(p.model)}</dd>
        <dt>Extraction calls</dt><dd>one per work order, with a deterministic
          regex pre-pass for serials and firmware strings</dd>
        <dt>Aggregation</dt><dd>no model calls; exposure-normalised throughout,
          joined to a serial-level asset registry</dd>
        <dt>Verification</dt><dd>matched controls by site, equipment and season;
          a cluster may be declined</dd>
        <dt>Cost of this analysis</dt><dd>${usd(p.findings_cost_usd)}</dd>
      </dl>
    </details>`;
}

/* =============================================================== DRAWER */
async function openWO(id){
  const w = await api('/api/work_order/' + id);
  const dr = $('#drawer');
  if(w.error){ dr.innerHTML = '<p>Unknown work order.</p>'; }
  else dr.innerHTML = `
    <button class="x" id="dx">×</button>
    <div class="pill plain" style="margin-bottom:9px">Original field report</div>
    <h3 class="mono" style="font-size:15px">${esc(w.wo_id)}</h3>
    <dl class="kv">
      <dt>Site</dt><dd>${esc(w.site)}</dd>
      <dt>Opened</dt><dd>${esc(w.date)}</dd>
      <dt>Closed</dt><dd>${esc(w.date_closed||'—')}</dd>
      <dt>Type</dt><dd>${esc(w.type||'—')} · priority ${esc(w.priority||'—')}</dd>
      <dt>Asset</dt><dd class="mono">${esc(w.asset_id||'—')}</dd>
      <dt>Equipment</dt><dd>${esc([w.asset_manufacturer,w.asset_model].filter(Boolean).join(' ')||'—')}</dd>
      <dt>Technician</dt><dd>${esc(w.technician_id||'—')}</dd>
      <dt>Labour</dt><dd>${w.labor_hours ?? '—'} h</dd>
      <dt>Parts</dt><dd>${esc(w.parts_used || 'none recorded')}</dd>
      <dt>Resolution</dt><dd>${esc(w.resolution_code||'—')}</dd>
      <dt>Lost production</dt><dd>${w.lost_mwh ? w.lost_mwh+' MWh' : 'none recorded'}</dd>
    </dl>
    <h4>Technician narrative</h4>
    <div class="nar" style="font-size:14px;line-height:1.65;background:var(--bg);
      border:1px solid var(--line-2);border-radius:7px;padding:14px">${esc(w.narrative)}</div>`;
  dr.classList.add('on'); $('#scrim').classList.add('on');
  const close = () => { dr.classList.remove('on'); $('#scrim').classList.remove('on'); };
  const x = $('#dx'); if(x) x.onclick = close;
  $('#scrim').onclick = close;
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-wo]');
  if(b){ e.stopPropagation(); openWO(b.dataset.wo); }
});
document.addEventListener('keydown', e => {
  if(e.key === 'Escape'){ $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); }
});

/* =========================================================== DEMO STRIP */
const DEMO = [
  ['Fleet overview','#/overview'], ['Baseline ranking','#/baseline'],
  ['24Q2 decline','#/finding/CAND-003'], ['24Q3 escalation','#/finding/CAND-006'],
  ['Caprock wash','#/finding/CAND-017'], ['Evidence','#/evidence'],
  ['How it works','#/how']];
/* Demo Mode survives a refresh. Without this the strip vanishes on reload,
   which on a hosted site means anyone who refreshes mid-walkthrough loses it.
   sessionStorage is per-tab and needs no cleanup. Guarded because some
   browsers throw on storage access. */
const demoStore = {
  get(){ try { return JSON.parse(sessionStorage.getItem('fi.demo') || 'null'); }
         catch(e){ return null; } },
  set(v){ try { sessionStorage.setItem('fi.demo', JSON.stringify(v)); }
          catch(e){ /* private mode: demo mode simply will not persist */ } },
};
const _saved = demoStore.get() || {};
let demoOn = !!_saved.on, demoAt = _saved.at || 0;

function paintStrip(){
  $('#strip-steps').innerHTML = DEMO.map((d,i)=>
    `<span class="s ${i===demoAt?'on':''}" data-i="${i}">${i+1}. ${d[0]}</span>`).join('');
  $$('#strip-steps .s').forEach(s => s.onclick = () => {
    demoAt = +s.dataset.i; location.hash = DEMO[demoAt][1];
    demoStore.set({on: demoOn, at: demoAt}); paintStrip(); });
}
function setDemo(on){
  demoOn = on;
  document.body.classList.toggle('demo', on);
  $('#strip').classList.toggle('on', on);
  demoStore.set({on: on, at: demoAt});
  if(on) paintStrip();
}
$('#strip-next').onclick = () => { demoAt = Math.min(demoAt+1, DEMO.length-1);
  location.hash = DEMO[demoAt][1]; demoStore.set({on:demoOn, at:demoAt}); paintStrip(); };
$('#strip-prev').onclick = () => { demoAt = Math.max(demoAt-1, 0);
  location.hash = DEMO[demoAt][1]; demoStore.set({on:demoOn, at:demoAt}); paintStrip(); };
$('#strip-off').onclick = () => setDemo(false);
document.addEventListener('keydown', e => {
  if(e.key.toLowerCase() === 'd' && e.shiftKey) setDemo(!demoOn);
});

/* ================================================================ ROUTER */
async function route(){
  const h = location.hash || '#/overview';
  if(!S.overview) { S.overview = await api('/api/overview'); S.prov = await api('/api/provenance'); }
  const show = id => { $$('.view').forEach(v=>v.classList.remove('on'));
                       $('#v-'+id).classList.add('on'); };
  const mark = base => $$('#nav a').forEach(a =>
    a.classList.toggle('on', a.getAttribute('href') === base));

  if(h.startsWith('#/finding/')){
    show('findings'); mark('#/findings');
    await renderDetail(h.split('/')[2]);
  } else if(h.startsWith('#/baseline')){ show('baseline'); mark('#/baseline'); await renderBaseline(); }
  else if(h.startsWith('#/findings')){ show('findings'); mark('#/findings'); await renderFindings(); }
  else if(h.startsWith('#/evidence')){ show('evidence'); mark('#/evidence'); await renderEvidence(); }
  else if(h.startsWith('#/how')){ show('how'); mark('#/how'); renderHow(); }
  else { show('overview'); mark('#/overview'); await renderOverview(); }
  window.scrollTo(0,0);
}
window.addEventListener('hashchange', route);
if(demoOn) setDemo(true);          // restore the strip after a refresh
route();
