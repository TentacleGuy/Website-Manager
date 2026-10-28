/* Apply the saved appearance before styles paint. Works without localStorage too. */
(()=>{
 const media=window.matchMedia('(prefers-color-scheme: dark)');let preference=null;
 try{preference=localStorage.getItem('tentacle-theme');}catch(e){}
 const apply=theme=>{document.documentElement.dataset.theme=theme;const toggle=document.querySelector('#theme-toggle');if(toggle){toggle.setAttribute('aria-checked',String(theme==='dark'));toggle.title=theme==='dark'?'Zum hellen Modus wechseln':'Zum dunklen Modus wechseln';} };
 apply(preference==='light'||preference==='dark'?preference:media.matches?'dark':'light');
 document.addEventListener('DOMContentLoaded',()=>{apply(document.documentElement.dataset.theme);document.querySelector('#theme-toggle').addEventListener('click',()=>{preference=document.documentElement.dataset.theme==='dark'?'light':'dark';apply(preference);try{localStorage.setItem('tentacle-theme',preference);}catch(e){}});});
 media.addEventListener('change',()=>{if(!preference)apply(media.matches?'dark':'light');});
 window.addEventListener('storage',event=>{if(event.key==='tentacle-theme'){preference=event.newValue;apply(preference==='light'||preference==='dark'?preference:media.matches?'dark':'light');}});
})();
