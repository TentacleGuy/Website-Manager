/* Shared application layout and focused views. All actions use the existing APIs. */
const workspaceState={extension:'',project:'',ready:false,dirty:true,pending:false};
function localButton(text,fn,cls=''){const b=el('button',text,cls);b.type='button';b.onclick=fn;return b;}
function workspacePanel(title,description=''){const section=el('section',undefined,'panel workspace-panel');section.append(el('h2',title));if(description)section.append(el('p',description,'small-note'));return section;}
function workspaceFacts(values){const dl=el('dl',undefined,'workspace-facts');for(const [label,value] of values){const dd=el('dd');dd.append(value instanceof Node?value:document.createTextNode(String(value??'—')));dl.append(el('dt',label),dd);}return dl;}
function workspaceBadge(text,kind=''){return el('span',text,'badge '+kind);}
function workspaceChoices(items,current,onSelect){const list=el('div',undefined,'workspace-choices');for(const item of items){const b=localButton('',()=>onSelect(item.id),'workspace-choice');b.setAttribute('aria-pressed',String(item.id===current));const text=el('span');text.append(el('strong',item.name),el('small',item.meta));b.append(text);if(item.badge)b.append(item.badge);list.append(b);}return list;}
const workspaceTables=new Map();
const tablePageSize=20;
function managerTime(timestamp,timeZone){
    return new Date(timestamp*1000).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit',timeZone});
}
function managerDate(timestamp,withTime=false,timeZone){
    if(!timestamp)return '—';
    const date=new Date(timestamp*1000);
    const day=date.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone});
    return withTime?day+' · '+managerTime(timestamp,timeZone):day;
}
function workspaceTable(headers,rows,settings={}){
    const key=settings.key||[view,view==='projects'?location.hash: '',...headers].join('|');
    if(!workspaceTables.has(key))workspaceTables.set(key,{query:'',page:0,column:-1,direction:1});
    const state=workspaceTables.get(key);
    const wrapper=el('div',undefined,'managed-table'),scroll=el('div',undefined,'project-table-scroll');
    const table=el('table',undefined,'project-table workspace-table'),head=el('thead'),body=el('tbody');
    const search=settings.search||el('input');
    search.type='search';search.placeholder='Alle Spalten durchsuchen …';search.setAttribute('aria-label',search.placeholder);
    if(!settings.search)search.value=state.query;
    const legend=el('div',undefined,'table-legend'),footer=el('nav',undefined,'table-pages');
    footer.setAttribute('aria-label','Tabellenseiten');
    const textOf=cell=>{
        if(cell instanceof HTMLInputElement)return cell.value;
        if(!(cell instanceof Element))return String(cell??'');
        return cell.textContent+' '+[cell,...cell.querySelectorAll('[aria-label]')].map(node=>node.getAttribute('aria-label')||'').join(' ');
    };
    const valueFor=(row,column)=>{
        const cell=rows[row][column];
        if(cell instanceof HTMLInputElement)return cell.value;
        if(cell instanceof Element&&cell.dataset.sortValue!==undefined)return Number(cell.dataset.sortValue);
        return settings.values?.[row]?.[column]??textOf(cell);
    };
    const actions=new Map();
    rows.forEach(row=>row.forEach(cell=>{
        if(!(cell instanceof Element))return;
        for(const control of [cell,...cell.querySelectorAll('button,a,summary')]){
            if(!control.matches('button,a,summary'))continue;
            if(control.tagName==='A'&&actionIcons.has(control.textContent.trim()))control.classList.add('button-link');
            decorateAction(control);
            const icon=control.dataset.iconName||[...control.querySelector('.ui-icon')?.classList||[]].find(name=>name.startsWith('icon-'))?.slice(5);
            const label=control.dataset.iconLabel||control.getAttribute('aria-label')||control.title;
            if(icon&&label)actions.set(icon+'|'+label,[icon,label]);
        }
    }));
    if(rows.some(row=>row.some(cell=>cell instanceof Element&&cell.querySelector('.downloaded-check'))))
        actions.set('check-lg|Gesichert',['check-lg','Gesichert']);
    for(const [icon,label] of actions.values()){
        const entry=el('span');entry.append(iconNode(icon),document.createTextNode(label));legend.append(entry);
    }
    function draw(){
        const query=(settings.search?search.value:state.query).trim().toLocaleLowerCase('de');
        const terms=query.split(/\s+/).filter(Boolean);
        const indices=rows.map((_,i)=>i).filter(i=>{
            if(settings.remote||!terms.length)return true;
            const text=rows[i].map(textOf).join(' ').toLocaleLowerCase('de');
            return terms.every(term=>text.includes(term));
        });
        if(!settings.remote&&state.column>=0)indices.sort((a,b)=>{
            const x=valueFor(a,state.column),y=valueFor(b,state.column);
            return state.direction*(typeof x==='number'&&typeof y==='number'?x-y:String(x??'').localeCompare(String(y??''),'de',{numeric:true}));
        });
        const count=settings.remote?settings.total:indices.length;
        const pages=Math.max(1,Math.ceil(count/tablePageSize));
        state.page=Math.min(settings.remote?settings.page:state.page,pages-1);
        const heading=el('tr');
        headers.forEach((label,column)=>{
            const th=el('th',label);th.scope='col';
            if(!/^Aktion(en)?$/.test(label)){
                const selected=(settings.remote?settings.column:state.column)===column;
                const direction=settings.remote?settings.direction:state.direction;
                th.setAttribute('aria-sort',selected?(direction===1?'ascending':'descending'):'none');
                th.replaceChildren(localButton(label+(selected?(direction===1?' ↑':' ↓'):''),()=>{
                    if(settings.remote){settings.sort(column);return;}
                    state.direction=state.column===column?-state.direction:1;state.column=column;state.page=0;draw();
                },'column-sort'));
            }
            heading.append(th);
        });
        head.replaceChildren(heading);body.replaceChildren();
        const visible=settings.remote?indices:indices.slice(state.page*tablePageSize,(state.page+1)*tablePageSize);
        for(const i of visible){
            const row=el('tr');
            rows[i].forEach((cell,column)=>{
                const td=el('td');td.dataset.label=headers[column];
                td.append(cell instanceof Node?cell:document.createTextNode(String(cell??'—')));row.append(td);
            });
            body.append(row);
        }
        if(!visible.length){const row=el('tr'),cell=el('td','Keine passenden Einträge.');cell.colSpan=headers.length;row.append(cell);body.append(row);}
        footer.replaceChildren();
        if(pages>1){
            const go=page=>{if(settings.remote)settings.go(page);else{state.page=page;draw();}};
            const previous=localButton('‹ Zurück',()=>go(state.page-1));previous.disabled=state.page===0;footer.append(previous);
            const buttons=new Set([0,pages-1,state.page-1,state.page,state.page+1].filter(page=>page>=0&&page<pages));
            let last=-1;
            for(const page of [...buttons].sort((a,b)=>a-b)){
                if(page-last>1)footer.append(el('span','…'));
                const b=localButton(String(page+1),()=>go(page));if(page===state.page)b.setAttribute('aria-current','page');footer.append(b);last=page;
            }
            const next=localButton('Weiter ›',()=>go(state.page+1));next.disabled=state.page===pages-1;footer.append(next);
        }
    }
    if(settings.search&&!settings.remote){
        const filter=()=>{state.page=0;draw();};
        search.oninput=filter;wrapper.addEventListener('table-search',filter);
    }
    if(!settings.search&&!settings.noSearch){
        search.oninput=()=>{state.query=search.value;state.page=0;draw();};
        wrapper.append(search);
    }
    if(legend.childElementCount)wrapper.append(legend);
    table.append(head,body);scroll.append(table);wrapper.append(scroll,footer);draw();return wrapper;
}
function workspaceStorageSize(bytes){return bytes===null?'Projektdateien und Datenbankexport':formatBytes(bytes);}
function cleanupButton(kind,id,label='Löschen'){return localButton(label,()=>openCleanup(kind,id),'danger');}
async function openCleanup(kind,id){try{const value=await api('cleanup/'+kind+'/'+encodeURIComponent(id));$('#cleanup-dialog')?.remove();const dialog=el('dialog');dialog.id='cleanup-dialog';dialog.setAttribute('aria-labelledby','cleanup-title');dialog.append(el('h2',value.label+' löschen?'));dialog.firstChild.id='cleanup-title';dialog.append(el('strong',value.name),el('p',value.note),workspaceFacts([['Speicherplatz',workspaceStorageSize(value.size)],['Dateien / Gruppen',value.files]]));if(value.projects.length)dialog.append(el('p','Projektzuordnungen: '+value.projects.join(', '),'small-note'));const footer=el('footer'),cancel=localButton('Abbrechen',()=>dialog.close()),remove=localButton('Endgültig löschen',async()=>{remove.disabled=true;cancel.disabled=true;try{await api('cleanup/'+kind+'/'+encodeURIComponent(id)+'/delete',{});dialog.close();workspaceState.dirty=true;await refresh();}catch(e){error.textContent=e.message;remove.disabled=false;cancel.disabled=false;}},'danger');const error=el('p',undefined,'error');error.setAttribute('role','alert');if(value.blocked.length){error.textContent=value.blocked.join(' ');remove.disabled=true;}else dialog.append(el('p','Diese Löschung gibt den Speicherplatz frei und kann nicht rückgängig gemacht werden.','small-note'));footer.append(cancel,remove);dialog.append(error,footer);document.body.append(dialog);dialog.showModal();}catch(e){message(e);}}
function syncWorkspaceShell(){const header=$('main>header');if(!header)return;$('#page-description')?.remove();const add=$('#source-new');if(add.parentElement!==header)header.append(add);add.hidden=view!=='extensions';}
statuses.running='Aktiv';statuses.stopped='Startbereit';
const baseApi=api;
api=async function(path,body){const value=await baseApi(path,body);if(body!==undefined)workspaceState.dirty=true;return value;};

