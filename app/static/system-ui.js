// Service diagnostics remain separate from host/browser permission claims.
jobKinds['service-check']='Dienste und Rechte prüfen';
jobKinds['service-control']='Dienst steuern';
let systemManagerStopped=false,servicesEntering=false;
const infrastructurePanel=$('#system-panel-infrastructure');
$('#system-tab-infrastructure').textContent='Dienste';
const servicePanel=workspacePanel('Dienste und Berechtigungen');
servicePanel.id='system-services';
const serviceToolbar=el('div',undefined,'extra-actions');
actionIcons.set('Dienste und Rechte prüfen','arrow-clockwise');
actionIcons.set('Alle Versionen abrufen','arrow-clockwise');
const servicesCheck=localButton('Dienste und Rechte prüfen',()=>checkSystemServices());
serviceToolbar.classList.add('heading-actions');
serviceToolbar.append(servicePanel.querySelector('h2'),servicesCheck);
const kickstartReload=$('#kickstart-sync'),kickstartTitle=kickstartReload.parentElement.querySelector('h2');
if(kickstartTitle){
    const heading=el('div',undefined,'heading-actions');
    kickstartTitle.before(heading);
    heading.append(kickstartTitle,kickstartReload);
}
const serviceTime=el('p',undefined,'small-note'),serviceList=el('div'),permissionList=el('div'),desktopPanel=workspacePanel('Ordner öffnen und Freigaben');
serviceList.id='system-service-list';permissionList.id='system-permission-list';
servicePanel.append(serviceToolbar,serviceTime,serviceList);
const permissionsPanel=workspacePanel('Zugriffsrechte');
permissionsPanel.append(permissionList);
const serviceTabs=el('div',undefined,'subtabs');
let serviceArea='services';
function showServiceArea(key){
    serviceArea=key;
    viewTabs(serviceTabs,[['services','Dienste'],['rights','Rechte'],['shares','Freigaben']],key,showServiceArea);
    servicePanel.hidden=key!=='services';
    permissionsPanel.hidden=key!=='rights';
    desktopPanel.hidden=key!=='shares';
}
infrastructurePanel.prepend(serviceTabs,permissionsPanel);
infrastructurePanel.prepend(desktopPanel);infrastructurePanel.prepend(servicePanel);
const infrastructureLegacy=el('details');infrastructureLegacy.append(el('summary','Weitere Informationen zur Umgebung'));
for(const child of [...infrastructurePanel.children])if(![servicePanel,desktopPanel,serviceTabs,permissionsPanel].includes(child))infrastructureLegacy.append(child);
infrastructurePanel.append(infrastructureLegacy);
infrastructurePanel.prepend(serviceTabs);
showServiceArea(serviceArea);
const updatesHeader=$('#system-panel-updates h2');
const updatesTitle=el('div',undefined,'section-title-actions');
updatesHeader.before(updatesTitle);
updatesTitle.append(updatesHeader,$('#manager-check'));

const serviceActionLabels = {start: 'Starten', restart: 'Neu starten', stop: 'Beenden'};
const serviceActionIcons = {start: 'play-fill', restart: 'arrow-clockwise', stop: 'stop-fill'};

