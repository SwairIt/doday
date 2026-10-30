const {chromium,webkit}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');
// Usage: node scripts/check_landing.cjs BASE_URL OUTPUT_DIRECTORY
// Requires Playwright, Chrome and Playwright WebKit. No account is used.
const base=(process.argv[2]||'http://127.0.0.1:8013').replace(/\/$/,'');
const output=process.argv[3]||'.tmp_landing_review';
(async()=>{
  const report=[];const errors=[];fs.mkdirSync(output,{recursive:true});
  for(const engine of ['chromium','webkit']){
    const browser=await(engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{channel:'chrome'});
    try{
      const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,colorScheme:'dark',reducedMotion:'reduce',serviceWorkers:'block'});
      await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      let videoRequests=0;context.on('request',r=>{if(r.url().includes('doday-in-action.mp4'))videoRequests++});
      const p=await context.newPage();p.on('pageerror',e=>errors.push(engine+': '+e.message));
      const response=await p.goto(base,{waitUntil:'domcontentloaded'});assert.equal(response.status(),200);
      await p.evaluate(()=>document.fonts.ready);
      for(const width of [320,360,390,430,768,1024,1440]){
        await p.setViewportSize({width,height:900});await p.waitForTimeout(350);
        assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),engine+' '+width+' overflow');
        assert.equal(await p.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(255, 254, 250)');
        await p.screenshot({path:`${output}/${engine}-${width}.png`});report.push(engine+' layout '+width);
      }
      for(const id of ['features','school','workflow','pricing','screenshots','comparison','testimonials','three-steps','blog','ecosystem','faq','updates'])assert.equal(await p.locator('#'+id).count(),1,id);
      assert.equal(await p.locator('.lp-hero-stage img').evaluate(i=>i.naturalWidth),1440);
      await p.locator('#features summary').click();assert.ok(await p.locator('.lp-all-features').isVisible());
      await p.locator('#features summary').click();
      await p.setViewportSize({width:390,height:844});await p.goto(base);await p.waitForTimeout(400);
      await p.getByRole('button',{name:'Открыть меню',exact:true}).click();assert.ok(await p.getByRole('navigation',{name:'Мобильное меню',exact:true}).isVisible());
      await p.keyboard.press('Escape');assert.equal(await p.locator('#landing-menu-toggle').getAttribute('aria-expanded'),'false');
      await p.getByRole('button',{name:'Открыть меню',exact:true}).click();await p.locator('#landing-mobile-menu a[href="#features"]').click();assert.ok(!await p.locator('#landing-mobile-menu').isVisible());
      await p.getByRole('button',{name:'Тёмная',exact:true}).click();assert.ok(await p.locator('#gallery-dark').isVisible());assert.ok(!await p.locator('#gallery-light').isVisible());
      await p.locator('#gallery-dark img').evaluate(i=>i.decode());assert.equal(await p.locator('#gallery-dark img').evaluate(i=>i.naturalWidth),390);
      await p.locator('#faq summary').first().click();assert.ok(await p.locator('#faq details').first().getAttribute('open')!==null);
      await p.setViewportSize({width:1440,height:1000});
      for(const id of ['features','school','workflow','pricing','screenshots','testimonials','faq'])await p.locator('#'+id).screenshot({path:`${output}/${engine}-${id}.png`});
      assert.equal(videoRequests,0,'Video must not be downloaded before interaction');
      assert.equal(await p.locator('#landing-video').evaluate(v=>v.readyState),0,engine+' video metadata must not preload');
      await p.getByRole('button',{name:'Смотреть демонстрацию Doday',exact:true}).click();
      await p.waitForFunction(()=>document.getElementById('landing-video').currentTime>0.3);
      // WebKit's native media loader can bypass Playwright request events.
      // Playback time, metadata and decoded dimensions are the real contract.
      const media=await p.locator('#landing-video').evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,paused:v.paused}));
      assert.ok(Math.abs(media.duration-15)<.1,JSON.stringify(media));assert.ok(!media.paused);
      if(engine==='chromium'){assert.equal(media.width,1920);assert.equal(media.height,1080);}
      // Windows WebKit may expose the native player's scaled presentation size.
      else {assert.ok(media.width>=320);assert.ok(Math.abs(media.width/media.height-16/9)<.02,JSON.stringify(media));}
      await p.locator('#landing-video').evaluate(v=>v.pause());report.push(engine+' video starts only on request, 15s/1080p');
      await p.screenshot({path:`${output}/${engine}-full.png`,fullPage:true});
      report.push(engine+' menu, sections, gallery, FAQ');await context.close();
      const nojs=await browser.newContext({viewport:{width:320,height:844},javaScriptEnabled:false,serviceWorkers:'block'});
      const staticPage=await nojs.newPage();await staticPage.goto(base,{waitUntil:'domcontentloaded'});
      assert.ok(await staticPage.locator('#landing-title').isVisible());assert.ok(await staticPage.locator('noscript a[href="/auth/login"]').isVisible());
      assert.ok(!await staticPage.locator('#landing-menu-toggle').isVisible());assert.ok(!await staticPage.locator('#landing-video-start').isVisible());
      assert.equal(await staticPage.locator('#landing-video').getAttribute('preload'),'none');await nojs.close();report.push(engine+' functional HTML without JS');
      const noMotion=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference',serviceWorkers:'block'});
      await noMotion.route('**/motion-14.8.0.min.js',r=>r.abort());const fallback=await noMotion.newPage();await fallback.goto(base,{waitUntil:'domcontentloaded'});
      await fallback.getByRole('button',{name:'Открыть меню',exact:true}).click();assert.ok(await fallback.locator('#landing-mobile-menu').isVisible());await noMotion.close();report.push(engine+' menu survives unavailable Motion');
      const animated=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference',serviceWorkers:'block'});
      await animated.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      const motionPage=await animated.newPage();motionPage.on('pageerror',e=>errors.push(engine+' motion: '+e.message));
      await motionPage.goto(base,{waitUntil:'domcontentloaded'});await motionPage.locator('.lp-feature-card').first().scrollIntoViewIfNeeded();await motionPage.waitForTimeout(650);
      assert.ok(await motionPage.locator('.lp-feature-card').first().evaluate(e=>Number(getComputedStyle(e).opacity)>=.99));
      await animated.close();report.push(engine+' Motion enhancement');
    }finally{await browser.close()}
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({report,errors},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