renderProjects=function(){syncWorkspaceShell();const detail=location.hash.split('/')[1];$('#project-view').hidden=!detail;$('#projects-view').hidden=!!detail;if(detail){renderProject(detail);return;}const query=$('#search').value.trim().toLowerCase(),selected=projects.filter(p=>[p.slug,p.cms,p.version,p.php].join(' ').toLowerCase().includes(query));$('#count').textContent=selected.length+' Projekte';const box=$('#projects');if(unchanged(box,[selected,workspaceState.project,jobs.filter(j=>['queued','running'].includes(j.status))]))return;box.replaceChildren();box.className='workspace-grid';if(!selected.length){empty(box,workspaceState.ready?'Keine passenden Projekte.':'Projekte werden geladen …');return;}if(!selected.some(p=>p.slug===workspaceState.project))workspaceState.project=selected[0].slug;const p=selected.find(p=>p.slug===workspaceState.project);const list=workspaceChoices(selected.map(p=>({id:p.slug,name:p.slug,meta:cmsLabel(p.cms)+' '+(p.version||'')+' · PHP '+p.php,badge:workspaceBadge(jobActive(p.slug)?'Vorgang läuft':statuses[p.status]||p.status,p.status)})),p.slug,id=>{workspaceState.project=id;renderProjects();});list.setAttribute('aria-label','Projekte auswählen');const panel=workspacePanel(p.slug,p.slug+'.vmm.test');panel.append(workspaceFacts([['Status',workspaceBadge(statuses[p.status]||p.status,p.status)],['CMS',cmsLabel(p.cms)+' '+(p.version||'')],['PHP',p.php],['Updates',p.extension_status?updateSummary(p.extension_status):'Noch nicht geprüft']]));if(p.error)panel.append(el('p',p.error,'error'));panel.append(localButton('Projektdetails →',()=>{location.hash='#projects/'+p.slug;},'primary'));const links=el('div',undefined,'extra-actions');links.append(folderButton(p));if(p.backend_url)links.append(projectLink(p.backend_url,'Backend ↗'));if(p.frontend_url)links.append(projectLink(p.frontend_url,'Frontend ↗'));panel.append(links);box.append(list,panel);scanOverview();};

