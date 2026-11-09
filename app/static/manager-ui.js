/* List views, local files and recurring jobs. Native folder picking is handed to the host. */
actionIcons.set('Neuen Benutzer anlegen','person-plus');actionIcons.set('Neuer Benutzer','person-plus');actionIcons.set('Passwort zurücksetzen','sliders');actionIcons.set('Pfad manuell eingeben','pencil');actionIcons.set('In Bibliothek speichern','archive');actionIcons.set('Dateien anzeigen','info-circle');
openUsers=async function(name){userProject=name;$('#users-title').textContent='CMS-Benutzer · '+name;const form=$('#users-form');form.reset();form.elements.id.value='';$('#users-list').replaceChildren();$('#users-list').hidden=true;$('#users-reset').hidden=true;$('#users-form-title').textContent='Benutzer hinzufügen';$('#users-dialog').showModal();};
$('#users-form').onsubmit=e=>{e.preventDefault();act(async()=>{const body=Object.fromEntries(new FormData(e.target));body.action=body.id?'reset':'create';await api('projects/'+userProject+'/users',body);$('#users-dialog').close();await loadProjectUsers(userProject);});};
function operatingBadge(p){
    return workspaceBadge(p.health?.reachable===false?'Nicht erreichbar':p.status==='running'?'Aktiv':statuses[p.status]||p.status,p.status);
}
renderProjects=function(){
    syncWorkspaceShell();
    const slug=location.hash.split('/')[1];
    $('#project-view').hidden=!slug;$('#projects-view').hidden=!!slug;
    if(slug){renderProject(slug);return;}
    const box=$('#projects');
    if(unchanged(box,[projects,jobs.filter(j=>['queued','running'].includes(j.status))]))return;
    $('#count').textContent=projects.length+' Projekte';
    const rows=projects.map(p=>[p.slug,cmsLabel(p.cms),p.version,p.php,operatingBadge(p),
        p.extension_status?workspaceBadge(p.extension_status.updates?p.extension_status.updates+' Updates':'Aktuell'):workspaceBadge('Ungeprüft'),
        projectActions(p)]);
    box.replaceChildren(workspaceTable(['Projekt','CMS','Version','PHP','Status','Updates','Aktionen'],rows,{search:$('#search')}));
};

