// Read-only browser checks. Usage: node scripts/check_appearance.cjs BASE_URL
const {chromium,webkit}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=(process.argv[2]||'http://127.0.0.1:8013').replace(/\/$/,'');
(async()=>{
  const reports=[];
  for(const name of ['chromium','webkit']){
    const browser=await(name==='chromium'?chromium:webkit).launch(name==='chromium'?{channel:'chrome'}:{});
    try{
      const context=await browser.newContext({viewport:{width:390,height:844},colorScheme:'light',timezoneId:'Asia/Tokyo',serviceWorkers:'block',reducedMotion:'reduce'});
      await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto(base);await page.getByRole('button',{name:'Настроить тему',exact:true}).click();
      const dialog=page.getByRole('dialog');await dialog.waitFor();
      assert.equal(await page.locator('input[name="appearance-mode"]:checked').inputValue(),'schedule');
      assert.equal(await page.locator('#appearance-light-start').inputValue(),'09:00');
      for(const width of [320,390,768,1440]){
        await page.setViewportSize({width,height:844});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' overflow '+width);
        const box=await dialog.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);
      }
      await page.setViewportSize({width:390,height:844});
      await page.locator('input[value="dark"][name="appearance-mode"]').check();
      await page.getByRole('button',{name:'Сохранить',exact:true}).click();
      await page.waitForFunction(()=>document.documentElement.dataset.landingVariant==='night'&&document.documentElement.dataset.theme==='dark');
      assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      assert.equal(await page.locator('#landing-video').getAttribute('data-src'),'/static/landing/doday-in-action-dark.mp4');
      assert.equal(await page.locator('#landing-video').evaluate(v=>v.readyState),0);
      await page.locator('#landing-video-start').click();
      await page.waitForFunction(()=>document.getElementById('landing-video').currentTime>.3);
      assert.ok(await page.locator('#landing-video').evaluate(v=>Math.abs(v.duration-15)<.1&&!v.error));
      await page.locator('#landing-video').evaluate(v=>v.pause());
      for(const width of [320,390,768,1440]){
        await page.setViewportSize({width,height:844});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' night overflow '+width);
      }
      await page.getByRole('button',{name:'Настроить тему',exact:true}).click();
      await page.locator('input[value="light"][name="appearance-mode"]').check();
      await page.getByRole('button',{name:'Сохранить',exact:true}).click();
      await page.waitForFunction(()=>document.documentElement.dataset.landingVariant==='day'&&document.documentElement.dataset.theme==='light');
      assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
      await page.setViewportSize({width:320,height:844});
      await page.getByRole('button',{name:'Настроить тему',exact:true}).click();
      await page.locator('input[value="schedule"][name="appearance-mode"]').check();
      await page.locator('#appearance-light-start').fill('00:00');await page.locator('#appearance-dark-start').fill('00:00');
      await page.getByRole('button',{name:'Сохранить',exact:true}).click();assert.ok(await page.locator('#appearance-error').isVisible());
      await page.locator('#appearance-dark-start').fill('00:01');
      await page.getByRole('button',{name:'Сохранить',exact:true}).click();
      await page.waitForFunction(()=>document.documentElement.dataset.landingVariant==='night');
      await page.reload();await page.getByRole('button',{name:'Настроить тему',exact:true}).click();
      assert.equal(await page.locator('#appearance-dark-start').inputValue(),'00:01');
      await page.locator('input[value="system"][name="appearance-mode"]').check();
      await page.getByRole('button',{name:'Сохранить',exact:true}).click();
      await page.waitForFunction(()=>document.documentElement.dataset.landingVariant==='day');
      await page.emulateMedia({colorScheme:'dark'});
      await page.waitForFunction(()=>document.documentElement.dataset.landingVariant==='night');
      assert.equal(await page.evaluate(()=>localStorage.getItem('doday-theme')),'system');
      assert.deepEqual(errors,[]);reports.push(name+' four modes, persisted times, system changes, 320–1440px');
      await context.close();
      // Exercise timer boundaries without depending on the actual time of this run.
      const clockContext=await browser.newContext({serviceWorkers:'block'});
      const clockPage=await clockContext.newPage();await clockPage.goto(base);
      await clockPage.evaluate(()=>localStorage.clear());
      const core=await(await clockPage.request.get(base+'/static/theme-core.js')).text();
      const start=Date.parse('2026-10-30T18:59:59+03:00');
      await clockPage.clock.install({time:start});
      await clockPage.setContent(`<html><head><script data-server-now="${start}">${core.replace(/<\/script/gi,'<\\/script')}</script></head><body>Theme clock</body></html>`);
      assert.equal(await clockPage.locator('html').getAttribute('data-theme'),'light');
      await clockPage.clock.fastForward(1100);
      assert.equal(await clockPage.locator('html').getAttribute('data-theme'),'dark');
      await clockPage.clock.fastForward(14*60*60*1000);
      assert.equal(await clockPage.locator('html').getAttribute('data-theme'),'light');
      await clockContext.close();reports.push(name+' automatic 19:00 / 09:00 boundaries');
    }finally{await browser.close()}
  }
  console.log(JSON.stringify({reports},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
