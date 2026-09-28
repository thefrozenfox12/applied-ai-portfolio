// End-to-end upload check using a local simulated model, never a paid provider.
const fs=require('fs'),path=require('path'),assert=require('assert'),{spawn}=require('child_process'),readline=require('readline');
let pw;try{pw=require('playwright')}catch{pw=require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+'/playwright')}
(async()=>{
 const fixture=spawn(process.env.PYTHON||'python',['test_support/upload_fixture.py'],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
 let browser;let checks=0;
 try{
  const url=await new Promise((resolve,reject)=>{const lines=readline.createInterface({input:fixture.stdout});lines.once('line',line=>resolve(JSON.parse(line).url));fixture.once('error',reject);fixture.once('exit',code=>reject(Error('Fixture exited '+code)));});
  browser=await pw.chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url+'/dashboard.html');
  await page.click('#uploadReviews');await page.waitForURL(url+'/upload.html');checks++;
  assert(await page.locator('#classify').isDisabled());checks++;
  await page.fill('#accessToken','wrong');await page.click('#connectForm button');await page.waitForFunction(()=>document.getElementById('connectionStatus').textContent.includes('valid'));checks++;
  await page.fill('#accessToken','test-token-for-local-tests-only-12345');await page.click('#connectForm button');await page.waitForFunction(()=>document.getElementById('connectPanel').hidden);checks++;
  await page.locator('#file').setInputFiles({name:'headphones.csv',mimeType:'text/csv',buffer:Buffer.from('headline,body,rating,product\nFive Stars,"Great sound, clear calls",1,secret-product\nBroke,"Broken after two days",5,secret-product\nDetails,"Factual description",3,secret-product\n')});
  await page.selectOption('#titleColumn','headline');await page.fill('#productName','Headphones');assert.equal(await page.locator('#mode').inputValue(),'binary');checks++;
  await page.screenshot({path:path.join(__dirname,'assets/upload-workspace.png'),fullPage:true});
  await page.click('#classify');await page.waitForFunction(()=>document.getElementById('batchStatus').textContent.endsWith('Complete'),{},{timeout:15000});
  assert.deepEqual(await page.locator('#summary .kpi-value').allTextContents(),['3','2','1','0']);checks++;
  await page.selectOption('#sentiment','NEGATIVE');assert.equal(await page.locator('#rows tr').count(),1);checks++;
  const downloadPromise=page.waitForEvent('download');await page.click('#export');const download=await downloadPromise;const csv=fs.readFileSync(await download.path(),'utf8');assert(csv.includes('POSITIVE')&&csv.includes('NEGATIVE'));checks++;
  await page.selectOption('#mode','three_class');await page.click('#classify');await page.waitForFunction(()=>document.getElementById('batchStatus').textContent.startsWith('Three-class')&&document.getElementById('batchStatus').textContent.endsWith('Complete'),{},{timeout:15000});
  assert.deepEqual(await page.locator('#summary .kpi-value').allTextContents(),['3','1','1','1','0']);checks++;
  const requests=await (await page.request.get(url+'/__test_requests')).json();assert.equal(requests.length,6);checks++;
  for(const r of requests){assert.equal(r.messages.length,2);const input=JSON.parse(r.messages[1].content);assert.deepEqual(Object.keys(input).sort(),['text','title']);assert(!JSON.stringify(input).includes('secret-product'));assert(!input.title.includes('Five Stars'));checks+=4;}
  await page.locator('#file').setInputFiles({name:'fail.csv',mimeType:'text/csv',buffer:Buffer.from('text\nFAIL_TEST\n')});await page.click('#classify');await page.waitForFunction(()=>document.getElementById('batchStatus').textContent.includes('1 failed'),{},{timeout:20000});assert.equal(await page.locator('#rows .badge').count(),0);checks++;
  await page.locator('#file').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from('text,text\na,b\n')});await page.waitForFunction(()=>document.getElementById('uploadError').textContent.includes('unique'));assert(await page.locator('#classify').isDisabled());checks++;
  await page.setViewportSize({width:390,height:844});assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));checks++;
  assert.deepEqual(errors,[]);checks++;
  fs.writeFileSync(path.join(__dirname,'results/upload_checks.json'),JSON.stringify({passed:true,checks,provider:'local simulated endpoint',real_provider_tested:false,js_errors:errors},null,2));
  console.log(`${checks} upload browser assertions passed against a simulated provider; no JavaScript errors.`);
 }finally{if(browser)await browser.close();fixture.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
