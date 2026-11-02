// Service diagnostics remain separate from host/browser permission claims.
jobKinds['service-check']='Dienste und Rechte prüfen';
jobKinds['service-control']='Dienst steuern';
let systemManagerStopped=false,servicesEntering=false;
const infrastructurePanel=$('#system-panel-infrastructure');
$('#system-tab-infrastructure').textContent='Dienste & Rechte';
const servicePanel=workspacePanel('Dienste und Berechtigungen');
servicePanel.id='system-services';
const serviceToolbar=el('div',undefined,'extra-actions');
const servicesCheck=localButton('Dienste und Rechte prüfen',()=>checkSystemServices());
serviceToolbar.append(servicesCheck);
const serviceTime=el('p',undefined,'small-note'),serviceList=el('div'),permissionList=el('div'),desktopPanel=workspacePanel('Ordner öffnen und Freigaben');
serviceList.id='system-service-list';permissionList.id='system-permission-list';
servicePanel.append(serviceToolbar,serviceTime,serviceList,el('h3','Zugriffsrechte'),permissionList);
infrastructurePanel.prepend(desktopPanel);infrastructurePanel.prepend(servicePanel);
const infrastructureLegacy=el('details');infrastructureLegacy.append(el('summary','Weitere Informationen zur Umgebung'));
for(const child of [...infrastructurePanel.children])if(child!==servicePanel&&child!==desktopPanel)infrastructureLegacy.append(child);
infrastructurePanel.append(infrastructureLegacy);

