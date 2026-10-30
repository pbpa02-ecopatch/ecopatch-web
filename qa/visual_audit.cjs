
const fs=require('fs'),path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=process.env.AUDIT_OUTPUT||'/tmp/ecopatch-predeploy-20261030/tdd';
const m=JSON.parse(fs.readFileSync(path.join(out,'manifest.json')));
const routes=[
 ['garden-list','/my-ecopatch/'],['garden-create','/my-ecopatch/new/'],['garden-detail','/my-ecopatch/'+m.patch+'/'],['garden-empty','/my-ecopatch/'+m.empty_patch+'/'],['garden-edit','/my-ecopatch/'+m.patch+'/edit/'],['garden-delete','/my-ecopatch/'+m.patch+'/delete/'],['plant-delete','/my-ecopatch/plants/'+m.patchplant+'/delete/'],
 ['profile','/profile/'],['plants','/plants/'],['plant-detail','/plants/'+m.plant+'/'],['recommend','/plants/recommend/'],['plant-create','/plants/add/'],
 ['care','/smart-care/'],['care-create','/smart-care/create/'],['care-edit','/smart-care/'+m.task+'/edit/'],
 ['journal','/journal/'],['journal-create','/journal/create/'],['journal-edit','/journal/'+m.journal+'/edit/'],['journal-detail','/journal/'+m.journal+'/'],['journal-history','/journal/plant/Bayam/'],
 ['seed','/seed-exchange/'],['seed-create','/seed-exchange/create/'],['seed-detail','/seed-exchange/'+m.listing+'/'],['seed-edit','/seed-exchange/'+m.listing+'/edit/'],['seed-delete','/seed-exchange/'+m.listing+'/delete/']
];
const guests=[['home','/'],['login','/login/'],['register','/register/'],['reset','/lupa-password/']];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'reduce'});
 const page=await context.newPage();
 for(const [name,url] of [...routes,...guests]){
  if(process.env.AUDIT_ROUTES&&!process.env.AUDIT_ROUTES.split(',').includes(name))continue;
  const guest=guests.some(r=>r[0]===name);
  let assetGeometry;
  await context.clearCookies();
  if(!guest)await context.addCookies([{name:'sessionid',value:m.cookie,domain:'127.0.0.1',path:'/'}]);
  for(const [phase,port] of [['paired-before',8767],['paired-after',8766]]){
   fs.mkdirSync(path.join(out,phase),{recursive:true});
   const response=await page.goto('http://127.0.0.1:'+port+url,{waitUntil:'load'});
   if(response.status()!==200)throw Error(name+' status '+response.status());
   await page.evaluate(()=>document.fonts.ready);
   await page.waitForFunction(()=>!document.documentElement.classList.contains('show-splash'));
   await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
   await page.evaluate(()=>{
    for(const svg of document.querySelectorAll('svg')){if(svg.pauseAnimations){svg.pauseAnimations();svg.setCurrentTime(0);}}
    if(window.Chart){for(const c of document.querySelectorAll('canvas')){
      const chart=Chart.getChart(c);if(chart){chart.stop();chart.options.animation=false;chart.update('none');}
    }}
   });
   const animatedAssets=page.locator('img[src*=".svg"],img[src^="data:image/svg"]');
   const geometry=await animatedAssets.evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {src:n.getAttribute('src'),x:r.x,y:r.y,w:r.width,h:r.height};}));
   if(assetGeometry&&JSON.stringify(geometry)!==JSON.stringify(assetGeometry))throw Error(name+' SVG image geometry changed');
   assetGeometry=geometry;
   await page.screenshot({path:path.join(out,phase,name+'-1440.png'),fullPage:true,animations:'disabled',mask:[animatedAssets]});
  }
  console.log('PAIRED '+name);
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
