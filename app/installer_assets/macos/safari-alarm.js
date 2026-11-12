ObjC.import('AppKit');
ObjC.import('AVFoundation');

const safariBundleId = 'com.apple.Safari';
const announcement = 'Achtung, Achtung! Bedrohung entdeckt: Safari Browser wurde geöffnet. Bitte schließen Sie dieses Programm, wenn Sie an Ihrem Leben hängen.';
const beaconCycle = 1.6;
const beaconFrameCount = 32;
const fadeDuration = 0.4;
const repeatPause = 3;

let statusPath;
let tone;
let synthesizer;
let voice;
let safariProcesses;
let safariFocused = false;
let beaconFrames;
let panels = [];
let overlayStarted;
let fadeStarted;
let audioCycle;

function writeStatus() {
    const status = {
        pid: Number($.NSProcessInfo.processInfo.processIdentifier),
        time: Math.floor(Date.now() / 1000),
    };
    return $(JSON.stringify(status)).writeToFileAtomicallyEncodingError(statusPath, true, $.NSUTF8StringEncoding, null);
}

function runningSafariProcesses() {
    const applications = $.NSRunningApplication.runningApplicationsWithBundleIdentifier(safariBundleId);
    const processes = new Set();
    for (let index = 0; index < applications.count; index++) {
        processes.add(Number(applications.objectAtIndex(index).processIdentifier));
    }
    return processes;
}

function safariIsFrontmost() {
    const frontmost = $.NSWorkspace.sharedWorkspace.frontmostApplication;
    return !frontmost.isNil() && ObjC.unwrap(frontmost.bundleIdentifier) === safariBundleId;
}

function red(alpha) {
    return $.NSColor.colorWithSRGBRedGreenBlueAlpha(1, 0.025, 0.09, alpha).CGColor;
}

function beaconImage(phase) {
    const color = (r, g, b, alpha = 1) => $.NSColor.colorWithSRGBRedGreenBlueAlpha(r, g, b, alpha);
    const gradient = (start, end) => $.NSGradient.alloc.initWithStartingColorEndingColor(start, end);
    const roundedRect = (x, y, w, h, radius) => $.NSBezierPath.bezierPathWithRoundedRectXRadiusYRadius(
        $.NSMakeRect(x, y, w, h), radius, radius);
    const point = (x, y) => $.NSMakePoint(x, y);
    const image = $.NSImage.alloc.initWithSize($.NSMakeSize(136, 136));
    const sweep = Math.sin(phase);
    const brightness = 0.78 + 0.22 * Math.cos(phase);
    image.lockFocus;
    try {
        const glow = point(68, 62);
        gradient(color(1, 0.07, 0.02, 0.62 * brightness), color(1, 0.04, 0.02, 0))
            .drawFromCenterRadiusToCenterRadiusOptions(glow, 13, glow, 66, 0);

        for (const degrees of [25, 54, 90, 126, 155]) {
            const angle = degrees * Math.PI / 180;
            const [x, y] = [Math.cos(angle), Math.sin(angle)];
            const intensity = 0.45 + 0.55 * (1 + Math.cos(phase - angle)) / 2;
            const ray = $.NSBezierPath.bezierPath;
            ray.moveToPoint(point(68 + x * 48, 63 + y * 48));
            ray.lineToPoint(point(68 + x * 61, 63 + y * 61));
            ray.setLineCapStyle($.NSLineCapStyleRound);
            ray.setLineWidth(3 + intensity);
            color(1, 0.69, 0.25, intensity).setStroke;
            ray.stroke;
        }

        const dome = $.NSBezierPath.bezierPath;
        dome.moveToPoint(point(33, 37));
        dome.lineToPoint(point(37, 72));
        dome.curveToPointControlPoint1ControlPoint2(point(68, 102), point(39, 91), point(51, 102));
        dome.curveToPointControlPoint1ControlPoint2(point(99, 72), point(85, 102), point(97, 91));
        dome.lineToPoint(point(103, 37));
        dome.closePath;
        gradient(color(0.48, 0.015, 0.07), color(1, 0.24, 0.14)).drawInBezierPathAngle(dome, 90);
        gradient(color(1, 0.94, 0.62, brightness), color(1, 0.19, 0.045, 0))
            .drawInBezierPathRelativeCenterPosition(dome, point(sweep * 0.65, -0.12));
        dome.setLineWidth(2);
        color(1, 0.44, 0.3).setStroke;
        dome.stroke;

        const reflection = $.NSBezierPath.bezierPath;
        reflection.moveToPoint(point(44, 72));
        reflection.curveToPointControlPoint1ControlPoint2(point(57, 91), point(46, 82), point(49, 87));
        reflection.setLineCapStyle($.NSLineCapStyleRound);
        reflection.setLineWidth(3.5);
        color(1, 0.93, 0.84, 0.85).setStroke;
        reflection.stroke;

        gradient(color(0.09, 0.09, 0.12), color(0.38, 0.26, 0.28))
            .drawInBezierPathAngle(roundedRect(29, 29, 78, 13, 5), 90);
        gradient(color(0.055, 0.055, 0.075), color(0.24, 0.21, 0.25))
            .drawInBezierPathAngle(roundedRect(23, 16, 90, 16, 6), 90);
    } finally {
        image.unlockFocus;
    }
    return image;
}

