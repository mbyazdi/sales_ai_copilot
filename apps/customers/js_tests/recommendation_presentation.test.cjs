/* Navigation/session UI only: run the production script against isolated DOM fixtures. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../../../static/core/js/recommendation_presentation.js'),'utf8');
function fixture(next,brokenImage=false){
 const elements=new Map(),navigations=[];
 for(const id of ['endPresentationDialog','endAll','endGroup','continuePresentation'])elements.set(id,{dataset:{},listeners:{},focus(){this.focused=true;},addEventListener(type,fn){this.listeners[type]=fn;},click(){this.listeners.click?.({currentTarget:this});}});
 const dialog=elements.get('endPresentationDialog');dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;dialog.listeners.close?.();};
 if(next)elements.get('endGroup').dataset.nextGroup=next;
 const image=brokenImage?{complete:true,naturalWidth:0,hidden:false,addEventListener(){}}:null,fallback={hidden:true};
 vm.runInNewContext(source,{document:{getElementById:id=>elements.get(id),querySelector:selector=>selector==='[data-product-image]'?image:fallback},window:{location:{assign:url=>navigations.push(url)}}});
 return {elements,navigations,dialog,image,fallback};
}
let f=fixture('/server-approved-next-group');f.elements.get('endGroup').click();assert.deepEqual(f.navigations,['/server-approved-next-group']);assert(!f.dialog.open);
console.log('PASS end group follows only the server-provided target');
f=fixture();f.elements.get('endAll').click();assert(f.dialog.open);assert.equal(f.navigations.length,0);assert(f.elements.get('continuePresentation').focused);
f.elements.get('continuePresentation').click();assert(!f.dialog.open);assert(f.elements.get('endAll').focused);assert.equal(f.navigations.length,0);
console.log('PASS end all requires confirmation and cancel preserves the presentation');
f=fixture();f.elements.get('endGroup').click();assert(f.dialog.open);assert.equal(f.navigations.length,0);
console.log('PASS last group requests confirmation instead of silently ending all');
f=fixture(null,true);assert(f.image.hidden);assert(!f.fallback.hidden);
console.log('PASS failed future media adapter returns to the truthful image fallback');