function localDesktopAvailable(){return ['localhost','127.0.0.1','[::1]','vmm.test'].includes(location.hostname);}
async function checkSystemServices(){servicesCheck.disabled=true;try{await api('system-services/check',{});await refresh(true);}catch(e){message(e);}finally{servicesCheck.disabled=jobActive('system-services');}}
function confirmServiceControl(service,action){
    const labels={start:'Starten',restart:'Neu starten',stop:'Beenden'},d=simpleDialog(service.name+' · '+labels[action]);
    d.append(el('p',service.key==='manager'?(action==='stop'?'Die Oberfläche wird beendet. Zum erneuten Starten die lokale Starten-Datei auf dem Rechner ausführen.':'Die Oberfläche verliert kurz die Verbindung und verbindet sich anschließend erneut.'):'Dieser Dienst kann von mehreren Projekten gemeinsam genutzt werden. Beim Beenden oder Neustarten sind diese Projekte kurzzeitig nicht erreichbar.'));
    if(service.key.startsWith('runtime:php'))d.append(el('p','PHP wird bei einem erneuten Website-Aufruf bei Bedarf wieder gestartet.','small-note'));
    const error=el('p',undefined,'error'),footer=el('footer'),submit=localButton(labels[action],async()=>{submit.disabled=true;try{const value=await api('system-services/control',{service:service.key,action});d.close();if(value.manager==='stop'){systemManagerStopped=true;serviceTime.textContent=value.message;servicesCheck.disabled=true;serviceList.querySelectorAll('button').forEach(b=>b.disabled=true);}else if(value.manager==='restart'){serviceTime.textContent=value.message;}else await refresh(true);}catch(e){error.textContent=e.message;submit.disabled=false;}},action==='stop'?'danger':'primary');
    footer.append(localButton('Abbrechen',()=>d.close()),submit);d.append(error,footer);d.showModal();
}
async function requestDesktopAccess(repair=false){
    if(!localDesktopAvailable()){message('Diese Freigabe muss auf dem Docker-Rechner über localhost:8090 angefragt werden.');return;}
    try{
        const request=await api('folder-picker',{mode:repair?'repair':'choose'}),d=simpleDialog(repair?'Ordneranbindung erneut einrichten':'Ordnerfreigabe anfragen');
        d.append(el('p','Der lokale Ordnerdialog wird geöffnet. Ein Ordner darf zum Test ausgewählt werden; deine Speicherorte werden dabei nicht geändert.'));
        const launch=el('a','Dialog erneut öffnen');launch.href=request.url;launch.className='primary';const status=el('p','Warte auf den lokalen Ordnerdialog …','small-note');
        d.append(launch,status,localButton('Schließen',()=>d.close()));d.showModal();launch.click();
        const deadline=Date.now()+180000;
        const poll=setInterval(async()=>{if(!d.open||Date.now()>deadline){clearInterval(poll);if(d.open)status.textContent='Keine Rückmeldung. Bitte die lokale Anbindung und die Browserfreigabe prüfen.';return;}try{const result=await api('folder-picker/'+request.id);if(result.status!=='waiting'){clearInterval(poll);status.textContent=result.status==='done'?'Lokale Anbindung antwortet. Der Ordnerdialog wurde erfolgreich verwendet. Keine Speicherorte geändert.':'Lokale Anbindung antwortet. Die Ordnerauswahl wurde abgebrochen.';}}catch(e){clearInterval(poll);status.textContent=e.message;}},1000);
    }catch(e){message(e);}
}
async function renderSystemServices(){
    const value=await api('system-services');if(view!=='system'||!location.hash.endsWith('/infrastructure'))return;
    const active=jobActive('system-services');servicesCheck.disabled=active;
    serviceTime.textContent=active?'Prüfung oder Dienstaktion läuft …':value.checked?'Letzte Prüfung: '+new Date(value.checked*1000).toLocaleString('de-DE'):'Noch nicht geprüft.';
    if(value.action_error)serviceTime.textContent+=' · '+value.action_error;
    if(unchanged(serviceList,[value,active]))return;
    const labels={running:'Läuft',exited:'Beendet',created:'Angelegt',restarting:'Startet neu',paused:'Pausiert',dead:'Fehler',missing:'Nicht eingerichtet'};
    serviceList.replaceChildren(workspaceTable(['Dienst','Zustand','Details','Aktionen'],(value.services||[]).map(service=>{
        const actions=el('div',undefined,'extra-actions service-actions');
        for(const action of service.actions){if(action==='start'&&service.status==='running')continue;if(['stop','restart'].includes(action)&&service.status!=='running')continue;const b=localButton({start:'Starten',restart:'Neu starten',stop:'Beenden'}[action],()=>confirmServiceControl(service,action));b.title={start:'Starten',restart:'Neu starten',stop:'Beenden'}[action]+' · '+service.name;b.setAttribute('aria-label',b.title);b.classList.add('icon-action');b.replaceChildren(iconNode({start:'play-fill',restart:'arrow-clockwise',stop:'stop-fill'}[action]));b.disabled=active;actions.append(b);}
        if(!service.actions.length)actions.append(el('small','Lokale Starten-Datei verwenden.'));
        return [service.name,workspaceBadge(labels[service.status]||service.status,service.status==='running'?'done':service.status==='dead'?'error':'queued'),service.detail,actions];
    })));
    permissionList.replaceChildren(workspaceTable(['Prüfung','Ergebnis','Details'],(value.permissions||[]).map(p=>[p.name,workspaceBadge({ok:'Geprüft',error:'Fehler',warning:'Hinweis',unknown:'Manuell prüfen'}[p.status]||p.status,p.status==='ok'?'done':p.status==='error'?'error':'queued'),p.detail])));
    desktopPanel.replaceChildren(el('h2','Ordner öffnen und Freigaben'),el('p','Finder und Explorer benötigen eine lokale Anbindung. Diese wird über die Starten-Datei eingerichtet und läuft nur beim Öffnen eines Ordners. Ein Browser-Link allein kann das nicht auf allen Betriebssystemen erledigen.'));
    const actions=el('div',undefined,'extra-actions');
    const test=localButton('Ordnerfreigabe anfragen',()=>requestDesktopAccess()),repair=localButton('Ordneranbindung erneut einrichten',()=>requestDesktopAccess(true));
    test.disabled=repair.disabled=!localDesktopAvailable()||!value.desktop_registered;actions.append(test,repair);desktopPanel.append(actions);
    desktopPanel.append(el('p',value.desktop_registered?'Die Anbindung ist laut lokaler Einrichtung registriert. Der Dialogtest prüft, ob sie auf diesem Rechner tatsächlich antwortet.':'Einrichtung fehlt: die lokale Starten-Datei im Installationsordner ausführen. Das richtet die Anbindung für deinen Benutzer ein.','small-note'));
    if(value.desktop_test)desktopPanel.append(el('p','Letzte Rückmeldung des lokalen Ordnerdialogs: '+new Date(value.desktop_test.checked*1000).toLocaleString('de-DE')+' · '+(value.desktop_test.status==='selected'?'Ordner ausgewählt':'Auswahl abgebrochen'),'small-note'));
    const help=el('details');help.append(el('summary','Eine Freigabe wurde abgelehnt – was tun?'),el('p','Browser: In den Website-Einstellungen für localhost die Anfrage zum Öffnen externer Anwendungen wieder erlauben. Danach „Ordnerfreigabe anfragen“ anklicken. Eine dauerhaft abgelehnte Anfrage kann die Website nicht selbst zurücksetzen.'),el('p','macOS: Systemeinstellungen → Datenschutz & Sicherheit → Dateien & Ordner. Den Zugriff für die Ordneranbindung bzw. die angezeigte Anwendung erlauben. Windows: Bei gesperrtem Ordner den überwachten Ordnerzugriff unter Windows-Sicherheit prüfen. Linux: Ordnerrechte und Desktop-Sitzung prüfen; für den Auswahldialog wird zenity oder kdialog benötigt.'),el('p','Docker: Freigaben für Speicherordner werden in Docker Desktop verwaltet. Ist Docker oder der Manager beendet, startet die lokale Starten-Datei die Umgebung wieder. Betriebssystemfreigaben werden nicht pauschal angefordert.'));
    desktopPanel.append(help);
}
const routeBeforeServices=route;route=async function(){const entering=location.hash==='#system/infrastructure'&&!servicesEntering;servicesEntering=location.hash==='#system/infrastructure';await routeBeforeServices();if(entering){await renderSystemServices();if(!jobActive('system-services'))await checkSystemServices();}};
const refreshBeforeServices=refresh;refresh=async function(force=false){if(systemManagerStopped)return;await refreshBeforeServices(force);if(view==='system'&&location.hash.endsWith('/infrastructure'))await renderSystemServices();};
const openFolderBeforeSystemHelp=openProjectFolder;
openProjectFolder=function(p){openFolderBeforeSystemHelp(p);const d=$('#project-folder-dialog');if(!d)return;d.querySelector('.extra-actions')?.append(localButton('Dienste & Rechte',()=>{d.close();location.hash='#system/infrastructure';}));};