renderExtensions=function(){syncWorkspaceShell();const query=$('#extension-search').value.toLowerCase(),filtered=extensionSources.filter(x=>x.cms===extensionCMS&&[x.name,...extensions.filter(e=>e.source_id===x.id).map(e=>e.version)].join(' ').toLowerCase().includes(query));$('#library-title').textContent=cmsLabel(extensionCMS)+'-Erweiterungen';$('#library-count').textContent=filtered.length+' Erweiterungen';const box=$('#extensions');if(!filtered.some(x=>x.id===workspaceState.extension))workspaceState.extension=filtered[0]?.id||'';const signature=[filtered,extensions,licenses,extensionPlans,workspaceState.extension,jobs.filter(j=>j.resource.startsWith('extension-'))];if(!unchanged(box,signature)){box.replaceChildren();box.className='workspace-grid';if(!filtered.length)empty(box,'Keine passenden Erweiterungen. Ein ZIP-Paket hinzufügen oder aus einem Projekt übernehmen.');else{const source=filtered.find(x=>x.id===workspaceState.extension);const list=workspaceChoices(filtered.map(x=>{const saved=extensions.filter(e=>e.source_id===x.id);return {id:x.id,name:x.name,meta:saved.length?saved.length+(saved.length===1?' Paket · ':' Pakete · ')+saved.map(e=>e.version).sort((a,b)=>b.localeCompare(a,undefined,{numeric:true}))[0]:'Noch kein Paket gespeichert'};}),source.id,id=>{workspaceState.extension=id;renderExtensions();});list.setAttribute('aria-label','Erweiterungen auswählen');const panel=workspacePanel(source.name,'Updatequelle und gespeicherte Versionen');const saved=extensions.filter(e=>e.source_id===source.id).sort((a,b)=>b.version.localeCompare(a.version,undefined,{numeric:true}));panel.append(workspaceFacts([['CMS',cmsLabel(source.cms)],['Typ',extensionType(source)],['Updatequelle',sourceDescription(source)],['Gespeicherte Pakete',saved.length],['Globaler Schlüssel',source.license?'Hinterlegt':'Nicht hinterlegt']]));const label=el('label','Version'),versions=el('select');versions.setAttribute('aria-label','Version für '+source.name);option(versions,'latest','Neueste verfügbare Version');for(const v of new Set([...saved.map(e=>e.version),...(source.available||[]).map(e=>e.version)]))option(versions,v,v+(saved.some(e=>e.version===v)?' · gespeichert':''));label.append(versions);panel.append(label);const actions=el('div',undefined,'extra-actions');if(source.source_type!=='upload')actions.append(button('Updates prüfen',()=>api('extension-sources/'+source.id+'/check',{})),button('Paket speichern',()=>api('extension-sources/'+source.id+'/download',{version:versions.value})));panel.append(actions,button('In Projekt installieren',()=>openAssign(source,{version:versions.value}),'primary'));const edit=el('div',undefined,'extra-actions');edit.append(localButton('Bearbeiten / globaler Schlüssel',()=>openSource(source)),localButton('Projektschlüssel',()=>openProjectKey(source)));panel.append(edit);if(source.error)panel.append(el('p',source.error,'error'));const used=extensionPlans.filter(p=>p.source===source.id);if(used.length)panel.append(el('p','Zugeordnet: '+used.map(p=>p.project).join(', '),'small-note'));const footer=el('div',undefined,'workspace-danger-zone');footer.append(cleanupButton('extension',source.id,'Erweiterung entfernen'));panel.append(footer);if(jobActive('extension-'+source.id))panel.querySelectorAll('button').forEach(b=>b.disabled=true);box.append(list,panel);}}
 renderLibraryPackages(query);const select=$('#inventory-project'),previous=select.value;if(!unchanged(select,[extensionCMS,projects.map(p=>[p.slug,p.cms,p.status,p.restore])])){select.replaceChildren();option(select,'','Projekt auswählen');for(const p of projects.filter(p=>p.cms===extensionCMS&&!p.restore))option(select,p.slug,p.slug+(p.status==='running'?'':' · zuerst starten'));if([...select.options].some(o=>o.value===previous))select.value=previous;}renderLibraryCandidates();setLibraryPanel(libraryPanel);};
