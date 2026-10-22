/* M-01-B: GET-only projection. No ranking, commercial arithmetic or commands. */
(function(scope) {
    'use strict';
    const API='/api/management/v1/strategy/';
    const SCOPES={PRODUCT:{label:'محصول',kind:'products'},BRAND:{label:'برند',kind:'brands'},CATEGORY:{label:'گروه محصول',kind:'categories'}};
    const ERRORS={401:'نشست شما معتبر نیست؛ دوباره وارد حساب کاربری شوید.',403:'دسترسی مشاهدهٔ راهبرد برای این حساب مجاز نیست.',
        404:'اطلاعات راهبرد در دسترس نیست.',409:'شواهد سیاست معتبر یا سازگار نیست؛ نمایش متوقف شد.',503:'زیرساخت راهبرد آماده نیست؛ کمی بعد دوباره دریافت کنید.'};
    const integer=value=>Number.isSafeInteger(value) && value>=0;
    const id=value=>integer(value) && value>0;
    const text=value=>typeof value==='string' && value.trim();
    const format=value=>String(value).replace(/[0-9.]/g,c=>c==='.'?'٫':'۰۱۲۳۴۵۶۷۸۹'[Number(c)]);
    function ensure(condition){if(!condition){const e=new Error('INVALID_OVERVIEW');e.status=409;throw e;}}
    function validate(head,options) {
        ensure(head && options && head.schema_version===1 && options.schema_version===1 && text(head.algorithm_version) && head.algorithm_version===options.algorithm_version);
        for(const key of ['revision','version_count','comparison_count'])ensure(integer(head[key]));
        for(const key of ['active_version_id','draft_version_id'])ensure(head[key]===null || id(head[key]));
        ensure(typeof head.selling_context_integration==='boolean' && typeof head.impact_available==='boolean' && text(head.limitations_fa));
        for(const key of ['priority_bounds','target_weight_bounds','promotion_points_bounds'])ensure(Array.isArray(options[key]) && options[key].length===2 &&
            options[key].every(integer) && options[key][0]<=options[key][1]);
        ensure(integer(options.adjustment_cap) && Array.isArray(options.priority_scopes));
        const bounded=(value,range)=>integer(value) && value>=range[0] && value<=range[1];
        const config=head.active_config;
        ensure(config && config.schema_version===1 && Array.isArray(config.priority_rules) && Array.isArray(config.promotion_rules) && bounded(config.target_weight,options.target_weight_bounds));
        const seen=new Set();
        config.priority_rules.forEach(rule=>{ensure(rule && Object.hasOwn(SCOPES,rule.scope_type) && options.priority_scopes.includes(rule.scope_type) && id(rule.scope_id) && bounded(rule.points,options.priority_bounds));
            const key=rule.scope_type+':'+rule.scope_id;ensure(!seen.has(key));seen.add(key);});
        const promotions=new Set();config.promotion_rules.forEach(rule=>{ensure(rule && id(rule.promotion_id) && bounded(rule.points,options.promotion_points_bounds));ensure(!promotions.has(rule.promotion_id));promotions.add(rule.promotion_id);});
        return {head,options};
    }
    function historyPage(data,after=0) {
        ensure(data && Array.isArray(data.results));let previous=after;
        data.results.forEach(row=>{ensure(row && id(row.id) && row.id>previous && typeof row.published==='boolean' && typeof row.created_at==='string' && Number.isFinite(Date.parse(row.created_at)));previous=row.id;});
        ensure(data.next_after_id===null || (id(data.next_after_id) && data.results.length>0 && data.next_after_id===previous));
        return data;
    }
    function render(document,root,model,labels={}) {
        const {head,options}=model,config=head.active_config;
        const put=(field,value)=>{root.querySelector('[data-overview-field="'+field+'"]').textContent=value;};
        const node=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};
        const version=value=>'نسخهٔ '+format(value);
        put('active',head.active_version_id===null?'سیاست خنثی':version(head.active_version_id));
        put('draft',head.draft_version_id===null?'پیش‌نویس ندارد':version(head.draft_version_id));
        put('comparisons',format(head.comparison_count));put('revision',format(head.revision));put('versions',format(head.version_count));
        put('policy-label',head.active_version_id===null?'بدون سیاست منتشرشده':version(head.active_version_id));
        put('target',format(config.target_weight)+' امتیاز');
        put('integration',head.selling_context_integration?'متصل؛ فقط برای زمینه‌های فروش تازه':'اتصال به زمینهٔ فروش تأیید نشده است');
        root.querySelector('#overviewLimitations').textContent=head.limitations_fa;
        root.querySelector('#priorityBounds').textContent='بازهٔ امتیاز اولویت: '+format(options.priority_bounds[0])+' تا '+format(options.priority_bounds[1])+'؛ بدون جمع‌شدن قواعد هم‌پوشان.';
        root.querySelector('#targetBounds').textContent='بازهٔ پیکربندی هدف: '+format(options.target_weight_bounds[0])+' تا '+format(options.target_weight_bounds[1])+' امتیاز؛ نه درصد فروش.';
        root.querySelector('#promotionBounds').textContent='بازهٔ تأکید ترویجی: '+format(options.promotion_points_bounds[0])+' تا '+format(options.promotion_points_bounds[1])+'؛ سقف مجموع تعدیل سیاست: '+format(options.adjustment_cap)+' امتیاز.';
        let missing=false;
        function reference(kind,key,fallback) {
            const row=(labels[kind] || []).find(item=>item.id===key);
            if(!row || !text(row.name)){missing=true;return fallback+' با شناسهٔ '+format(key);}
            return row.name;
        }
        const priorities=root.querySelector('#overviewPriorities');priorities.replaceChildren();
        config.priority_rules.forEach(rule=>{
            const scope=SCOPES[rule.scope_type],li=node('li',undefined,'overview-rule'),identity=node('div');
            identity.append(node('h3',reference(scope.kind,rule.scope_id,scope.label)),node('p',scope.label+' · شناسهٔ '+format(rule.scope_id)));
            li.append(identity,node('strong',format(rule.points)+' امتیاز'));priorities.append(li);
        });
        root.querySelector('#overviewPriorityEmpty').hidden=config.priority_rules.length!==0;
        const promotions=root.querySelector('#overviewPromotions');promotions.replaceChildren();
        config.promotion_rules.forEach(rule=>{const li=node('li',undefined,'overview-rule'),identity=node('div');
            identity.append(node('h3',reference('promotions',rule.promotion_id,'برنامهٔ ترویجی')),node('p','شناسهٔ '+format(rule.promotion_id)));
            li.append(identity,node('strong',format(rule.points)+' امتیاز'));promotions.append(li);});
        root.querySelector('#overviewPromotionEmpty').hidden=config.promotion_rules.length!==0;
        root.querySelector('#overviewReferenceNotice').hidden=!missing;
    }
    function renderHistory(document,root,head,rows) {
        const node=(tag,value,cls)=>{const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;};
        const list=root.querySelector('#overviewHistory');list.replaceChildren();
        const date=new Intl.DateTimeFormat('fa-IR',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Tehran'});
        rows.forEach(row=>{
            const li=document.createElement('li'),identity=document.createElement('div'),badges=document.createElement('div');badges.className='overview-history-tags';
            li.dataset.versionId=String(row.id);
            identity.append(node('h3','نسخهٔ '+format(row.id)),node('p','ایجاد نسخه: '+date.format(new Date(row.created_at))+' · به وقت تهران'));
            if(row.id===head.active_version_id)badges.append(node('span','سیاست فعال','strategy-tag'));
            if(row.id===head.draft_version_id)badges.append(node('span','پیش‌نویس فعلی','strategy-tag strategy-tag-neutral'));
            badges.append(node('span',row.published?'سابقهٔ انتشار دارد':'انتشاری ثبت نشده','strategy-tag strategy-tag-neutral'));
            li.append(identity,badges);list.append(li);
        });
        root.querySelector('#overviewHistoryEmpty').hidden=rows.length!==0;
    }
    function attach(document,root,fetcher) {
        const find=id=>root.querySelector('#'+id),status=find('overviewStatus'),error=find('overviewError'),content=find('overviewContent'),retry=find('overviewRetry'),more=find('overviewMoreVersions');
        let serial=0,head,rows=[],cursor=null,historyBusy=false;
        async function get(path) {
            ensure(/^(overview\/|options\/\?(?:kind=(products|brands|categories|promotions)&after_id=0&limit=100)?|versions\/\?after_id=\d+&limit=6)$/.test(path));
            const response=await fetcher(API+path,{method:'GET',credentials:'same-origin',cache:'no-store',redirect:'error',headers:{Accept:'application/json'}});
            if(!response.ok){const e=new Error('HTTP');e.status=response.status;throw e;}return response.json();
        }
        const errorText=failure=>ERRORS[failure.status] || 'دریافت اطلاعات کامل نشد؛ برای تلاش دوباره، دریافت مجدد را انتخاب کنید.';
        async function load() {
            const request=++serial;error.hidden=true;content.hidden=true;status.hidden=false;retry.disabled=true;content.setAttribute('aria-busy','true');
            find('overviewHistoryError').hidden=true;more.disabled=true;historyBusy=false;
            try {
                const [overview,options,history]=await Promise.all([get('overview/'),get('options/?'),get('versions/?after_id=0&limit=6')]);
                const model=validate(overview,options);historyPage(history);
                const kinds=new Set(overview.active_config.priority_rules.map(rule=>SCOPES[rule.scope_type].kind));
                if(overview.active_config.promotion_rules.length)kinds.add('promotions');
                const kindList=[...kinds];const results=await Promise.allSettled(kindList.map(kind=>get('options/?kind='+kind+'&after_id=0&limit=100')));
                if(request!==serial)return;
                const labels={};results.forEach((result,index)=>{
                    if(result.status==='rejected') {if([401,403].includes(result.reason.status))throw result.reason;return;}
                    const value=result.value;if(Array.isArray(value.results) && value.results.every(row=>row && id(row.id)))labels[kindList[index]]=value.results;
                });
                head=overview;rows=history.results;cursor=history.next_after_id;
                render(document,root,model,labels);renderHistory(document,root,head,rows);more.hidden=cursor===null;more.disabled=false;content.hidden=false;
            } catch(failure) {
                if(request!==serial)return;
                find('overviewErrorText').textContent=errorText(failure);find('overviewLogin').hidden=failure.status!==401;error.hidden=false;
            } finally {if(request===serial){status.hidden=true;retry.disabled=false;content.setAttribute('aria-busy','false');}}
        }
        async function loadMore() {
            if(cursor===null || historyBusy || content.hidden)return;
            const request=serial,after=cursor;historyBusy=true;more.disabled=true;find('overviewHistoryError').hidden=true;
            try {const page=historyPage(await get('versions/?after_id='+after+'&limit=6'),after);if(request!==serial)return;
                rows=rows.concat(page.results);cursor=page.next_after_id;renderHistory(document,root,head,rows);more.hidden=cursor===null;
            } catch(failure){if(request===serial){find('overviewHistoryError').textContent=errorText(failure);find('overviewHistoryError').hidden=false;}}
            finally {if(request===serial){historyBusy=false;more.disabled=false;}}
        }
        retry.addEventListener('click',load);find('overviewRefresh').addEventListener('click',load);more.addEventListener('click',loadMore);load();return {load,loadMore};
    }
    if(typeof module!=='undefined' && module.exports)module.exports={validate,historyPage,render,renderHistory,attach,format,ERRORS};
    if(scope.document){const root=scope.document.getElementById('strategyOverview');if(root)attach(scope.document,root,scope.fetch.bind(scope));}
})(typeof window!=='undefined'?window:globalThis);