function localDesktopAvailable(){return ['localhost','127.0.0.1','[::1]','vmm.test'].includes(location.hostname);}
async function checkSystemServices(){servicesCheck.disabled=true;try{await api('system-services/check',{});await refresh(true);}catch(e){message(e);}finally{servicesCheck.disabled=jobActive('system-services');}}
function serviceActionButton(name, action, onClick) {
    const button = localButton(serviceActionLabels[action], onClick);
    button.title = serviceActionLabels[action] + ' · ' + name;
    button.setAttribute('aria-label', button.title);
    button.dataset.iconLabel = serviceActionLabels[action];
    button.classList.add('icon-action');
    button.replaceChildren(iconNode(serviceActionIcons[action]));
    return button;
}
function confirmServiceControl(service,action){
    const label=serviceActionLabels[action],d=simpleDialog(service.name+' · '+label);
    d.append(el('p',service.key==='manager'?(action==='stop'?'Die Oberfläche wird beendet. Zum erneuten Starten die lokale Starten-Datei auf dem Rechner ausführen.':'Die Oberfläche verliert kurz die Verbindung und verbindet sich anschließend erneut.'):'Dieser Dienst kann von mehreren Projekten gemeinsam genutzt werden. Beim Beenden oder Neustarten sind diese Projekte kurzzeitig nicht erreichbar.'));
    if(service.key.startsWith('runtime:php'))d.append(el('p','PHP wird bei einem erneuten Website-Aufruf bei Bedarf wieder gestartet.','small-note'));
    const error=el('p',undefined,'error'),footer=el('footer'),submit=localButton(label,async()=>{submit.disabled=true;try{const value=await api('system-services/control',{service:service.key,action});d.close();if(value.manager==='stop'){systemManagerStopped=true;serviceTime.textContent=value.message;servicesCheck.disabled=true;serviceList.querySelectorAll('button').forEach(b=>b.disabled=true);}else if(value.manager==='restart'){serviceTime.textContent=value.message;}else await refresh(true);}catch(e){error.textContent=e.message;submit.disabled=false;}},action==='stop'?'danger':'primary');
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
function isServiceView(){return ['#system','#system/infrastructure'].includes(location.hash);}
async function renderSystemServices(){
    const [value, helper] = await Promise.all([
        api('system-services'),
        localHelperAvailable() ? requestLocalHelper().catch(() => null) : null
    ]);
    if(view!=='system'||!isServiceView())return;
    const active=jobActive('system-services');servicesCheck.disabled=active;
    serviceTime.textContent=active?'Prüfung oder Dienstaktion läuft …':value.checked?'Letzte Prüfung: '+managerDate(value.checked,true):'Noch nicht geprüft.';
    if(value.action_error)serviceTime.textContent+=' · '+value.action_error;
    if(unchanged(serviceList,[value,active,helper]))return;
    const labels={running:'Läuft',exited:'Beendet',created:'Angelegt',restarting:'Startet neu',paused:'Pausiert',dead:'Fehler',missing:'Nicht eingerichtet'};
    const serviceRows=(value.services||[]).map(service=>{
        const actions=el('div',undefined,'extra-actions service-actions');
        for(const action of service.actions){if(action==='start'&&service.status==='running')continue;if(['stop','restart'].includes(action)&&service.status!=='running')continue;const b=serviceActionButton(service.name,action,()=>confirmServiceControl(service,action));b.disabled=active;actions.append(b);}
        if(!service.actions.length)actions.append(el('small','Lokale Starten-Datei verwenden.'));
        return [service.name,workspaceBadge(labels[service.status]||service.status,service.status==='running'?'done':service.status==='dead'?'error':'queued'),service.detail,actions];
    });
    if (helper?.available) {
        const actions = el('div', undefined, 'extra-actions service-actions');
        for (const action of helper.running ? ['restart', 'stop'] : ['start']) {
            actions.append(serviceActionButton('Tentacle Helfer', action, () => openLocalHelperControl(action)));
        }
        const state = workspaceBadge(helper.running ? labels.running : labels.exited, helper.running ? 'done' : 'queued');
        serviceRows.push(['Tentacle Helfer', state, 'Lokaler macOS-Dienst', actions]);
    }
    serviceList.replaceChildren(workspaceTable(['Dienst','Zustand','Details','Aktionen'],serviceRows));
    permissionList.replaceChildren(workspaceTable(['Prüfung','Ergebnis','Details'],(value.permissions||[]).map(p=>[p.name,workspaceBadge({ok:'Geprüft',error:'Fehler',warning:'Hinweis',unknown:'Manuell prüfen'}[p.status]||p.status,p.status==='ok'?'done':p.status==='error'?'error':'queued'),p.detail])));
    desktopPanel.replaceChildren(el('h2','Ordner öffnen und Freigaben'),el('p','Finder und Explorer benötigen eine lokale Anbindung. Diese wird über die Starten-Datei eingerichtet und läuft nur beim Öffnen eines Ordners. Ein Browser-Link allein kann das nicht auf allen Betriebssystemen erledigen.'));
    const actions=el('div',undefined,'extra-actions');
    const test=localButton('Ordnerfreigabe anfragen',()=>requestDesktopAccess()),repair=localButton('Ordneranbindung erneut einrichten',()=>requestDesktopAccess(true));
    test.disabled=repair.disabled=!localDesktopAvailable()||!value.desktop_registered;actions.append(test,repair);desktopPanel.append(actions);
    desktopPanel.append(el('p',value.desktop_registered?'Die Anbindung ist laut lokaler Einrichtung registriert. Der Dialogtest prüft, ob sie auf diesem Rechner tatsächlich antwortet.':'Einrichtung fehlt: die lokale Starten-Datei im Installationsordner ausführen. Das richtet die Anbindung für deinen Benutzer ein.','small-note'));
    if(value.desktop_test)desktopPanel.append(el('p','Letzte Rückmeldung des lokalen Ordnerdialogs: '+managerDate(value.desktop_test.checked,true)+' · '+(value.desktop_test.status==='selected'?'Ordner ausgewählt':'Auswahl abgebrochen'),'small-note'));
    const help=el('details');help.append(el('summary','Eine Freigabe wurde abgelehnt – was tun?'),el('p','Browser: In den Website-Einstellungen für localhost die Anfrage zum Öffnen externer Anwendungen wieder erlauben. Danach „Ordnerfreigabe anfragen“ anklicken. Eine dauerhaft abgelehnte Anfrage kann die Website nicht selbst zurücksetzen.'),el('p','macOS: Systemeinstellungen → Datenschutz & Sicherheit → Dateien & Ordner. Den Zugriff für die Ordneranbindung bzw. die angezeigte Anwendung erlauben. Windows: Bei gesperrtem Ordner den überwachten Ordnerzugriff unter Windows-Sicherheit prüfen. Linux: Ordnerrechte und Desktop-Sitzung prüfen; für den Auswahldialog wird zenity oder kdialog benötigt.'),el('p','Docker: Freigaben für Speicherordner werden in Docker Desktop verwaltet. Ist Docker oder der Manager beendet, startet die lokale Starten-Datei die Umgebung wieder. Betriebssystemfreigaben werden nicht pauschal angefordert.'));
    desktopPanel.append(help);
}
const routeBeforeServices=route;route=async function(){const entering=isServiceView()&&!servicesEntering;servicesEntering=isServiceView();await routeBeforeServices();if(entering){await renderSystemServices();if(!jobActive('system-services'))await checkSystemServices();}};
const refreshBeforeServices=refresh;refresh=async function(force=false){if(systemManagerStopped)return;await refreshBeforeServices(force);if(view==='system'&&isServiceView())await renderSystemServices();};
const openFolderBeforeSystemHelp=openProjectFolder;
openProjectFolder=function(p){openFolderBeforeSystemHelp(p);const d=$('#project-folder-dialog');if(!d)return;d.querySelector('.extra-actions')?.append(localButton('Dienste & Rechte',()=>{d.close();location.hash='#system/infrastructure';}));};

function localHelperAvailable() {
    const platform = navigator.userAgentData?.platform || navigator.platform;
    return /^mac/i.test(platform) && location.protocol === 'http:' && location.port === '8090' &&
        ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
}

async function requestLocalHelper(action) {
    const endpoint = '/api/safari-alarm';
    const options = {signal: AbortSignal.timeout?.(5000)};
    if (action) {
        options.method = 'POST';
        options.headers = {'Content-Type': 'application/json', 'X-VMM-Request': '1'};
        options.body = JSON.stringify({action});
    }
    const response = await fetch(endpoint + (action ? '/launch' : ''), options);
    if (!response.ok) throw new Error('Die Verbindung zum Tentacle Helfer ist fehlgeschlagen.');
    return response.json();
}

function localHelperActionComplete(action, current, previous) {
    if (!current?.available) return false;
    if (action === 'stop') return !current.running;
    if (action === 'start') return current.running;
    return current.running && Number.isInteger(current.pid) && current.pid !== previous?.pid;
}

async function openLocalHelperControl(action, startup = false) {
    const label = startup ? 'Helfer starten' : serviceActionLabels[action];
    const dialog = simpleDialog(startup ? 'Tentacle Helfer' : 'Tentacle Helfer · ' + label);
    dialog.firstElementChild.id = 'safari-alarm-title';
    dialog.setAttribute('aria-labelledby', 'safari-alarm-title');
    const details = {
        start: 'Der lokale Dienst wird gestartet.',
        restart: 'Der lokale Dienst wird beendet und erneut gestartet.',
        stop: 'Der lokale Dienst wird beendet. Du kannst ihn hier jederzeit wieder starten.'
    };
    const description = el('p', startup ?
        'Der Tentacle Helfer ist derzeit nicht aktiv. Bitte starte den Dienst, damit alle Funktionen des Tentacle Project Managers verfügbar sind.' :
        details[action]);
    description.id = 'safari-alarm-description';
    dialog.setAttribute('aria-describedby', description.id);
    const note = el('p', 'Wenn dein Browser fragt, ob er die lokale App öffnen darf, bestätige das Öffnen.', 'small-note');
    const status = el('p', '', 'small-note');
    status.setAttribute('role', 'status');

    let launchRequest, previous, renewal, pending = false;
    const launch = el('a', label, (action === 'stop' ? 'danger' : 'primary') + ' folder-open-link');
    launch.hidden = true;
    const retry = localButton('Erneut versuchen', () => prepareLaunch(true));
    retry.hidden = true;
    const footer = el('footer');
    if (!startup) footer.append(localButton('Abbrechen', () => dialog.close()));
    footer.append(retry, launch);
    dialog.append(description, note, status, footer);

    async function prepareLaunch(showProgress = false) {
        clearTimeout(renewal);
        launch.hidden = retry.hidden = true;
        if (showProgress) status.textContent = 'Aktion wird vorbereitet …';
        try {
            const [prepared, baseline] = await Promise.all([
                requestLocalHelper(action),
                action === 'restart' ? requestLocalHelper() : null
            ]);
            if (!dialog.open) return;
            const validFor = prepared.expires * 1000 - Date.now();
            if (!/^tentacle-project:\/\/safari-alarm\/[a-f0-9]{32}$/.test(prepared.url) || !Number.isFinite(validFor) || validFor <= 0) {
                throw new Error('Der Startlink ist ungültig.');
            }
            launchRequest = prepared;
            previous = baseline;
            launch.href = prepared.url;
            launch.hidden = false;
            if (showProgress) status.textContent = '';
            renewal = setTimeout(prepareLaunch, Math.max(1000, validFor - 15000));
        } catch {
            if (!dialog.open) return;
            status.textContent = 'Der Startlink konnte nicht vorbereitet werden. Versuche es erneut.';
            retry.hidden = false;
        }
    }

    launch.addEventListener('click', event => {
        if (pending || !launchRequest || Date.now() >= launchRequest.expires * 1000) {
            event.preventDefault();
            if (!pending) {
                status.textContent = 'Der Link wird erneuert. Klicke anschließend erneut auf „' + label + '“.';
                prepareLaunch();
            }
            return;
        }
        pending = true;
        clearTimeout(renewal);
        launch.setAttribute('aria-disabled', 'true');
        status.textContent = 'Warte auf den lokalen Helfer …';
        waitForHelper();
    });

    async function waitForHelper() {
        const deadline = Date.now() + 30000;
        while (dialog.open && Date.now() < deadline) {
            await new Promise(resolve => setTimeout(resolve, 900));
            if (!dialog.open) return;
            const current = await requestLocalHelper().catch(() => null);
            if (dialog.open && localHelperActionComplete(action, current, previous)) {
                dialog.close();
                if (!startup) {
                    const result = {start: 'läuft.', restart: 'wurde neu gestartet.', stop: 'wurde beendet.'};
                    message('Der Tentacle Helfer ' + result[action]);
                    if (view === 'system' && isServiceView()) renderSystemServices().catch(() => {});
                }
                return;
            }
        }
        if (!dialog.open) return;
        pending = false;
        launch.removeAttribute('aria-disabled');
        status.textContent = 'Der Helfer hat noch nicht geantwortet. Prüfe, ob der Browser lokale Apps öffnen darf, und versuche es erneut.';
        prepareLaunch();
    }

    const closed = new Promise(resolve => dialog.addEventListener('close', () => {
        clearTimeout(renewal);
        resolve();
    }, {once: true}));
    dialog.showModal();
    prepareLaunch(true);
    await closed;
}

const safariAlarmStartup = (async () => {
    if (!localHelperAvailable()) return;
    const initial = await requestLocalHelper().catch(() => null);
    if (initial?.available && !initial.running) await openLocalHelperControl('start', true);
})();