renderLibraryPackages=function(query=''){const box=$('#extension-packages'),rows=extensions.filter(e=>e.cms===extensionCMS&&[e.name,e.version].join(' ').toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name)||b.version.localeCompare(a.version,undefined,{numeric:true}));if(unchanged(box,[rows,extensionSources]))return;box.replaceChildren();if(!rows.length){empty(box,'Keine gespeicherten Pakete für dieses CMS.');return;}box.append(workspaceTable(['Erweiterung / Paket','Version','Größe','Aktionen'],rows.map(x=>{const info=el('div'),source=extensionSources.find(s=>s.id===x.source_id);info.append(el('strong',source?.name||x.name),el('small',x.filename||'Originalpaket'));const actions=el('div',undefined,'extra-actions'),download=el('a','Herunterladen');download.href='/api/extension-packages/'+x.id;download.download=(source?.name||x.name)+'-'+x.version+'.zip';actions.append(download,cleanupButton('extension-package',x.id));return [info,x.version,formatBytes(x.size),actions];})));};
const baseRenderPackages=renderPackages;
renderPackages=function(){syncWorkspaceShell();baseRenderPackages();const box=$('#packages');box.replaceChildren();if(!packages.length){empty(box,'Noch keine Installationspakete gespeichert.');return;}box.append(workspaceTable(['CMS','Version','Größe','Aktionen'],packages.map(p=>[cmsLabel(p.cms),p.version,formatBytes(p.size),cleanupButton('cms',p.id)])));};
renderBackups=async function(){syncWorkspaceShell();const data=await api('cleanup');for(const [selector,kinds] of [['#backups',['backup']],['#exports',['export']],['#other-downloads',['kickstart','manager-download','trash','residue']]]){const box=$(selector);if(!box)continue;const items=data.items.filter(x=>kinds.includes(x.kind));if(unchanged(box,items))continue;box.replaceChildren();if(!items.length){empty(box,'Keine gespeicherten Dateien in diesem Bereich.');continue;}box.append(workspaceTable(['Datei / Archiv','Typ','Größe','Aktionen'],items.map(item=>{const info=el('div');info.append(el('strong',item.name));if(item.status==='error')info.append(el('small',item.note,'small-note'));if(item.blocked.length)info.append(el('small',item.blocked.join(' '),'small-note'));if(item.verification)info.append(el('small','Wiederherstellungsprobe: '+({done:'Bestanden',running:'Läuft',error:'Fehlgeschlagen',interrupted:'Unterbrochen'}[item.verification.status]||item.verification.status)));const actions=el('div',undefined,'extra-actions');if(item.kind==='backup'){const record=backups.find(b=>b.id===item.id),file=record?.files.find(n=>/\.(jpa|jps|zip)$/i.test(n));if(file){const a=el('a','Herunterladen');a.href='/api/backups/'+item.id+'/'+encodeURIComponent(file);a.download=file;actions.append(a);actions.append(localButton('Projekt erstellen',async()=>{await openCreate();$('#project-source').value='backup';fillProjectSources();$('#project-backup').value=item.id+'/'+file;}));}}if(item.kind==='export'){const a=el('a','Herunterladen');a.href='/api/exports/'+encodeURIComponent(item.id);a.download=item.id;actions.append(a);}if(['backup','export'].includes(item.kind))actions.append(button('Wiederherstellung prüfen',()=>api('verification',{kind:item.kind,id:item.id})));actions.append(cleanupButton(item.kind,item.id));return [info,item.label,workspaceStorageSize(item.size),actions];})));}};

