import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRun,reduceEvent} from '../static/model.js';
test('replay pairs tool results, nests agent events, and preserves metrics',()=>{
  const run=createRun('demo','replay');
  for(const line of fs.readFileSync(new URL('../fixtures/tree.jsonl',import.meta.url),'utf8').trim().split('\n'))reduceEvent(run,JSON.parse(line));
  assert.equal(run.status,'finished');assert.equal(run.session,'replay-session');
  assert.equal(run.tools.get('before').status,'error');
  assert.equal(run.tools.get('after').status,'success');
  assert.ok(run.tools.get('survey').children.some(x=>x.id==='subread'));
  assert.ok(!run.roots.some(x=>x.id==='subread'));
  assert.equal(run.metrics.cost,.0234);
});
test('children arriving before parent remain attached',()=>{
  const run=createRun('','replay');
  reduceEvent(run,{type:'assistant',parent_tool_use_id:'parent',message:{content:[{type:'text',text:'child'}]}});
  reduceEvent(run,{type:'assistant',message:{content:[{type:'tool_use',id:'parent',name:'Agent',input:{}}]}});
  assert.equal(run.roots.length,1);assert.equal(run.tools.get('parent').children[0].text,'child');
});
test('failure and unresolved tool are distinct',()=>{
  const run=createRun('','replay');
  reduceEvent(run,{type:'assistant',message:{content:[{type:'tool_use',id:'a',name:'Read',input:{}}]}});
  assert.equal(run.tools.get('a').status,'pending');
  reduceEvent(run,{type:'result',subtype:'error_during_execution',is_error:true,errors:['broken']});
  assert.equal(run.status,'failed');assert.equal(run.error,'broken');assert.equal(run.tools.get('a').status,'incomplete');
});