function warningPanel(screen) {
    const frame = screen.frame;
    const style = $.NSWindowStyleMaskBorderless | $.NSWindowStyleMaskNonactivatingPanel;
    const panel = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(frame, style, $.NSBackingStoreBuffered, false);
    panel.setOpaque(false);
    panel.setBackgroundColor($.NSColor.clearColor);
    panel.setHasShadow(false);
    panel.setIgnoresMouseEvents(true);
    panel.setHidesOnDeactivate(false);
    panel.setReleasedWhenClosed(false);
    panel.setLevel($.NSStatusWindowLevel);
    panel.setCollectionBehavior($.NSWindowCollectionBehaviorCanJoinAllSpaces |
        $.NSWindowCollectionBehaviorFullScreenAuxiliary | $.NSWindowCollectionBehaviorIgnoresCycle);

    const { width, height } = frame.size;
    const surface = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, width, height));
    surface.setWantsLayer(true);
    surface.layer.setBackgroundColor(red(0.24));
    surface.layer.setBorderColor(red(0.72));
    surface.layer.setBorderWidth(4);
    const visible = screen.visibleFrame;
    const size = Math.min(136, visible.size.width * 0.20, visible.size.height * 0.20);
    const inset = Math.min(12, size * 0.10);
    const left = visible.origin.x - frame.origin.x + inset;
    const bottom = visible.origin.y - frame.origin.y + inset;
    const right = left + visible.size.width - size - 2 * inset;
    const top = bottom + visible.size.height - size - 2 * inset;
    const lights = [];
    for (const x of [left, right]) {
        for (const y of [bottom, top]) {
            const light = $.NSImageView.alloc.initWithFrame($.NSMakeRect(x, y, size, size));
            light.setImageScaling($.NSImageScaleProportionallyUpOrDown);
            surface.addSubview(light);
            if (y === top) {
                light.setWantsLayer(true);
                light.setFrameCenterRotation(180);
            }
            lights.push(light);
        }
    }
    panel.setContentView(surface);
    panel.setAlphaValue(0);
    return {panel, lights};
}

function schedule(observer, interval, selector, repeat) {
    return $.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(interval, observer, selector, null, repeat);
}

function beginFade(now) {
    if (overlayStarted !== undefined && fadeStarted === undefined) {
        fadeStarted = now;
    }
}

function playAlarmTone(now) {
    audioCycle = {stage: 'tone', deadline: now + (tone.play ? tone.duration : 0)};
}

function finishAlarmCycle(now) {
    if (safariFocused) {
        audioCycle = {stage: 'pause', deadline: now + repeatPause};
    } else {
        audioCycle = undefined;
        beginFade(now);
    }
}

function advanceAlarmCycle(now) {
    if (!audioCycle) return;
    if (audioCycle.stage === 'speech') {
        if (synthesizer.isSpeaking) {
            audioCycle.started = true;
        } else if (audioCycle.started || now >= audioCycle.deadline) {
            finishAlarmCycle(now);
        }
        return;
    }
    if (now < audioCycle.deadline || synthesizer.isSpeaking) return;
    if (audioCycle.stage === 'pause') {
        playAlarmTone(now);
        return;
    }
    audioCycle = {stage: 'speech', deadline: now + 3, started: false};
    try {
        const words = $.AVSpeechUtterance.speechUtteranceWithString(announcement);
        words.setVoice(voice);
        synthesizer.speakUtterance(words);
    } catch (error) {
        console.log('Die Ansage konnte nicht abgespielt werden: ' + error);
        finishAlarmCycle(now);
    }
}

