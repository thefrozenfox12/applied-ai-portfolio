'use strict';
const $=id=>document.getElementById(id),esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let accessToken='',connected=false,csvText='',table=[],job=null,timer=null,page=0,busy=false;
const labels=mode=>mode==='binary'?['POSITIVE','NEGATIVE']:['POSITIVE','NEUTRAL','NEGATIVE'];
const title=s=>s.charAt(0).toUpperCase()+s.slice(1).toLowerCase();
function parseCSV(text){
 const rows=[];let row=[],field='',quoted=false,afterQuote=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(quoted){if(c==='"'){if(text[i+1]==='"'){field+='"';i++;}else{quoted=false;afterQuote=true;}}else field+=c;continue;}
  if(c==='"'){if(field||afterQuote)throw Error('Check the quotation marks in your CSV.');quoted=true;continue;}
  if(c===','||c==='\n'||c==='\r'){
   row.push(field);field='';afterQuote=false;
   if(c!==','){if(c==='\r'&&text[i+1]==='\n')i++;if(row.some(v=>v!==''))rows.push(row);row=[];}continue;
  }
  if(afterQuote)throw Error('Unexpected characters after a quoted CSV value.');field+=c;
 }
 if(quoted)throw Error('A quoted CSV value is not closed.');
 if(field||row.length||afterQuote){row.push(field);rows.push(row);}
 if(rows.length<2)throw Error('Include a header row and at least one review.');
 const headers=rows[0];if(headers.some(h=>!h.trim())||new Set(headers).size!==headers.length)throw Error('Column names must be nonempty and unique.');
 if(rows.some(r=>r.length!==headers.length))throw Error('Every row must have the same number of columns.');
 if(rows.length>501)throw Error('Upload at most 500 reviews per batch.');return rows;
}
async function api(path,options={}){
 const response=await fetch(path,{...options,headers:{'Content-Type':'application/json','Authorization':'Bearer '+accessToken},cache:'no-store'});
 const data=await response.json();if(!response.ok){const error=Error(data.error||'The server could not complete this request.');error.status=response.status;throw error;}return data;
}
function updateButton(){$('classify').disabled=!connected||!table.length||busy;}
function preview(){
 if(!table.length)return;
 const ti=table[0].indexOf($('textColumn').value),hi=table[0].indexOf($('titleColumn').value);
 $('preview').innerHTML=table.slice(1,3).map(row=>`<div><strong>${esc(hi>=0?row[hi]:'Review')}</strong><p>${esc(row[ti])}</p></div>`).join('');
}
$('connectForm').onsubmit=async event=>{
 event.preventDefault();accessToken=$('accessToken').value.trim();connected=false;updateButton();
 try{const config=await api('/api/config');if(!config.ready)throw Error(config.message);connected=true;$('accessToken').value='';$('connectionStatus').textContent='Connected';$('connectPanel').hidden=true;
  const previous=sessionStorage.getItem('signalJob');if(previous){busy=true;await poll(previous);}
 }catch(error){$('connectionStatus').textContent=error.message;}
 updateButton();
};
$('file').onchange=async()=>{
 table=[];csvText='';$('mapping').hidden=true;$('uploadError').textContent='';updateButton();const file=$('file').files[0];if(!file)return;
 try{if(file.size>2*1024*1024)throw Error('Choose a CSV smaller than 2 MB.');csvText=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer()).replace(/^\uFEFF/,'');table=parseCSV(csvText);
  const opts=table[0].map(h=>`<option value="${esc(h)}">${esc(h)}</option>`).join('');$('textColumn').innerHTML=opts;$('titleColumn').innerHTML='<option value="">No title column</option>'+opts;
  const guess=table[0].find(h=>['text','review','review_text','content','body'].includes(h.toLowerCase()));if(guess)$('textColumn').value=guess;
  const header=table[0].find(h=>['title','review_title','summary'].includes(h.toLowerCase()));if(header&&header!==$('textColumn').value)$('titleColumn').value=header;
  $('mapping').hidden=false;$('fileSummary').textContent=`${table.length-1} reviews · Preview of first ${Math.min(2,table.length-1)}`;preview();
 }catch(error){table=[];$('uploadError').textContent=error.message;}updateButton();
};
$('textColumn').onchange=preview;$('titleColumn').onchange=preview;
$('uploadForm').onsubmit=async event=>{
 event.preventDefault();if(!connected||busy||!table.length)return;$('uploadError').textContent='';busy=true;updateButton();
 try{const created=await api('/api/jobs',{method:'POST',body:JSON.stringify({name:$('productName').value,mode:$('mode').value,csv:csvText,text_column:$('textColumn').value,title_column:$('titleColumn').value})});
  sessionStorage.setItem('signalJob',created.id);page=0;$('search').value='';$('resultStatus').value='all';$('sentiment').innerHTML='<option value="all">All sentiments</option>';await poll(created.id);
 }catch(error){$('uploadError').textContent=error.message;busy=false;updateButton();}
};
async function poll(id){
 clearTimeout(timer);$('resume').hidden=true;
 try{job=await api('/api/jobs/'+encodeURIComponent(id));busy=['queued','running'].includes(job.status);render();updateButton();if(busy)timer=setTimeout(()=>poll(id),1500);}
 catch(error){$('batch').hidden=false;$('batchStatus').textContent=error.message;if(error.status===404){sessionStorage.removeItem('signalJob');busy=false;updateButton();}else{$('resume').hidden=false;$('resume').onclick=()=>poll(id);}}
}
function render(){
 $('batch').hidden=false;$('batchName').textContent=job.name;
 const failed=job.rows.filter(r=>r.status==='failed').length,done=job.rows.filter(r=>r.status==='complete');
 $('batchStatus').textContent=`${job.mode==='binary'?'Binary':'Three-class'} · ${job.completed} of ${job.total} processed${busy?' · Processing…':failed?` · ${failed} failed`:' · Complete'}`;
 $('progress').max=job.total;$('progress').value=job.completed;$('export').disabled=busy;
 const classes=labels(job.mode);$('summary').innerHTML=[['Classified',done.length],...classes.map(c=>[title(c),done.filter(r=>r.prediction.sentiment===c).length]),['Failed',failed]].map(([label,count])=>`<article class="card"><div class="kpi-label">${label}</div><div class="kpi-value">${count}</div></article>`).join('');
 const selected=$('sentiment').value;$('sentiment').innerHTML='<option value="all">All sentiments</option>'+classes.map(c=>`<option value="${c}">${title(c)}</option>`).join('');$('sentiment').value=classes.includes(selected)?selected:'all';renderRows();
}
function renderRows(){
 if(!job)return;const query=$('search').value.toLowerCase(),sentiment=$('sentiment').value,status=$('resultStatus').value;
 const rows=job.rows.filter(r=>(r.title+' '+r.text).toLowerCase().includes(query)&&(sentiment==='all'||r.prediction?.sentiment===sentiment)&&(status==='all'||r.status===status));
 page=Math.min(page,Math.max(0,Math.ceil(rows.length/20)-1));$('resultCount').textContent=`${rows.length} of ${job.total} reviews`;
 $('rows').innerHTML=rows.slice(page*20,page*20+20).map(r=>`<tr><td><strong>${esc(r.title||'Untitled review')}</strong><details><summary>Read review #${r.id}</summary><p>${esc(r.text)}</p></details></td><td>${r.prediction?`<span class="badge ${r.prediction.sentiment}">${title(r.prediction.sentiment)}</span>`:esc(title(r.status))}</td><td>${r.prediction?esc(r.prediction.emotion==='none'?'None detected':title(r.prediction.emotion)):'—'}</td><td>${esc(r.prediction?.reason||r.error||'Waiting for classification')}</td></tr>`).join('')||'<tr><td colspan="4">No matching reviews.</td></tr>';
 $('pageLabel').textContent=rows.length?`${page*20+1}–${Math.min(page*20+20,rows.length)} of ${rows.length}`:'0 reviews';$('previous').disabled=page===0;$('next').disabled=(page+1)*20>=rows.length;
}
for(const id of ['search','sentiment','resultStatus'])$(id).oninput=()=>{page=0;renderRows();};
$('previous').onclick=()=>{page--;renderRows();};$('next').onclick=()=>{page++;renderRows();};
function csvCell(value){let text=String(value??'');if(/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';}
$('export').onclick=()=>{
 if(!job)return;const data=[['review_id','title','text','status','sentiment','emotion','reason','error'],...job.rows.map(r=>[r.id,r.title,r.text,r.status,r.prediction?.sentiment,r.prediction?.emotion,r.prediction?.reason,r.error])];
 const url=URL.createObjectURL(new Blob(['\uFEFF'+data.map(row=>row.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='signal-'+job.mode+'-results.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
if(location.protocol==='file:'){$('localNotice').hidden=false;$('connectForm').querySelector('button').disabled=true;$('connectionStatus').textContent='Open this page through the Python server to connect.';}
