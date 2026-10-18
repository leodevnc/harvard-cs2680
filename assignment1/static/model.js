/* Pure event reducer, shared by browser and Node tests. */
export function createRun(prompt, mode) {
  return {prompt, mode, status:'running', roots:[], tools:new Map(), groups:new Map(), session:null, metrics:null, warnings:[]};
}
function container(run, parent) {
  if (!parent) return run.roots;
  if (run.tools.has(parent)) return run.tools.get(parent).children;
  if (!run.groups.has(parent)) {
    const group = {kind:'group', id:parent, name:'Subagent', children:[]};
    run.groups.set(parent, group); run.roots.push(group);
  }
  return run.groups.get(parent).children;
}
export function reduceEvent(run, e) {
  if (e.session_id) run.session = e.session_id;
  if (e.type === 'lens_error') { run.status='failed'; run.error=e.message; }
  if (e.type === 'lens_warning') run.warnings.push(e.message);
  if (e.type === 'result') {
    run.status = e.is_error || e.subtype !== 'success' ? 'failed' : 'finished';
    run.metrics = {cost:e.total_cost_usd, duration:e.duration_ms, turns:e.num_turns};
    if (run.status === 'failed') run.error = e.errors?.join('\n') || e.result || e.subtype;
    // A tool without a result must never look successful.
    for (const t of run.tools.values()) if (t.status === 'pending') t.status='incomplete';
  }
  if (!['assistant','user'].includes(e.type)) return run;
  const blocks = e.message?.content;
  if (!Array.isArray(blocks)) return run;
  for (const b of blocks) {
    if (b.type === 'text') container(run,e.parent_tool_use_id).push({kind:'text', text:b.text, role:e.type});
    if (b.type === 'tool_use') {
      if (run.tools.has(b.id)) continue;
      const t={kind:'tool', id:b.id, name:b.name, input:b.input, status:'pending', children:[]};
      run.tools.set(b.id,t);
      const orphan=run.groups.get(b.id);
      if (orphan) {
        t.children=orphan.children;
        run.roots=run.roots.filter(x=>x!==orphan);
        run.groups.delete(b.id);
      }
      container(run,e.parent_tool_use_id).push(t);
    }
    if (b.type === 'tool_result') {
      let t=run.tools.get(b.tool_use_id);
      if (!t) {
        t={kind:'tool', id:b.tool_use_id, name:'Unknown tool', input:{}, children:[]};
        run.tools.set(t.id,t); container(run,e.parent_tool_use_id).push(t);
      }
      t.output=typeof b.content==='string'?b.content:JSON.stringify(b.content,null,2);
      t.status=b.is_error?'error':'success';
    }
  }
  return run;
}