function showWarning(observer) {
    if (overlayStarted !== undefined && fadeStarted === undefined) return;
    if (overlayStarted === undefined) {
        if (!beaconFrames) {
            beaconFrames = Array.from({length: beaconFrameCount}, (_, index) =>
                beaconImage(index * 2 * Math.PI / beaconFrameCount));
        }
        const screens = $.NSScreen.screens;
        try {
            for (let index = 0; index < screens.count; index++) {
                panels.push(warningPanel(screens.objectAtIndex(index)));
            }
            for (const {panel} of panels) panel.orderFrontRegardless;
        } catch (error) {
            for (const {panel} of panels) panel.close;
            panels = [];
            throw error;
        }
        schedule(observer, 1 / 30, 'animate:', true);
    }
    overlayStarted = $.NSProcessInfo.processInfo.systemUptime;
    fadeStarted = undefined;
    playAlarmTone(overlayStarted);
}

function stopWarning() {
    audioCycle = undefined;
    beginFade($.NSProcessInfo.processInfo.systemUptime);
    tone.stop;
    synthesizer.stopSpeakingAtBoundary($.AVSpeechBoundaryImmediate);
}

ObjC.registerSubclass({
    name: 'TentacleSafariAlarmObserver',
    superclass: 'NSObject',
    methods: {
        'checkSafari:': {
            types: ['void', ['id']],
            implementation() {
                const current = runningSafariProcesses();
                const opened = [...current].some(pid => !safariProcesses.has(pid));
                const wasFocused = safariFocused;
                safariProcesses = current;
                safariFocused = safariIsFrontmost();
                try {
                    if (safariFocused || opened) {
                        showWarning(this);
                    } else if (wasFocused) {
                        stopWarning();
                    }
                } catch (error) {
                    console.log('Safari-Alarm konnte nicht ausgelöst werden: ' + error);
                }
            },
        },
        'heartbeat:': {
            types: ['void', ['id']],
            implementation() { writeStatus(); },
        },
        'animate:': {
            types: ['void', ['id']],
            implementation(timer) {
                const now = $.NSProcessInfo.processInfo.systemUptime;
                const elapsed = now - overlayStarted;
                advanceAlarmCycle(now);

                const remaining = fadeStarted === undefined ? 1 : 1 - (now - fadeStarted) / fadeDuration;
                if (remaining <= 0) {
                    timer.invalidate;
                    for (const {panel} of panels) panel.close;
                    panels = [];
                    overlayStarted = undefined;
                    return;
                }

                const envelope = Math.min(1, elapsed / fadeDuration, remaining);
                const pulse = 0.90 + 0.10 * Math.sin(elapsed * 2 * Math.PI / 3.2);
                const frame = Math.floor(elapsed * beaconFrameCount / beaconCycle);
                for (const {panel, lights} of panels) {
                    panel.setAlphaValue(envelope * pulse);
                    lights.forEach((light, index) => {
                        const offset = index * beaconFrameCount / lights.length;
                        light.setImage(beaconFrames[(frame + offset) % beaconFrameCount]);
                    });
                }
            },
        },
    },
});

function run(argv) {
    if (argv.length !== 2 || !argv[0].startsWith('/') || !argv[1].startsWith('/')) {
        throw new Error('Der Safari-Alarm benötigt absolute Pfade für Status und Alarmton.');
    }
    statusPath = argv[0];
    tone = $.NSSound.alloc.initWithContentsOfFileByReference(argv[1], true);
    if (tone.isNil()) throw new Error('Der Alarmton konnte nicht geladen werden.');
    synthesizer = $.AVSpeechSynthesizer.alloc.init;
    voice = $.AVSpeechSynthesisVoice.voiceWithLanguage('de-DE');

    const app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
    const observer = $.TentacleSafariAlarmObserver.alloc.init;
    // The script host does not reliably receive workspace launch notifications.
    safariProcesses = runningSafariProcesses();
    schedule(observer, 0.25, 'checkSafari:', true);
    if (!writeStatus()) throw new Error('Der Safari-Alarm konnte seinen Status nicht speichern.');
    schedule(observer, 5, 'heartbeat:', true);
    app.run;
}
