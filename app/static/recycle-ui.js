/* One search across all visible columns; the trash preserves each asset's library metadata. */
jobKinds['recycle-restore']='Aus Papierkorb wiederherstellen';jobKinds['recycle-purge']='Papierkorb bereinigen';
actionIcons.set('Wiederherstellen','arrow-counterclockwise');actionIcons.set('Endgültig löschen','trash');actionIcons.set('In Papierkorb verschieben','trash');actionIcons.set('Dateien aktualisieren','arrow-clockwise');
fileFilter.remove();fileToolbar.replaceChildren(fileSearch);
const filesReload=button('Dateien aktualisieren',()=>renderFiles(true));
filesReload.hidden=true;
$('#title').parentElement.append(filesReload);
const routeBeforeFilesReload=route;
route=async function(){
    filesReload.hidden=location.hash.replace(/^#\/?/,'').split('/')[0]!=='files';
    await routeBeforeFilesReload();
};
fileSearch.placeholder='Alle Spalten durchsuchen …';fileSearch.setAttribute('aria-label','Alle Dateispalten durchsuchen');
let recycleItems=[],fileArea='files';
const fileTabs=el('div',undefined,'subtabs');fileTabs.setAttribute('role','tablist');fileTabs.setAttribute('aria-label','Dateibereiche');
for(const [key,label] of [['files','Alle Dateien'],['trash','Papierkorb']]){const b=localButton(label,()=>{fileArea=key;location.hash=key==='trash'?'#files/trash':'#files';syncFileTabs();drawFiles();});b.dataset.fileArea=key;b.id='files-tab-'+key;b.setAttribute('role','tab');b.setAttribute('aria-controls','file-list');fileTabs.append(b);}
filesView.prepend(fileTabs);fileList.id='file-list';fileList.setAttribute('role','tabpanel');
const recycleNotice=el('p',undefined,'small-note');fileToolbar.after(recycleNotice);
function syncFileTabs(){for(const b of fileTabs.children){const selected=b.dataset.fileArea===fileArea;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;}fileList.setAttribute('aria-labelledby','files-tab-'+fileArea);recycleNotice.hidden=fileArea!=='trash';recycleNotice.textContent='Abgelaufene Einträge werden bei laufendem Manager automatisch endgültig gelöscht. Wiederherstellen überschreibt keine inzwischen vorhandenen Dateien.';}
renderFiles=async function(force=false){if(force||view==='files'){const [normal,bin]=await Promise.all([api('cleanup'),api('recycle')]);fileInventory=normal.items.filter(x=>x.kind!=='trash');recycleItems=bin.items;}drawFiles();};
drawFiles=function(){
    const trash=fileArea==='trash',items=trash?recycleItems:fileInventory;
    const headers=['Datei / Gruppe','Typ','Größe',...(trash?['Gelöscht am','Endgültige Löschung']:[]),'Aktionen'];
    if(unchanged(fileList,[items,fileArea]))return;
    const rows=items.map(item=>{
        const actions=el('div',undefined,'extra-actions');
        if(trash){
            const restore=localButton('Wiederherstellen',()=>confirmRecycle(item,'restore'));
            restore.disabled=item.status!=='ready'||item.restorable===false;
            actions.append(restore,localButton('Endgültig löschen',()=>confirmRecycle(item,'purge'),'danger'));
        }else actions.append(cleanupButton(item.kind,item.id));
        return [item.name,item.label,workspaceStorageSize(item.size),...(trash?[managerDate(item.deleted),managerDate(item.expires)]:[]),actions];
    });
    const values=items.map(item=>[item.name,item.label,item.size||0,item.deleted,item.expires]);
    fileList.replaceChildren(workspaceTable(headers,rows,{search:fileSearch,values}));
};
async function confirmRecycle(item,action){const d=simpleDialog(action==='restore'?'Wiederherstellen?':'Endgültig löschen?');d.append(el('strong',item.name),el('p',action==='restore'?'Die Datei und ihre Bibliotheksdaten werden wiederhergestellt. Bereits vorhandene Dateien werden nicht überschrieben. Gelöschte Projekte erscheinen gestoppt im Manager.':'Dieser Papierkorbeintrag wird endgültig entfernt und kann danach nicht mehr wiederhergestellt werden.'));
    const error=el('p',undefined,'error'),footer=el('footer'),ok=localButton(action==='restore'?'Wiederherstellen':'Endgültig löschen',async()=>{ok.disabled=true;try{await api('recycle/'+item.id+'/'+action,{});d.close();workspaceState.dirty=true;await refresh(true);}catch(e){error.textContent=e.message;ok.disabled=false;}},action==='purge'?'danger':'primary');ok.dataset.keepText='true';footer.append(localButton('Abbrechen',()=>d.close()),ok);d.append(error,footer);d.showModal();
}
// Every stored-asset removal uses the current deletion policy, including library and backup views.
openCleanup=async function(kind,id){try{const value=await api('cleanup/'+kind+'/'+encodeURIComponent(id)),trash=value.deletion_mode==='trash';$('#cleanup-dialog')?.remove();const d=simpleDialog(trash?'In Papierkorb verschieben?':'Endgültig löschen?');d.id='cleanup-dialog';d.append(el('strong',value.name),el('p',trash?'Das gespeicherte Paket bzw. Archiv kann im Dateimanager unter Papierkorb wiederhergestellt werden. Installierte Websites bleiben erhalten.':value.note),workspaceFacts([['Speicherplatz',workspaceStorageSize(value.size)],['Dateien / Gruppen',value.files]]));if(value.projects.length)d.append(el('p','Projektzuordnungen: '+value.projects.join(', '),'small-note'));const error=el('p',value.blocked.join(' '),'error'),footer=el('footer'),ok=localButton(trash?'In Papierkorb verschieben':'Endgültig löschen',async()=>{ok.disabled=true;try{await api('cleanup/'+kind+'/'+encodeURIComponent(id)+'/delete',{});d.close();workspaceState.dirty=true;await refresh(true);}catch(e){error.textContent=e.message;ok.disabled=false;}},'danger');ok.dataset.keepText='true';ok.disabled=value.blocked.length>0;if(!trash)d.append(el('p','Diese Löschung kann nicht rückgängig gemacht werden.','small-note'));footer.append(localButton('Abbrechen',()=>d.close()),ok);d.append(error,footer);d.showModal();}catch(e){message(e);}};
const deletionTab=el('button','Löschen & Papierkorb');deletionTab.type='button';deletionTab.dataset.tab='deletion';deletionTab.id='system-tab-deletion';deletionTab.setAttribute('role','tab');deletionTab.setAttribute('aria-controls','system-panel-deletion');deletionTab.onclick=()=>location.hash='#system/deletion';$('#system-view [data-tab-group="system"]').append(deletionTab);
const deletionPanel=el('div');deletionPanel.id='system-panel-deletion';deletionPanel.dataset.panelGroup='system';deletionPanel.dataset.panel='deletion';deletionPanel.setAttribute('role','tabpanel');deletionPanel.setAttribute('aria-labelledby','system-tab-deletion');deletionPanel.hidden=true;$('#system-view').append(deletionPanel);
let deletionFormLoaded=false;
async function loadDeletionSettings(){const value=await api('deletion-settings');if(deletionFormLoaded)return;deletionFormLoaded=true;const panel=workspacePanel('Dateien löschen'),form=el('form'),group=el('fieldset');group.append(el('legend','Gespeicherte Pakete und Archive'));
    for(const [mode,text] of [['trash','Zuerst in den Papierkorb verschieben'],['permanent','Direkt endgültig löschen']]){const radio=el('input');radio.type='radio';radio.name='mode';radio.value=mode;radio.checked=value.mode===mode;const label=el('label',text,'check');label.prepend(radio);group.append(label);}
    const days=el('input');days.type='number';days.min='1';days.max='3650';days.value=String(value.days);days.required=true;const label=el('label','Aufbewahrung im Papierkorb (Tage)');label.append(days);
    const update=()=>days.disabled=form.querySelector('input[name="mode"]:checked')?.value!=='trash';group.onchange=update;
    const note=el('p','Die Aufbewahrung läuft ab dem Verschieben. Neue Einstellungen gelten für künftig gelöschte Dateien; vorhandene Einträge behalten ihr angezeigtes Ablaufdatum. Die automatische Bereinigung läuft, solange der Manager läuft. Gelöschte Projekte werden weiterhin zunächst im Projektpapierkorb gesichert.','small-note'),status=el('p'),save=el('button','Einstellungen speichern','primary');save.type='submit';form.append(group,label,note,status,save);update();
    form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{const result=await api('deletion-settings',{mode:form.querySelector('input[name="mode"]:checked').value,days:Number(days.value)});status.textContent=result.message;}catch(e){status.textContent=e.message;status.className='error';}finally{save.disabled=false;}};panel.append(form);deletionPanel.replaceChildren(panel);
}
const routeBeforeRecycle=route;
route=async function(){
    const aliases={'#system/runtimes':'#system/infrastructure','#system/deletion':'#system/storage','#system/splash':'#system/akeeba'};
    if(aliases[location.hash])history.replaceState(null,'',aliases[location.hash]);
    fileArea=location.hash==='#files/trash'?'trash':'files';
    syncFileTabs();
    await routeBeforeRecycle();
    if(view==='system'&&location.hash.endsWith('/storage'))await loadDeletionSettings();
};
deletionTab.remove();
delete deletionPanel.dataset.panelGroup;
delete deletionPanel.dataset.panel;
deletionPanel.removeAttribute('role');
deletionPanel.removeAttribute('aria-labelledby');
deletionPanel.hidden=false;
$('#system-panel-storage').append(deletionPanel);
$('#system-tab-storage').textContent='Speicher';
$('#system-tab-akeeba').textContent='System';
$('#system-tab-runtimes').remove();
tabDefaults.system='infrastructure';
syncFileTabs();
