import {createRun,reduceEvent} from './model.js';
const $=s=>document.querySelector(s), runs=[], raw=[];
let session=null, busy=false;
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Small, HTML-disabled Markdown renderer: fences, headings, lists, emphasis, inline code.
function markdown(text) {
  return String(text).split(/```[^\n]*\n([\s\S]*?)```/g).map((part,i)=> {
    if(i%2) return `<pre><code>${escape(part)}</code></pre>`;
    return escape(part).split('\n').map(line=> {
      const t=line.replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
      if(/^#{1,3} /.test(t)) return `<h3>${t.replace(/^#+ /,'')}</h3>`;
      if(/^[-*] /.test(t)) return `<div>• ${t.slice(2)}</div>`;
      return `<div>${t||'<br>'}</div>`;
    }).join('');
  }).join('');
}
const labels={pending:'진행 중',success:'성공',error:'오류',incomplete:'결과 없음',running:'실행 중',finished:'완료',failed:'실패'};
function badge(status){return `<span class="badge ${status}">${labels[status]||escape(status)}</span>`;}
function node(n,prefix){
  if(n.kind==='text')return `<div class="message">${markdown(n.text)}</div>`;
  const id=prefix+'-'+n.id;
  if(n.kind==='group')return `<details class="children" data-key="${escape(id)}" open><summary>서브에이전트 · ${escape(n.id)}</summary>${n.children.map(x=>node(x,prefix)).join('')}</details>`;
  let output='';
  if(n.output!==undefined){
    const preview=n.output.length>1000?n.output.slice(0,1000)+'\n…':n.output;
    output=`<pre>${escape(preview)}</pre>`;
    if(n.output.length>1000)output+=`<details data-key="${escape(id)}-output"><summary>전체 결과 보기 · ${n.output.length.toLocaleString()}자</summary><pre>${escape(n.output)}</pre></details>`;
  }
  return `<article class="tool" id="${escape(id)}"><div class="tool-head"><span>↳</span><strong>${escape(n.name)}</strong>${badge(n.status)}</div><details data-key="${escape(id)}-input"><summary>입력 인자</summary><pre>${escape(JSON.stringify(n.input,null,2))}</pre></details>${output}${n.children.length?`<details class="children" data-key="${escape(id)}-children" open><summary>서브에이전트 · ${n.children.length}개 이벤트</summary>${n.children.map(x=>node(x,prefix)).join('')}</details>`:''}</article>`;
}
function render(){
  const states=new Map([...document.querySelectorAll('details[data-key]')].map(d=>[d.dataset.key,d.open]));
  $('#runs').innerHTML=runs.map((r,i)=>`<section class="run"><div class="run-head"><strong>${escape(r.prompt)}</strong><span class="mode-tag">${r.mode==='live'?'LIVE':'SYNTHETIC REPLAY'}</span>${badge(r.status)}</div><div class="events">${r.roots.map(n=>node(n,'r'+i)).join('')}${r.warnings.map(w=>`<p class="warning">${escape(w)}</p>`).join('')}</div>${r.error?`<div class="run-error">${escape(r.error)}</div>`:''}${r.metrics?`<div class="metrics"><span>보고 비용 $${Number(r.metrics.cost||0).toFixed(4)}</span><span>${((r.metrics.duration||0)/1000).toFixed(2)}s</span><span>${r.metrics.turns??'—'} turns</span></div>`:''}</section>`).join('');
  document.querySelectorAll('details[data-key]').forEach(d=>{if(states.has(d.dataset.key))d.open=states.get(d.dataset.key);});
  $('#outline').innerHTML=runs.map((r,i)=>`<div class="outline-label">RUN ${String(i+1).padStart(2,'0')}</div>`+[...r.tools.values()].map(t=>`<a class="outline-link" href="#${escape('r'+i+'-'+t.id)}">${escape(t.name)} <small>· ${labels[t.status]}</small></a>`).join('')).join('');
  $('#session').textContent=session?'SESSION / '+session:'새 대화';
}
function setBusy(value){busy=value;for(const id of ['submit','new','mode','cwd'])$('#'+id).disabled=value;$('#stop').disabled=!value;}
async function api(path,body){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Mads-Lens':'1'},body:JSON.stringify(body)});}
$('#composer').addEventListener('submit',async ev=>{
  ev.preventDefault();if(busy)return;
  $('#error').textContent='';
  const r=createRun($('#prompt').value,$('#mode').value);runs.push(r);setBusy(true);render();
  try{
    const response=await api('/api/run',{prompt:r.prompt,mode:r.mode,cwd:$('#cwd').value,session_id:session});
    if(!response.ok)throw new Error((await response.json()).error);
    const reader=response.body.getReader(), decoder=new TextDecoder();let pending='';
    function accept(line){if(!line.trim())return;const e=JSON.parse(line);raw.push(e);reduceEvent(r,e);if(r.session)session=r.session;render();}
    while(true){const {value,done}=await reader.read();if(done)break;pending+=decoder.decode(value,{stream:true});let end;while((end=pending.indexOf('\n'))>=0){accept(pending.slice(0,end));pending=pending.slice(end+1);}}
    pending+=decoder.decode();accept(pending);
    if(r.status==='running')throw new Error('최종 결과를 받기 전에 연결이 종료되었습니다.');
  }catch(e){r.status='failed';r.error=e.message;$('#error').textContent=e.message;}
  finally{for(const t of r.tools.values())if(t.status==='pending')t.status='incomplete';setBusy(false);render();}
});
$('#stop').onclick=async()=>{try{const res=await api('/api/stop',{});if(!res.ok)throw new Error('중단 요청 실패');}catch(e){$('#error').textContent=e.message;}};
$('#new').onclick=()=>{session=null;render();};
for(const id of ['mode','cwd'])$('#'+id).addEventListener('change',()=>{session=null;$('#session').textContent='새 대화';$('#hint').textContent=$('#mode').value==='live'?'CLI 로그인으로 실행합니다. 허용된 도구는 자동 승인됩니다.':'재생 모드에서는 입력 내용과 관계없이 같은 합성 예시를 보여줍니다.';});
$('#export').onclick=()=>{const url=URL.createObjectURL(new Blob([raw.map(e=>JSON.stringify(e)).join('\n')+'\n'],{type:'application/x-ndjson'}));const a=document.createElement('a');a.href=url;a.download='mads-lens-events.jsonl';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
fetch('/api/config').then(r=>r.json()).then(c=>$('#workspace').textContent='WORKSPACE / '+c.workspace).catch(e=>$('#error').textContent=e.message);
