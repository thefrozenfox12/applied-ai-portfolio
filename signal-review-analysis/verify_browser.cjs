// Optional development check: npm install --no-save playwright; npx playwright install chromium
const fs=require('fs'),path=require('path'),assert=require('assert');
let pw;try{pw=require('playwright')}catch{pw=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright')}
(async()=>{
 const browser=await pw.chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1});const errors=[];let external=0;
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))external++});
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('file://'+path.join(__dirname,'dashboard.html'));
 let checks=0;
 assert(!(await page.locator('#analystView').isVisible()));checks++;
 assert(await page.locator('#overview').isVisible());checks++;
 assert(await page.locator('#qualityAccuracy').isVisible());checks++;
 assert(await page.locator('#binaryBtn').isVisible());checks++;
 assert.equal(await page.locator('#binaryBtn').getAttribute('aria-pressed'),'true');checks++;
 await page.click('#threeBtn');assert((await page.locator('#customerScope').textContent()).startsWith('150 reviews'));checks++;
 await page.click('#binaryBtn');assert((await page.locator('#customerScope').textContent()).startsWith('100 reviews'));checks++;
 assert.deepEqual(await page.locator('#predicted option').allTextContents(),['All classes','Positive','Negative']);checks++;
 await page.click('#uploadReviews');assert(await page.locator('#detail').isVisible());checks++;await page.keyboard.press('Escape');
 assert(!/assignment|saved results/i.test(await page.locator('body').innerText()));checks++;
 const defaultRun=JSON.parse(fs.readFileSync(path.join(__dirname,'results/binary.json'),'utf8'));
 const counts=await page.locator('#customerKpis .kpi-value').allTextContents();
 assert.deepEqual(counts.map(Number),[100,...defaultRun.metrics.labels.map(c=>defaultRun.metrics.per_class[c].predicted)]);checks++;
 const initialText=await page.locator('body').innerText();
 for(const technical of ['Macro F1','Confusion matrix','NRC maximum-score ties','bootstrap']){assert(!initialText.includes(technical),'Technical detail leaked into customer view: '+technical);checks++;}
 await page.click('#negativeReviews');assert((await page.locator('#liveCount').textContent()).startsWith(`${defaultRun.metrics.per_class.NEGATIVE.predicted} of 100`));checks++;
 assert(!(await page.locator('#actual').isVisible()));checks++;
 await page.click('#reset');await page.locator('[data-emotion="anger"]').click();
 assert((await page.locator('#liveCount').textContent()).startsWith(`${defaultRun.emotion_metrics.llm_counts.anger} of 100`));checks++;
 await page.click('#reset');await page.locator('#reviewRows [data-review]').first().click();
 assert.equal(await page.locator('#detailContent > details[open]').count(),0);checks++;
 await page.keyboard.press('Escape');
 await page.check('#showBenchmark');assert(await page.locator('#actual').isVisible());checks++;
 await page.uncheck('#showBenchmark');assert(!(await page.locator('#actual').isVisible()));checks++;
 await page.click('#analystViewBtn');assert(await page.locator('#analystView').isVisible());checks++;

 const analysis=JSON.parse(fs.readFileSync(path.join(__dirname,'results/analysis.json'),'utf8'));
 for(const [mode,sample,name] of [['three_class','reference','three_class'],['binary','reference','binary'],['binary','three_class','binary_balanced'],['three_class','binary','three_class_first100']]){
  await page.selectOption('#sampleDesign',sample);
  await page.click(mode==='binary'?'#binaryBtn':'#threeBtn');
  assert(!/assignment/i.test(await page.locator('body').innerText()));checks++;
  const r=JSON.parse(fs.readFileSync(path.join(__dirname,`results/${name}.json`),'utf8'));const m=r.metrics;assert.deepEqual((await page.locator('#customerKpis .kpi-value').allTextContents()).map(Number),[m.n,...m.labels.map(c=>m.per_class[c].predicted)]);checks++;const ev=analysis.runs[name];const u=ev.uncertainty;const range=v=>(100*v.low).toFixed(1)+'%–'+(100*v.high).toFixed(1)+'%';
  assert.equal(await page.locator('#qualityAccuracy').textContent(),(100*m.accuracy).toFixed(1)+'%');checks++;
  assert.equal(await page.locator('#qualityBaseline').textContent(),(100*m.majority_baseline).toFixed(1)+'%');checks++;
  assert.deepEqual(await page.locator('#qualityClasses b').allTextContents(),m.labels.map(c=>`${m.per_class[c].correct} / ${m.per_class[c].support}`));checks++;
  assert.equal(await page.locator('#accuracy').textContent(),(100*m.accuracy).toFixed(1)+'%');checks++;
  assert.equal(await page.locator('#balanced').textContent(),(100*m.balanced_accuracy).toFixed(1)+'%');checks++;
  assert.equal(await page.locator('#f1').textContent(),m.macro_f1.toFixed(3));checks++;
  assert.equal(await page.locator('#baseline').textContent(),(100*m.majority_baseline).toFixed(1)+'%');checks++;
  const cells=await page.locator('#matrix button').evaluateAll(xs=>xs.map(x=>Number(x.firstChild.textContent)));assert.deepEqual(cells,m.matrix.flat());checks++;
  const metrics=await page.locator('#classMetrics tbody tr').evaluateAll(rows=>rows.map(row=>[...row.cells].map(c=>c.textContent)));
  assert.deepEqual(metrics,m.labels.map(c=>{let p=m.per_class[c];return [c.charAt(0)+c.slice(1).toLowerCase(),String(p.support),String(p.predicted),String(p.correct),(100*p.precision).toFixed(1)+'%',(100*p.recall).toFixed(1)+'%',u.available?range(u.intervals[c+'.recall']):'Not inferred',p.f1.toFixed(3)]}));checks++;
  assert.equal(await page.locator('#topSet').textContent(),ev.emotion_sensitivity.top_set_count+'/'+ev.emotion_sensitivity.signal_n);checks++;
  assert.equal(await page.locator('#exactSignal').textContent(),ev.emotion_sensitivity.exact_signal_count+'/'+ev.emotion_sensitivity.signal_n);checks++;
  assert.equal(await page.locator('#accuracyInterval').textContent(),u.available?'95% interval: '+range(u.intervals.accuracy):'Ordered sample · no population interval');checks++;
  assert.equal(await page.locator('#nrcTies').textContent(),String(r.emotion_metrics.ties));checks++;
  assert.equal(await page.locator('#nrcNone').textContent(),String(r.emotion_metrics.no_signal));checks++;
  const emotions=['joy','trust','anticipation','surprise','sadness','anger','fear','disgust','none'];
  assert.deepEqual(await page.locator('#emotionBars .paired-nums').allTextContents(),emotions.map(e=>(r.emotion_metrics.llm_counts[e]||0)+' / '+(r.emotion_metrics.nrc_counts[e]||0)));checks++;
  for(let i=0;i<m.labels.length;i++)for(let j=0;j<m.labels.length;j++){
   await page.locator(`#matrix button[data-actual="${m.labels[i]}"][data-predicted="${m.labels[j]}"]`).click();
   assert((await page.locator('#liveCount').textContent()).startsWith(`${m.matrix[i][j]} of ${m.n}`));checks++;
  }
  await page.click('#reset');await page.selectOption('#outcome','mismatch');
  assert((await page.locator('#liveCount').textContent()).startsWith(`${m.mismatches} of`));checks++;
  await page.fill('#search','zzzznotareviewzzz');assert.equal(await page.locator('#reviewRows .empty').count(),1);checks++;
  await page.click('#reset');await page.fill('#search',r.rows[0].title);
  const expected=r.rows.filter(x=>(x.title+' '+x.text).toLowerCase().includes(r.rows[0].title.toLowerCase())).length;
  assert((await page.locator('#liveCount').textContent()).startsWith(`${expected} of`));checks++;
  await page.click('#reset');await page.locator('#reviewRows [data-review]').first().click();assert(await page.locator('#detail').isVisible());
  assert.equal(await page.locator('#detailTitle').textContent(),r.rows[0].title||'(Untitled review)');checks++;
  await page.keyboard.press('Escape');assert(!(await page.locator('#detail').isVisible()));checks++;
  await page.click('#next');assert((await page.locator('#pageLabel').textContent()).startsWith('11–20'));checks++;
  await page.click('#prev');
  const dist=await page.locator('#distribution .num').allTextContents();assert.deepEqual(dist.map(x=>Number(x.replaceAll(',',''))),[5,4,3,2,1].map(s=>r.rows.filter(x=>x.rating===s).length));checks++;
  assert.equal(await page.locator('#emotionAgree').textContent(),(100*r.emotion_metrics.agreement_rate).toFixed(1)+'%');checks++;
 }
 await page.selectOption('#sampleDesign','reference');await page.click('#threeBtn');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(__dirname,'assets/validation-overview.png')});
 await page.click('#binaryBtn');await page.click('#customerViewBtn');await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(__dirname,'assets/dashboard-desktop.png')});
 await page.evaluate(()=>document.getElementById('explorer').scrollIntoView({block:'start'}));await page.screenshot({path:path.join(__dirname,'assets/review-explorer.png')});
 await page.click('#analystViewBtn');
 await page.locator('#comparison details summary').click();
 for(const sample of ['first100','balanced150']){
  await page.selectOption('#pairSample',sample);
  const values=await page.locator('#pairedMatrix tbody td').allTextContents();
  assert.deepEqual(values.map(Number),analysis.paired[sample].prediction_transitions.flat());checks++;
 }
 const comparisonValues=await page.locator('.experiment-card strong').allTextContents();
 assert.deepEqual(comparisonValues,['binary','three_class_first100','binary_balanced','three_class'].map(n=>(100*analysis.runs[n].metrics.accuracy).toFixed(1)+'%'));checks++;
 await page.evaluate(()=>document.getElementById('comparison').scrollIntoView({block:'start'}));await page.screenshot({path:path.join(__dirname,'assets/experiment-comparison.png')});
 await page.locator('#comparison details summary').click();
 await page.evaluate(()=>document.getElementById('emotions').scrollIntoView({block:'start'}));await page.screenshot({path:path.join(__dirname,'assets/emotion-analysis.png')});
 const downloadEvent=page.waitForEvent('download');await page.click('#export');const d=await downloadEvent;assert(d.suggestedFilename().endsWith('.csv'));checks++;
 await page.click('#customerViewBtn');
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert(!overflow,'Mobile page overflow');checks++;
 await page.screenshot({path:path.join(__dirname,'assets/dashboard-mobile.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:1080});await page.evaluate(()=>window.scrollTo(0,0));
 await page.click('#analystViewBtn');
 const widths=await page.locator('#distribution .fill').evaluateAll(xs=>xs.map(x=>x.getBoundingClientRect().width));assert(widths.every(x=>x>0),'A nonzero rating bar collapsed');checks++;
 assert.equal(external,0,'Dashboard made external requests');assert.deepEqual(errors,[]);checks+=2;
 const preview=await browser.newPage();let escapedPreview=0;
 await preview.route('**/*',route=>{if(route.request().url()==='https://preview.example/reference.html')return route.fulfill({status:200,contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'dashboard.html'),'utf8')});escapedPreview++;return route.abort();});
 await preview.goto('https://preview.example/reference.html');await preview.click('#uploadReviews');
 assert.equal(preview.url(),'https://preview.example/reference.html');checks++;
 assert(await preview.locator('#detail').isVisible());checks++;
 assert.equal(escapedPreview,0,'Preview tried to navigate to an unavailable upload page');checks++;
 await preview.close();
 fs.writeFileSync(path.join(__dirname,'results/browser_checks.json'),JSON.stringify({checks,passed:true,external_requests:external,js_errors:errors,viewports:[[1440,1080],[390,844]]},null,2));
 console.log(`${checks} browser assertions passed; no external requests or JavaScript errors.`);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
