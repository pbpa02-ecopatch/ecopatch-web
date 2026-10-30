
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=process.env.AUDIT_OUTPUT||'/tmp/ecopatch-predeploy-20261030/tdd',base=process.env.AUDIT_URL||'http://127.0.0.1:8766';
const m=JSON.parse(fs.readFileSync(path.join(out,'manifest.json')));
const results=[];
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 for(const width of [320,390,768,1440]){
  const context=await browser.newContext({viewport:{width,height:900},isMobile:width<768,hasTouch:width<768,reducedMotion:'reduce'});
  await context.addCookies([{name:'sessionid',value:m.cookie,domain:'127.0.0.1',path:'/'}]);
  const page=await context.newPage();page.setDefaultTimeout(7000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  async function test(name,fn){try{await fn();results.push({width,name,passed:true});console.log('PASS '+width+' '+name);}catch(e){results.push({width,name,passed:false,error:e.message});await page.screenshot({path:path.join(out,'functional-failure-'+width+'-'+name+'.png'),fullPage:true});console.log('FAIL '+width+' '+name+' '+e.message);}}
  async function choose(id,value){const button=page.locator('#'+id+'-control');await button.click();await button.locator('..').locator('button[data-value="'+value+'"]').click();}
  await test('garden-crud-htmx',async()=>{
   await page.goto(base+'/my-ecopatch/');
   const name='Audit UI '+width;
   await page.getByRole('link',{name:'+ Buat EcoPatch Baru',exact:true}).click();
   await page.locator('#id_name').fill(name);
   await choose('id_space_type','balcony');
   await page.locator('#id_size_m2').fill('3');
   await page.locator('#id_goal').fill('Memeriksa alur tanpa mengubah desain.');
   await Promise.all([page.waitForURL(/\/my-ecopatch\/\d+\/$/),page.locator('.patch-form-card button[type="submit"]').click()]);
   const detail=page.url();
   await choose('id_plant',String(m.plant));
   await page.locator('#id_quantity').fill('2');
   await choose('id_status','growing');
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/plants/add/')&&r.request().method()==='POST'),page.locator('#add-plant-submit').click()]);
   await page.locator('.plant-row').first().waitFor();
   assert.equal(page.url(),detail,'adding a plant should not reload/navigate');
   assert.match(await page.locator('.mep-feedback').innerText(),/berhasil ditambahkan/);
   const statusId=await page.locator('.plant-status-select').getAttribute('id');
   await Promise.all([page.waitForResponse(r=>r.url().includes('/status/')&&r.request().method()==='POST'),choose(statusId,'harvested')]);
   await page.waitForFunction(()=>document.querySelector('.plant-status-select')?.value==='harvested');
   assert.match(await page.locator('.mep-feedback').innerText(),/Status tanaman berhasil/);
   await page.locator('.plant-remove').click();
   await page.locator('.mep-delete-dialog[open]').waitFor();
   await page.locator('.mep-delete-dialog').getByRole('button',{name:'Batal',exact:true}).click();
   assert.equal(await page.locator('.plant-row').count(),1);
   await page.locator('.plant-remove').click();
   await Promise.all([page.waitForResponse(r=>r.url().includes('/plants/')&&r.url().endsWith('/delete/')&&r.request().method()==='POST'),page.locator('.mep-delete-dialog').getByRole('button',{name:'Ya, hapus tanaman',exact:true}).click()]);
   await page.waitForFunction(()=>document.querySelectorAll('.plant-row').length===0);
   await page.getByRole('link',{name:'Ubah',exact:true}).click();
   await page.locator('#id_name').fill(name+' diperbarui');
   await Promise.all([page.waitForURL(detail),page.getByRole('button',{name:'Simpan perubahan',exact:true}).click()]);
   assert.match(await page.locator('h1').innerText(),/diperbarui/);
   await page.locator('.mep-band [data-confirm-delete]').click();
   await page.locator('.confirm-dialog[open]').waitFor();
   await page.locator('.confirm-dialog').getByRole('button',{name:'Batal',exact:true}).click();
   assert.equal(page.url(),detail);
   await page.locator('.mep-band [data-confirm-delete]').click();
   await Promise.all([page.waitForURL(base+'/my-ecopatch/'),page.locator('.confirm-dialog').getByRole('button',{name:'Ya, hapus EcoPatch',exact:true}).click()]);
   assert.equal(await page.getByRole('heading',{name:name+' diperbarui',exact:true}).count(),0);
  });
  await test('profile-dialogs-and-discard',async()=>{
   await page.goto(base+'/profile/');
   await page.locator('#avatar-btn').click();
   const pop=page.locator('#pf-menu');await pop.waitFor({state:'visible'});
   const box=await pop.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1,'avatar menu must fit');
   await pop.locator('[data-m="petak"][data-v="proud"]').click();
   await page.locator('.pf-savebar.on').waitFor();
   await page.locator('#pf-discard').click();
   assert.equal(await page.locator('.pf-savebar.on').count(),0);
   await page.locator('.pf-eye').click();
   await page.locator('#password-modal.show').waitFor();
   const modal=await page.locator('#password-modal .modal-content').boundingBox();
   assert.ok(modal.x>=0&&modal.x+modal.width<=width+1,'password dialog must fit');
   await page.locator('#password-modal .btn-close').click();
  });
  await test('plant-modal-and-touch-search',async()=>{
   await page.goto(base+'/plants/');
   await page.locator('[data-plant-open][href="/plants/'+m.plant+'/"]').first().click();
   await page.locator('.plant-modal[open] #plant-modal-title').waitFor();
   await page.locator('.plant-modal-x').click();
   await page.locator('#plant-q').fill('Bay');
   const suggestion=page.locator('.plant-suggest-item').filter({hasText:'Bayam'}).first();
   await suggestion.waitFor({state:'visible'});
   if(width<768)await suggestion.tap();else await suggestion.click();
   await page.waitForURL(/q=Bayam/);
   assert.equal(await page.locator('#plant-q').inputValue(),'Bayam');
  });
  await test('smart-care-async-complete-and-undo',async()=>{
   await page.goto(base+'/smart-care/');
   const row=page.locator('#task-'+m.task);
   const checkbox=row.locator('.care-check');
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/complete/')&&r.request().method()==='POST'),checkbox.click()]);
   await page.waitForFunction(id=>document.querySelector('#task-'+id+' .care-check')?.getAttribute('aria-checked')==='true',m.task);
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/complete/')&&r.request().method()==='POST'),page.locator('#care-toast-undo').click()]);
   await page.waitForFunction(id=>document.querySelector('#task-'+id+' .care-check')?.getAttribute('aria-checked')==='false',m.task);
  });
  results.push({width,name:'no-runtime-javascript-errors',passed:errors.length===0,errors});
  fs.writeFileSync(path.join(out,'functional.json'),JSON.stringify(results,null,2));
  await context.close();
 }
 await browser.close();
 const failures=results.filter(r=>!r.passed);
 console.log(JSON.stringify({checks:results.length,failures:failures.length,details:failures}));
 if(failures.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