const projectRenderBeforeLists=renderProject;renderProject=function(slug){projectRenderBeforeLists(slug);if(projectTab==='backups'){const heading=[...$('#project-view').querySelectorAll('h2')].find(x=>x.textContent==='Backups für die Livesite');if(heading){const panel=heading.parentElement,buttons=[...panel.children].filter(x=>x.tagName==='BUTTON');if(buttons.length){const actions=el('div',undefined,'extra-actions inline-backup-actions');heading.after(actions);actions.append(...buttons);}}}};
const archiveUploadForm=$('#package-form');
const archiveList=el('div'),archiveTabs=el('div',undefined,'subtabs');
const archiveSync=$('#sync');
const pageHeading=$('#title').parentElement;
archiveSync.hidden=true;
pageHeading.append(archiveSync);
const archiveControls=el('div',undefined,'heading-actions cms-archive-controls');
const archiveCatalog=$('#catalog-cms');
let archiveUploading=false;
function viewTabs(container,choices,selected,select){
    container.setAttribute('role','tablist');
    container.replaceChildren(...choices.map(([key,label])=>{
        const tab=localButton(label,()=>select(key));
        tab.setAttribute('role','tab');tab.setAttribute('aria-selected',String(key===selected));return tab;
    }));
}
function cmsSwitch(selected,onChange){
    const label=el('label',undefined,'cms-switch');
    const input=el('input');
    input.type='checkbox';input.setAttribute('role','switch');
    input.setAttribute('aria-label','Joomla statt WordPress auswählen');
    input.checked=selected==='joomla';
    input.onchange=()=>onChange(input.checked?'joomla':'wordpress');
    label.append(el('span','WordPress'),input,el('span','Joomla'));
    return label;
}
$('#versions-view').replaceChildren(archiveTabs,archiveControls,archiveUploadForm,archiveCatalog,archiveList);
const cmsField=archiveUploadForm.elements.cms;
cmsField.closest('label').hidden=true;
cmsField.closest('label').after(cmsSwitch(cmsField.value,cms=>{cmsField.value=cms;}));
archiveControls.append(cmsSwitch(archiveCMS,cms=>{archiveCMS=cms;renderPackages();}));
archiveUploadForm.onsubmit=e=>{
    e.preventDefault();
    act(async()=>{
        const data=new FormData(archiveUploadForm);
        await upload('packages?'+new URLSearchParams({cms:data.get('cms'),version:data.get('version')}),data.get('file'));
        archiveUploadForm.elements.file.value='';
        workspaceState.dirty=true;
        await refresh(true);
    });
};
function cmsMinimum(cms,version){
    const [major,minor]=version.split('.').map(Number);
    if(cms==='joomla'){
        if(major===6)return ['8.3','MySQL 8.0.13 / MariaDB 10.4'];
        if(major===5)return ['8.1','MySQL 8.0.13 / MariaDB 10.4'];
        if(major===4)return ['7.2.5','MySQL 5.6'];
        if(major===3)return [minor>=3?'5.3.10':'5.3.1','MySQL 5.1'];
        return ['—','—'];
    }
    if(major===7)return ['7.4','MySQL / MariaDB 5.5.5'];
    if(major===6)return [minor>=6?'7.2.24':minor>=3?'7.0':'5.6.20',minor>=5?'MySQL / MariaDB 5.5.5':'MySQL 5.0.15 / MariaDB 5.5'];
    if(major===5)return [minor>=2?'5.6.20':'5.2.4','MySQL 5.0.15 / MariaDB 5.5'];
    if(major===4)return ['5.2.4','MySQL 5.0.15 / MariaDB 5.5'];
    return ['—','—'];
}
renderPackages=function(){
    viewTabs(archiveTabs,[['versions','CMS-Versionen'],['upload','CMS-Paket installieren']],archiveUploading?'upload':'versions',key=>{
        archiveUploading=key==='upload';
        renderPackages();
    });
    archiveCatalog.value=archiveCMS;
    archiveControls.hidden=archiveList.hidden=archiveUploading;
    archiveUploadForm.hidden=!archiveUploading;
    archiveSync.hidden=view!=='versions'||archiveUploading;
    if(archiveUploading)return;
    const known=new Map(releases.filter(r=>r.cms===archiveCMS).map(r=>[r.version,r]));
    for(const pkg of packages.filter(p=>p.cms===archiveCMS))known.set(pkg.version,pkg);
    const rows=[...known.values()].sort((a,b)=>b.version.localeCompare(a.version,'de',{numeric:true}));
    if(unchanged(archiveList,[archiveCMS,rows,jobs]))return;
    archiveList.replaceChildren(workspaceTable(['Version','Min. PHP','Min. Datenbank','Status','Größe','Aktionen'],rows.map(row=>{
        const actions=el('div',undefined,'extra-actions');
        if(row.id){
            const saved=iconNode('check-lg','downloaded-check');saved.title='Gesichert';saved.setAttribute('aria-label','Gesichert');
            actions.append(saved,cleanupButton('cms',row.id));
        }else{
            const cms=archiveCMS;
            const download=button('Herunterladen',()=>api('packages/download',{cms,version:row.version}));
            download.disabled=jobActive('package-'+cms+'-'+row.version);
            actions.append(download);
        }
        return [row.version,...cmsMinimum(archiveCMS,row.version),row.id?'Gesichert':'Verfügbar',row.size?formatBytes(row.size):'—',actions];
    }),{key:'cms-'+archiveCMS,noSearch:true,values:rows.map(row=>[,,,,row.size||0])}));
};
const extensionsWorkspace=$('#extensions-workspace');
const extensionSwitchboard=$('.library-switchboard');
const extensionCmsSwitch=cmsSwitch(extensionCMS,cms=>{location.hash='#extensions/'+cms;});
extensionsWorkspace.before($('.library-tabs'),$('#extension-search').parentElement,extensionCmsSwitch);
const activateWorkspaceTab=activateTab;
activateTab=function(group,key){
    if(group!=='extensions')return activateWorkspaceTab(group,key);
    extensionCMS=key==='joomla'?'joomla':'wordpress';
    libraryItems=[];libraryItemsProject='';
    extensionCmsSwitch.querySelector('input').checked=extensionCMS==='joomla';
};
extensionSwitchboard.remove();
$('.library-heading').hidden=true;
$('#library-archives > p')?.remove();
renderExtensions=function(){
    if(libraryPanel==='project')setLibraryPanel('catalog');
    syncWorkspaceShell();
    $('#library-title').hidden=true;
    $('#library-count').textContent=extensionSources.filter(source=>source.cms===extensionCMS).length+' Erweiterungen';
    document.querySelector('[data-library-panel="project"]')?.remove();
    const box=$('#extensions');
    const sources=extensionSources.filter(source=>source.cms===extensionCMS);
    if(unchanged(box,[sources,extensions,jobs]))return;
    const rows=sources.map(source=>{
        const saved=extensions.filter(pkg=>pkg.source_id===source.id).sort((a,b)=>b.version.localeCompare(a.version,'de',{numeric:true}));
        const actions=el('div',undefined,'extra-actions');
        if(saved.length){
            const download=linkButton('/api/extension-packages/'+saved[0].id,'Herunterladen');
            download.download='';actions.append(download);
        }
        actions.append(localButton('In Projekt installieren',()=>openAssign(source,{version:'latest'})),
            localButton('Globaler Schlüssel',()=>openSource(source)),cleanupButton('extension',source.id,'Erweiterung entfernen'));
        return [source.name,extensionType(source),sourceDescription(source),saved.map(p=>p.version).join(', ')||'—',
            source.license?'Hinterlegt':'Nicht hinterlegt',actions];
    });
    box.className='';
    box.replaceChildren(workspaceTable(['Erweiterung','Typ','Updatequelle','Versionen','Globaler Schlüssel','Aktionen'],rows,{search:$('#extension-search')}));
    $('#extension-packages').replaceChildren(workspaceTable(['Erweiterung / Paket','Version','Größe','Erstellt am','Aktionen'],
        extensions.filter(pkg=>pkg.cms===extensionCMS).map(pkg=>{
            const actions=el('div',undefined,'extra-actions');
            const download=linkButton('/api/extension-packages/'+pkg.id,'Herunterladen');download.download='';
            actions.append(download,cleanupButton('extension-package',pkg.id));
            return [pkg.name,pkg.version,formatBytes(pkg.size),managerDate(pkg.created),actions];
        }),{search:$('#extension-search')}));
    const field=$('#extension-search'),catalog=$('#extensions .managed-table'),packages=$('#extension-packages .managed-table');
    field.oninput=()=>{catalog.dispatchEvent(new Event('table-search'));packages.dispatchEvent(new Event('table-search'));};
};

