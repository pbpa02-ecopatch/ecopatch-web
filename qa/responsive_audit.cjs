
const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=process.env.AUDIT_OUTPUT||'/tmp/ecopatch-predeploy-20261030',base=process.env.AUDIT_URL||'http://127.0.0.1:8765';
const m=JSON.parse(fs.readFileSync(path.join(out,'manifest.json')));
const phase=process.argv[2]||'before';
const widths=(process.env.AUDIT_WIDTHS||'320,360,390,414,600,768,820,1024,1440').split(',').map(Number);
const routes=[
 ['garden-list','/my-ecopatch/'],['garden-create','/my-ecopatch/new/'],['garden-detail','/my-ecopatch/'+m.patch+'/'],['garden-empty','/my-ecopatch/'+m.empty_patch+'/'],['garden-edit','/my-ecopatch/'+m.patch+'/edit/'],['garden-delete','/my-ecopatch/'+m.patch+'/delete/'],['plant-delete','/my-ecopatch/plants/'+m.patchplant+'/delete/'],
 ['profile','/profile/'],['plants','/plants/'],['plant-detail','/plants/'+m.plant+'/'],['recommend','/plants/recommend/'],['plant-create','/plants/add/'],
 ['care','/smart-care/'],['care-create','/smart-care/create/'],['care-edit','/smart-care/'+m.task+'/edit/'],
 ['journal','/journal/'],['journal-create','/journal/create/'],['journal-edit','/journal/'+m.journal+'/edit/'],['journal-detail','/journal/'+m.journal+'/'],['journal-history','/journal/plant/Bayam/'],
 ['seed','/seed-exchange/'],['seed-create','/seed-exchange/create/'],['seed-detail','/seed-exchange/'+m.listing+'/'],['seed-edit','/seed-exchange/'+m.listing+'/edit/'],['seed-delete','/seed-exchange/'+m.listing+'/delete/']
];
const guests=[['home','/'],['login','/login/'],['register','/register/'],['reset','/lupa-password/']];
(async()=>{
 fs.mkdirSync(path.join(out,phase),{recursive:true});
 const browser=await chromium.launch({...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{}),headless:true});
 const results=[];
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:900},deviceScaleFactor:1,isMobile:width<768,hasTouch:width<768,reducedMotion:'reduce'});
  await context.addCookies([{name:'sessionid',value:m.cookie,domain:'127.0.0.1',path:'/'}]);
  const page=await context.newPage();
  let errors=[],httpErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',res=>{if(res.status()>=400&&res.url().startsWith(base))httpErrors.push({status:res.status(),url:res.url()});});
  async function inspect(name,url){
   errors=[];httpErrors=[];
   try{
    const res=await page.goto(base+url,{waitUntil:'load',timeout:30000});
    await page.evaluate(()=>document.fonts.ready);
    await page.waitForTimeout(120);
    const layout=await page.evaluate(()=>{
     const vw=window.innerWidth;
     const items=[...document.querySelectorAll('body *')].filter(el=>{
      if(el.closest('svg,[aria-hidden="true"],template'))return false;
      const st=getComputedStyle(el),r=el.getBoundingClientRect();
      return st.display!=='none'&&st.visibility!=='hidden'&&r.width>0&&r.height>0&&(r.right>vw+2||r.left < -2);
     }).slice(0,15).map(el=>{const r=el.getBoundingClientRect();return {tag:el.tagName,class:el.className,id:el.id,left:Math.round(r.left),right:Math.round(r.right),width:Math.round(r.width),text:el.textContent.trim().slice(0,80)};});
     return {viewport:vw,scrollWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,overflow:document.documentElement.scrollWidth>vw+2,offenders:items,bootstrap:!!window.bootstrap,htmx:!!window.htmx};
    });
    const row={name,width,url,status:res.status(),...layout,errors:[...errors],httpErrors:[...httpErrors]};results.push(row);
    if(width===1440||width===390||(width===768&&name==='profile'))await page.screenshot({path:path.join(out,phase,name+'-'+width+'.png'),fullPage:true,animations:'disabled'});
    if(row.overflow||errors.length||res.status()>=400)console.log(JSON.stringify(row));
   }catch(e){results.push({name,width,url,error:e.message});console.log(JSON.stringify({name,width,error:e.message}));}
  }
  for(const [name,url]of routes)if(!process.env.AUDIT_ROUTES||process.env.AUDIT_ROUTES.split(',').includes(name))await inspect(name,url);
  await context.clearCookies();
  for(const [name,url]of guests)if(!process.env.AUDIT_ROUTES||process.env.AUDIT_ROUTES.split(',').includes(name))await inspect(name,url);
  await context.close();
  fs.writeFileSync(path.join(out,phase+'-layout.json'),JSON.stringify(results,null,2));
  console.log('COMPLETED_WIDTH '+width+' rows='+results.length);
 }
 await browser.close();
 const bad=results.filter(r=>r.overflow||r.error||r.errors?.length||r.status>=400);
 console.log(JSON.stringify({phase,checks:results.length,failures:bad.length,output:path.join(out,phase+'-layout.json')}));
 if(bad.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