const baseRenderProject=renderProject;
function projectTabs(slug){const tabs=el('div',undefined,'subtabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Projektbereiche');for(const [key,label] of [['overview','Übersicht'],['extensions','Erweiterungen'],['backups','Backups'],['users','Benutzer'],['licenses','Lizenzen'],['credentials','Zugänge'],['settings','Einstellungen']]){const b=localButton(label,()=>{projectTab=key;projectSnapshot='';renderProject(slug);});b.setAttribute('role','tab');b.setAttribute('aria-selected',String(projectTab===key));tabs.append(b);}return tabs;}
renderProject=function(slug){if(projectRendered!==slug){projectTab='overview';projectRendered=slug;}const p=projects.find(p=>p.slug===slug);if(!p){baseRenderProject(slug);return;}if(['extensions','users','licenses'].includes(projectTab)){baseRenderProject(slug);$('#project-view>.subtabs').replaceWith(projectTabs(slug));syncWorkspaceShell();return;}projectSnapshot=projectState(slug);const box=$('#project-view');box.replaceChildren();const back=el('a','← Alle Projekte');back.href='#projects';box.append(back,projectTabs(slug));$('#new').hidden=true;$('#title').textContent=slug;syncWorkspaceShell();
 if(projectTab==='backups'){const panel=workspacePanel('Sicherungen','Akeeba-Archive und Projektsicherungen getrennt verwalten.');renderAkeebaBackups(p,panel);const snapshot=workspacePanel('Projektsicherung','ZIP mit Website-Dateien und Datenbankexport.');snapshot.append(button('Projektsicherung erstellen',()=>api('projects/'+slug+'/snapshot',{}),'primary'));const exports=el('div');snapshot.append(exports);api('exports').then(data=>{if(!exports.isConnected)return;const files=data.exports.filter(x=>x.name.startsWith(slug+'-'));for(const x of files){const row=el('div',undefined,'row'),a=el('a',x.name);a.href='/api/exports/'+encodeURIComponent(x.name);a.download=x.name;row.append(a,el('small',formatBytes(x.size)),cleanupButton('export',x.name));exports.append(row);}if(!files.length)empty(exports,'Noch keine Projektsicherung für dieses Projekt.');}).catch(message);box.append(panel,snapshot);return;}
 if(projectTab==='credentials'){const panel=workspacePanel('Zugänge','Passwörter werden erst auf Anforderung geladen und angezeigt.');const controls=el('div',undefined,'extra-actions'),content=el('div');controls.append(localButton('Datenbankzugänge anzeigen',async()=>{try{const data=await api('projects/'+slug+'/database');content.replaceChildren();for(const [key,value] of Object.entries(data)){const label=el('label',key),field=copyField(String(value),key);if(/password|passwort/i.test(key)){const input=field.querySelector('input');input.type='password';field.append(localButton('Anzeigen',e=>{input.type=input.type==='password'?'text':'password';e.currentTarget.textContent=input.type==='password'?'Anzeigen':'Verbergen';}));}label.append(field);content.append(label);}}catch(e){message(e);}}),localButton('Gespeicherte CMS-Zugänge',()=>openCredentials(slug)));panel.append(controls,content);box.append(panel);return;}
 if(projectTab==='settings'){const panel=workspacePanel('Laufzeit'),label=el('label','PHP-Version'),select=el('select');phpVersions.forEach(v=>option(select,v,'PHP '+v));select.value=p.php;label.append(select);const apply=button('Änderung übernehmen',()=>api('projects/'+slug+'/runtime',{php:select.value}));apply.disabled=jobActive(slug)||p.storage==='legacy';panel.append(label,apply);const danger=workspacePanel('Projekt entfernen','Dateien und Datenbankexport werden wie bisher im lokalen Papierkorb aufbewahrt.');const remove=localButton('Projekt löschen',()=>{const f=$('#delete-project-form');f.reset();f.dataset.project=slug;f.elements.confirm.placeholder=slug;$('#delete-project').showModal();},'danger');remove.disabled=jobActive(slug);danger.append(remove);box.append(panel,danger);return;}
 const grid=el('div',undefined,'workspace-grid workspace-overview'),site=workspacePanel('Website'),maintenance=workspacePanel('Updates & Sicherungen');site.append(workspaceFacts([['Domain',slug+'.vmm.test'],['CMS',cmsLabel(p.cms)+' '+(p.version||'')],['Laufzeit','PHP '+p.php],['Status',workspaceBadge(statuses[p.status]||p.status,p.status)]]));const links=el('div',undefined,'extra-actions');for(const [url,label] of [[p.frontend_url,'Frontend ↗'],[p.backend_url,'Backend ↗'],[p.database_url,'phpMyAdmin ↗'],[p.https_url,'HTTPS ↗'],...(p.restore?[[p.admin_url,'Wiederherstellung ↗']]:[])])if(url)links.append(projectLink(url,label));links.append(folderButton(p));site.append(links);maintenance.append(el('p',p.extension_status?updateSummary(p.extension_status):'Updates noch nicht geprüft.'));const actions=el('div',undefined,'extra-actions');actions.append(button('Updates prüfen',()=>api('projects/'+slug+'/updates',{})),localButton('Backups ansehen',()=>{projectTab='backups';renderProject(slug);},'primary'));maintenance.append(actions,localButton('Zugänge anzeigen',()=>{projectTab='credentials';renderProject(slug);}));if(p.restore){maintenance.append(el('p','Wiederherstellung noch nicht abgeschlossen.','small-note'),localButton('Wiederherstellung fortsetzen',()=>openRetry(p)));}if(p.error)maintenance.append(el('p',p.error,'error'));grid.append(site,maintenance);box.append(grid);};