async function saveProjectExtension(slug,item){const value=await api('projects/'+slug+'/library'),row=value.items.find(x=>x.key==='joomla:'+item.id||x.kind===item.kind&&x.element===item.element);if(!row)throw Error('Für diese Erweiterung wurde keine Downloadquelle gefunden.');if(!row.can_download)throw Error('Die Updatequelle liefert noch kein herunterladbares Paket. Bitte die Herstelleranbindung im CMS prüfen.');await api('projects/'+slug+'/library-import',{key:row.key,download:true});}
const cachedRenderBeforeLibrary=renderCachedInventory;renderCachedInventory=function(slug){cachedRenderBeforeLibrary(slug);const box=$('#project-inventory');if(!box||box.dataset.project!==slug)return;const data=cachedInventory[slug],filter=box.previousElementSibling.value;if(!data)return;const rows=data.items.filter(x=>cmsItem(x)||filter==='all'||filter==='updates'&&x.update==='available'||filter==='core'&&bundled(x)||filter==='third'&&!bundled(x)).sort((a,b)=>(b.update==='available')-(a.update==='available')||a.name.localeCompare(b.name));[...box.querySelectorAll('tbody tr')].forEach((tr,i)=>{const item=rows[i];if(!item||cmsItem(item))return;const cell=tr.lastElementChild,actions=el('div',undefined,'extra-actions');actions.append(...cell.childNodes,button('In Bibliothek speichern',()=>saveProjectExtension(slug,item)));cell.append(actions);});};
// Dedicated file manager, using the same guarded deletion dialogs everywhere.
renderAux=async function(){};$('#technical-downloads')?.remove();navigationIcons.files='folder2-open';titles.files=['Dateimanager'];const fileNav=localButton('Dateimanager',()=>location.hash='#files');fileNav.dataset.view='files';$('aside nav').append(fileNav);decorateNavigation();const filesView=el('section');filesView.id='files-view';filesView.className='view';filesView.hidden=true;$('main').append(filesView);const fileToolbar=el('div',undefined,'toolbar'),fileSearch=el('input'),fileFilter=el('select'),fileList=el('div');fileSearch.type='search';fileSearch.placeholder='Dateien suchen …';fileSearch.setAttribute('aria-label','Dateien suchen');fileFilter.setAttribute('aria-label','Dateityp');for(const [v,t] of [['','Alle Dateien'],['extension-package','Erweiterungspakete'],['cms','CMS-Pakete'],['backup','Akeeba Backups'],['export','Projektsicherungen'],['kickstart','Kickstart'],['manager-download','Manager-Downloads'],['trash','Projektpapierkorb'],['residue','Restdateien']])option(fileFilter,v,t);fileToolbar.append(fileSearch,fileFilter,button('Dateien aktualisieren',()=>renderFiles(true)));filesView.append(fileToolbar,fileList);let fileInventory=[];
async function renderFiles(force=false){
    if(force||view==='files')fileInventory=(await api('cleanup')).items;
    drawFiles();
}
function drawFiles(){
    fileList.replaceChildren(workspaceTable(['Datei / Gruppe','Typ','Größe','Aktionen'],
        fileInventory.map(item=>[item.name,item.label,workspaceStorageSize(item.size),cleanupButton(item.kind,item.id)]),{search:fileSearch}));
}

