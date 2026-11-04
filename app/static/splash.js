/* Startup preference belongs to this browser, like the theme preference. */
(() => {
 'use strict';
 const key='tentacle-start-video';
 let enabled=true;
 try{enabled=localStorage.getItem(key)!=='false';}catch(e){}
 const node=(tag,text,className)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(className)n.className=className;return n;};
 const dialog=node('dialog',null,'startup-splash');dialog.setAttribute('aria-label','Tentacle Startvideo');dialog.setAttribute('closedby','closerequest');
 const close=node('button','×','splash-close');close.type='button';close.setAttribute('aria-label','Startvideo schließen');close.title='Startvideo schließen';
 const frame=node('div',null,'splash-frame'),video=node('video');
 video.autoplay=true;video.preload='none';video.playsInline=true;video.disablePictureInPicture=true;video.disableRemotePlayback=true;video.tabIndex=-1;video.width=1920;video.height=1080;
 video.setAttribute('aria-label','Tentacle Productions Startvideo');video.setAttribute('controlslist','nodownload nofullscreen noremoteplayback');
 video.addEventListener('contextmenu',e=>e.preventDefault());
 frame.append(video);
 const footer=node('div',null,'splash-footer'),label=node('label',null,'check'),next=node('input');next.type='checkbox';next.checked=enabled;
 label.append(next,document.createTextNode('Beim nächsten Start abspielen'));
 footer.append(label);dialog.append(close,frame,footer);document.body.append(dialog);

 const tab=node('button','Startvideo');tab.type='button';tab.id='system-tab-splash';tab.dataset.tab='splash';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','system-panel-splash');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
 const tabs=document.querySelector('[data-tab-group="system"]');tabs.append(tab);
 const panel=node('div');panel.id='system-panel-splash';panel.dataset.panelGroup='system';panel.dataset.panel='splash';panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);panel.hidden=true;
 const section=node('section',null,'panel'),heading=node('h2','Startvideo'),settingLabel=node('label',null,'check'),setting=node('input');setting.type='checkbox';setting.checked=enabled;
 settingLabel.append(setting,document.createTextNode('Startvideo beim Öffnen des Projektmanagers abspielen'));
 const note=node('p','Diese Einstellung gilt für diesen Browser. Das Video startet automatisch und kann jederzeit geschlossen werden. Blockiert der Browser den Start mit Ton, wird es stumm abgespielt.','small-note');
 const preview=node('button','Startvideo ansehen');preview.type='button';
 section.append(heading,settingLabel,note,preview);panel.append(section);document.querySelector('#system-view').append(panel);
 tab.onclick=()=>{location.hash='#system/splash';};
 for(const button of tabs.querySelectorAll('[role="tab"]'))button.onkeydown=e=>{const all=[...tabs.querySelectorAll('[role="tab"]')],i=all.indexOf(button);let target;if(e.key==='ArrowRight')target=(i+1)%all.length;else if(e.key==='ArrowLeft')target=(i+all.length-1)%all.length;else if(e.key==='Home')target=0;else if(e.key==='End')target=all.length-1;else return;e.preventDefault();all[target].focus();all[target].click();};

 function preference(value){
  enabled=value;next.checked=setting.checked=value;
  try{localStorage.setItem(key,String(value));note.textContent='Gespeichert für diesen Browser. Das Startvideo ist '+(value?'aktiviert.':'deaktiviert.');}
  catch(e){note.textContent='Die Einstellung gilt nur bis zum Neuladen, weil der Browser das Speichern blockiert.';}
 }
 next.onchange=()=>preference(next.checked);setting.onchange=()=>preference(setting.checked);
 window.addEventListener('storage',e=>{if(e.key===key||e.key===null){enabled=e.key===null||e.newValue!=='false';next.checked=setting.checked=enabled;}});
 async function play(){
  try{await video.play();}
  catch(e){
   if(!dialog.open)return;
   if(e.name==='NotAllowedError'){
    video.muted=true;
    try{await video.play();}catch(error){if(dialog.open&&error.name!=='AbortError')video.pause();}
   }else if(e.name!=='AbortError')video.pause();
  }
 }
 function show(){
  if(dialog.open)return;
  next.checked=enabled;
  dialog.showModal();preview.disabled=true;video.muted=false;video.volume=1;
  if(!video.getAttribute('src'))video.src='/assets/tentacle-web.mp4';
  if(video.error)video.load();
  video.currentTime=0;
  play();
 }
 preview.onclick=show;
 video.addEventListener('error',()=>video.pause());
 dialog.addEventListener('cancel',e=>{e.preventDefault();dialog.close();});
 document.addEventListener('keydown',e=>{if(dialog.open&&e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();dialog.close();}},true);
 close.onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{video.pause();preview.disabled=false;});
 if(enabled)show();
})();