let managerNotesVersion='',managerNotes='';
renderManagerUpdate=async function(){
    const data=await api('manager-update'),box=$('#manager-update'),notice=$('#update-notice');
    const installation=data.installation;
    updateInstalling=!!installation&&['queued','running'].includes(installation.status);
    renderUpdateProgress(updateInstalling?installation:null);
    if(view==='system'&&location.hash.endsWith('/updates')&&managerNotesVersion!==data.current){
        try{managerNotes=(await api('manager-changelog')).notes;managerNotesVersion=data.current;}
        catch(error){managerNotes='Änderungsprotokoll konnte nicht geladen werden.';}
    }
    if(!unchanged(box,[data.current,data.latest,data.available,data.error,updateInstalling,jobActive('manager-update'),managerNotes])){
        box.replaceChildren(workspaceFacts([['Installiert',data.current],['Verfügbar',data.latest||'—']]));
        if(data.error)box.append(el('p',data.error,'error'));
        if(data.available&&!data.error){
            const install=button('Update '+data.latest+' installieren',async()=>{
                await api('manager-update/install',{version:data.latest});updateInstalling=true;
            },'primary');
            install.disabled=updateInstalling||jobActive('manager-update');box.append(install);
        }
        if(managerNotes){
            const notes=el('section');notes.append(el('h3','Änderungsprotokoll · '+data.current));
            for(const line of managerNotes.split('\n').map(line=>line.trim()).filter(Boolean)){
                if(line.startsWith('# Website Manager '))continue;
                notes.append(el(line.startsWith('### ')?'h4':'p',line.replace(/^### /,'')));
            }
            box.append(notes);
        }
    }
    notice.hidden=!data.available||!!data.error;
    if(!notice.hidden){
        const link=el('a','Update '+data.latest+' verfügbar');link.href='#system/updates';notice.replaceChildren(link);
    }
};

refresh=async function(force=false){if(document.hidden&&!force&&workspaceState.ready&&!workspaceState.dirty)return;if(busy){workspaceState.pending=true;workspaceState.pendingForce=workspaceState.pendingForce||force;return;}busy=true;try{const all=!workspaceState.ready||workspaceState.dirty;workspaceState.dirty=false;const needed=new Set(all?['projects','packages','extensions','backups','jobs']:({projects:['projects','jobs',...(['extensions','licenses'].includes(projectTab)?['extensions']:[])],extensions:['projects','extensions','jobs'],versions:['packages','jobs'],backups:['backups','jobs'],activity:['jobs'],system:['jobs']})[view]||['jobs']);const results=await Promise.all([...needed].map(async key=>[key,await api(key)]));for(const [key,data] of results){if(key==='projects'){projects=data.projects;phpVersions=data.php;}if(key==='packages'){packages=data.packages;releases=data.releases;}if(key==='extensions'){extensions=data.extensions;licenses=data.licenses;assignments=data.assignments;extensionSources=data.sources||[];providerRecords=data.providers||[];extensionPlans=data.plans||[];}if(key==='backups')backups=data.backups;if(key==='jobs')jobs=data.jobs;}workspaceState.ready=true;syncJobToasts();renderJobs();if(view==='activity')await loadActivity();if(view==='projects'){const slug=location.hash.split('/')[1];if(!slug)renderProjects();else{const p=projects.find(p=>p.slug===slug);if(!p&&!jobs.some(j=>j.resource===slug&&['queued','running'].includes(j.status)))location.hash='#projects';else if(!$('#project-view input:focus, #project-view select:focus')&&projectSnapshot!==projectState(slug))renderProject(slug);else renderProjectJobs(slug);}}if(view==='extensions'&&!$('#extensions input:focus')&&!$('#extensions select:focus'))renderExtensions();if(view==='versions')renderPackages();if(view==='backups')await renderBackups();if(storageApplying&&view!=='system')await renderStorage();if(view==='system'){const tab=location.hash.split('/')[1]||tabDefaults.system;if(tab==='runtimes')await renderRuntimes();if(tab==='updates')await renderManagerUpdate();if(tab==='akeeba')await loadKickstart();if(tab==='infrastructure')await renderEnvironment();if(tab==='storage')await renderStorage();}syncWorkspaceShell();}catch(e){workspaceState.dirty=true;message(updateInstalling?'Manager wird aktualisiert. Verbindung wird wiederhergestellt …':storageApplying?'Speicherorte werden umgestellt. Verbindung wird wiederhergestellt …':e);}finally{busy=false;if(workspaceState.pending){workspaceState.pending=false;const forceNext=workspaceState.pendingForce;workspaceState.pendingForce=false;queueMicrotask(()=>refresh(forceNext));}}};
route=async function(){let [next,tab]=location.hash.replace(/^#\/?/,'').split('/');if(!titles[next])next='projects';view=next;document.querySelectorAll('aside nav button').forEach(n=>{const active=n.dataset.view===view;n.classList.toggle('active',active);if(active)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});document.querySelectorAll('.view').forEach(n=>n.hidden=n.id!==view+'-view');$('#title').textContent=titles[view][0];$('#new').hidden=view!=='projects';if(tabDefaults[view])activateTab(view,tab||tabDefaults[view]);syncWorkspaceShell();if(view==='system'&&tab==='database'){const values=await api('system-credentials');$('#system-credentials').replaceChildren(...Object.entries(values).map(([key,value])=>{const label=el('label',key),field=copyField(value,key);if(/passwort|password/i.test(key))field.querySelector('input').type='password';label.append(field);return label;}));}if(view==='system'&&(tab==='infrastructure'||!tab)){const h=await api('health');$('#health').replaceChildren(el('p',h.docker?'● Docker erreichbar':'○ Docker nicht erreichbar'),el('p',h.kickstart?'● Akeeba Kickstart vorhanden':'Kickstart wird beim Import geladen'));const ports=$('#ports');ports.replaceChildren();for(const php of phpVersions)ports.append(el('p','PHP '+php+' · HTTP 80'+php.replace('.','')+' · HTTPS 81'+php.replace('.','')));}await refresh(true);if(view==='projects')renderProjects();window.scrollTo({top:0,behavior:'instant'});};
const baseOpenCreate=openCreate;
openCreate=async function(){try{const [p,b]=await Promise.all([api('packages'),api('backups')]);packages=p.packages;backups=b.backups;baseOpenCreate();}catch(e){message(e);}};
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
(function setupWorkspace(){document.body.classList.add('workspace-layout');const cms=$('#extensions-view>[data-tab-group]'),library=$('.library-tabs');if(cms&&library){const switchboard=el('div',undefined,'library-switchboard');cms.before(switchboard);switchboard.append(cms,library);}syncWorkspaceShell();})();

const baseSetLibraryPanel=setLibraryPanel;
setLibraryPanel=function(key){baseSetLibraryPanel(key);const toolbar=$('#extensions-workspace>.toolbar');if(toolbar)toolbar.hidden=key==='project';if(key==='archives')$('#library-count').textContent=extensions.filter(e=>e.cms===extensionCMS).length+' gespeicherte Pakete';};

// Directly assigned handlers need the enhanced views, too.
$('#search').oninput=()=>renderProjects();
$('#extension-search').oninput=()=>renderExtensions();
$('#new').onclick=()=>openCreate();