// Storage locations load fresh on entering the view. Native selection only changes the form.
async function chooseStorageFolder(input){if(input.disabled)return;if(!['localhost','127.0.0.1','vmm.test','[::1]'].includes(location.hostname)){message('Der Ordnerdialog ist auf dem Docker-Rechner über localhost verfügbar. Der Pfad lässt sich auch manuell eingeben.');return;}try{const value=await api('folder-picker',{}),link=el('a');link.href=value.url;document.body.append(link);link.click();link.remove();const until=Date.now()+180000;const check=async()=>{try{const result=await api('folder-picker/'+value.id);if(result.status==='done'){if(input.isConnected){input.value=result.path;invalidateStorageCheck();}return;}if(result.status==='cancelled')return;if(Date.now()<until)setTimeout(check,800);}catch(e){message(e);}};setTimeout(check,800);}catch(e){message(e);}}
const routeBeforePicker=route;let lastManagerRoute='';route=async function(){const current=location.hash;if(current==='#system/storage'&&lastManagerRoute!==current&&!storageApplying)$('#storage-areas').replaceChildren();lastManagerRoute=current;await routeBeforePicker();};
// Persistent recurring task editor and active-job monitor.
let recurringTasks=[];function scheduleEditor(task=null){const d=simpleDialog(task?'Aufgabe bearbeiten':'Wiederkehrende Aufgabe anlegen'),form=el('form');const inputs={};function field(key,title,type='text'){const l=el('label',title),input=el('input');input.type=type;input.required=true;l.append(input);form.append(l);inputs[key]=input;return input;}field('name','Bezeichnung').value=task?.name||'';const kind=el('select');option(kind,'updates','Updates und Erreichbarkeit prüfen');option(kind,'snapshot','Projektsicherungen erstellen');kind.value=task?.kind||'updates';let label=el('label','Aufgabe');label.append(kind);form.append(label);const frequency=el('select');option(frequency,'daily','Täglich');option(frequency,'weekly','Wöchentlich');frequency.value=task?.frequency||'daily';label=el('label','Häufigkeit');label.append(frequency);form.append(label);field('time','Uhrzeit','time').value=task?.time||'09:00';const day=el('select');['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag'].forEach((name,i)=>option(day,String(i),name));day.value=String(task?.weekday??0);const dayLabel=el('label','Wochentag');dayLabel.append(day);form.append(dayLabel);frequency.onchange=()=>dayLabel.hidden=frequency.value!=='weekly';frequency.onchange();const zone=el('select');option(zone,'Europe/Berlin','Deutschland · Europe/Berlin');option(zone,'UTC','UTC');if(task?.timezone&&!['Europe/Berlin','UTC'].includes(task.timezone))option(zone,task.timezone,task.timezone);zone.value=task?.timezone||'Europe/Berlin';label=el('label','Zeitzone');label.append(zone);form.append(label);const all=el('input');all.type='checkbox';all.checked=!task?.projects?.length;label=el('label','Alle Projekte','check');label.prepend(all);form.append(label);const selection=el('div',undefined,'schedule-projects');for(const p of projects){const input=el('input');input.type='checkbox';input.value=p.slug;input.checked=task?.projects?.includes(p.slug)||false;const l=el('label',p.slug,'check');l.prepend(input);selection.append(l);}form.append(selection);all.onchange=()=>selection.hidden=all.checked;all.onchange();const enabled=el('input');enabled.type='checkbox';enabled.checked=task?.enabled??true;label=el('label','Aufgabe aktiv','check');label.prepend(enabled);form.append(label);const error=el('p',undefined,'error'),footer=el('footer'),save=el('button','Speichern','primary');save.type='submit';footer.append(localButton('Abbrechen',()=>d.close()),save);form.append(el('p','Bearbeitet werden laufende, fertig eingerichtete Projekte. Nicht bereite Projekte werden im Protokoll als übersprungen vermerkt.','small-note'),error,footer);form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{const selected=all.checked?[]:[...selection.querySelectorAll('input:checked')].map(x=>x.value);if(!all.checked&&!selected.length)throw Error('Mindestens ein Projekt auswählen.');await api('schedules',{...(task?{id:task.id}:{}),name:inputs.name.value,kind:kind.value,frequency:frequency.value,time:inputs.time.value,weekday:Number(day.value),timezone:zone.value,projects:selected,enabled:enabled.checked});d.close();await renderSchedules();}catch(e){error.textContent=e.message;save.disabled=false;}};d.append(form);d.showModal();}
function removeSchedule(task){const d=simpleDialog('Wiederkehrende Aufgabe löschen?');d.append(el('p',task.name));const f=el('footer');f.append(localButton('Abbrechen',()=>d.close()),button('Aufgabe löschen',async()=>{await api('schedules/'+task.id+'/delete',{});d.close();await renderSchedules();},'danger'));d.append(f);d.showModal();}
renderTasks=function(){const box=$('#tasks-view');if(!$('#recurring-task-list')){box.replaceChildren();const controls=el('div',undefined,'extra-actions');controls.append(localButton('Aufgabe anlegen',()=>scheduleEditor()),button('Alle Projekte jetzt prüfen',()=>api('project-checks',{})));const recurring=workspacePanel('Wiederkehrende Aufgaben'),list=el('div');list.id='recurring-task-list';recurring.append(list);const running=workspacePanel('Laufende Aufgaben'),active=el('div');active.id='running-task-list';running.append(active);box.append(controls,recurring,running);}const active=jobs.filter(j=>['queued','running'].includes(j.status)),list=$('#running-task-list');if(!unchanged(list,active)){list.replaceChildren();if(!active.length)empty(list,'Keine laufenden Aufgaben.');for(const j of active){const row=el('div',undefined,'task-progress');row.append(el('strong',(jobKinds[j.kind]||j.kind)+' · '+j.resource),el('small','Gestartet: '+managerDate(j.created,true)),el('p',j.message));const progress=el('progress'),m=(j.message||'').match(/^(\d+)\/(\d+)/);if(m){progress.max=Number(m[2])||1;progress.value=Number(m[1]);}row.append(progress);if(j.resource==='project-checks')row.append(button('Prüfung beenden',()=>api('project-checks',{action:'cancel'})));if(j.resource.startsWith('schedule-'))row.append(button('Aufgabe beenden',()=>api('schedules/'+j.resource.slice(9)+'/cancel',{})));list.append(row);}}taskStatus.replaceChildren();const scan=active.find(j=>j.resource==='project-checks'||j.kind==='scheduled-task');if(scan){const a=linkButton('#tasks',(jobKinds[scan.kind]||'Aufgabe')+' läuft seit '+managerTime(scan.created)+' · '+scan.message);a.removeAttribute('target');taskStatus.append(a);}};
async function renderSchedules(){recurringTasks=(await api('schedules')).tasks;if(view!=='tasks')return;renderTasks();const list=$('#recurring-task-list');if(unchanged(list,recurringTasks))return;list.replaceChildren();if(!recurringTasks.length){empty(list,'Noch keine wiederkehrenden Aufgaben.');return;}list.append(workspaceTable(['Aufgabe','Zeitplan','Projekte','Nächster Lauf','Aktionen'],recurringTasks.map(task=>{const actions=el('div',undefined,'extra-actions');actions.append(localButton('Bearbeiten',()=>scheduleEditor(task)),button(task.enabled?'Pausieren':'Aktivieren',async()=>{await api('schedules',{...task,enabled:!task.enabled});await renderSchedules();}),button('Jetzt ausführen',()=>api('schedules/'+task.id+'/run',{})),localButton('Löschen',()=>removeSchedule(task),'danger'));if(task.running)actions.querySelectorAll('button').forEach(b=>b.disabled=true);return [task.name+(task.running?' · läuft':''),(task.frequency==='daily'?'Täglich':(['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag'][task.weekday]))+' '+task.time+' · '+task.timezone,task.projects.length?task.projects.join(', '):'Alle Projekte',task.enabled?managerDate(task.next_run,true,task.timezone):'Pausiert',actions];})));}
jobKinds['scheduled-task']='Wiederkehrende Aufgabe';jobKinds['scheduled-check']='Projekt prüfen';
const refreshBeforeManagerViews=refresh;refresh=async function(force=false){await refreshBeforeManagerViews(force);if(view==='files')await renderFiles();if(view==='tasks')await renderSchedules();};

const syncHeadingRoute=route;
route=async function(){
    const section=location.hash.replace(/^#\/?/,'').split('/')[0];
    archiveSync.hidden=section!=='versions'||archiveUploading;
    await syncHeadingRoute();
};

function addDialogClose(dialog){
    if(dialog.matches('.startup-splash')||dialog.querySelector(':scope > .dialog-close'))return;
    const close=localButton('Schließen',()=>dialog.close(),'dialog-close');
    close.autofocus=false;
    dialog.append(close);
    decorateAction(close);
}
document.querySelectorAll('dialog').forEach(addDialogClose);
new MutationObserver(records=>{
    for(const record of records){
        for(const node of record.addedNodes){
            if(node instanceof HTMLDialogElement)addDialogClose(node);
        }
    }
}).observe(document.body,{childList:true});
