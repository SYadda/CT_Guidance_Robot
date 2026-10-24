'use strict';
const $ = id => document.getElementById(id);
let calibrationId = null, candidateId = null, phase = 'idle', busy = false;
let bedPoints = [], markingBed = false;
let monitoring = false, selectedExam = null, monitorId = null, revision = 0;
let loopPromise = null, requestController = null, freshnessTimer = null;
let hasResult = false;
const SAMPLE_INTERVAL_MS = 1000;
const EXAMS = {head_ct:'Head CT',body_ct:'Chest / Abdomen / Pelvis CT'};

function drawBoxes(boxes,className='box',append=false) {
  if (!append) $('overlay').replaceChildren();
  boxes.forEach(box => {
    const el = document.createElement('div');el.className=className;
    if (box.reason) el.title=box.reason;
    Object.assign(el.style,{left:`${box.x*100}%`,top:`${box.y*100}%`,width:`${box.width*100}%`,height:`${box.height*100}%`});
    $('overlay').append(el);
  });
}
function drawCalibration() {
  drawBoxes([]);
  drawBedOutline(true);
  $('bedHint').textContent=markingBed ? ['Click a corner at the HEAD end.','Continue around the bed perimeter.','Click the third bed corner.','Click the remaining bed corner.'][bedPoints.length] : bedPoints.length===4 ? 'Review the automatically generated yellow outline. Corners 1–2 mark the HEAD end; swap ends if needed.' : 'Bed was not identified reliably. Mark its four corners, starting at a HEAD corner.';
}
function drawBedOutline(markers=false) {
  if(phase!=='review') return;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 1000 1000');svg.setAttribute('preserveAspectRatio','none');svg.classList.add('bed-map');
  if(bedPoints.length>1){
    const line=document.createElementNS(svg.namespaceURI,bedPoints.length===4?'polygon':'polyline');
    line.setAttribute('points',bedPoints.map(p=>`${p[0]*1000},${p[1]*1000}`).join(' '));
    line.setAttribute('fill',bedPoints.length===4?'#ffd70015':'none');line.setAttribute('stroke','#f2c400');line.setAttribute('stroke-width','5');svg.append(line);
  }
  $('overlay').append(svg);
  if(markers) bedPoints.forEach((p,i)=>{const marker=document.createElement('span');marker.className='bed-point';marker.textContent=i+1;
    Object.assign(marker.style,{left:`${p[0]*100}%`,top:`${p[1]*100}%`});$('overlay').append(marker);});
}
function errorText(error) {
  const known={NotAllowedError:'Camera permission was denied. Allow camera access and try again.',NotFoundError:'No camera was found. Connect a camera and try again.',NotReadableError:'The camera is unavailable or in use by another application.',OverconstrainedError:'The selected camera is unavailable. Reconnect it and try again.',AbortError:'The request timed out. Please try again.'};
  return known[error.name] || (error.message && /^[\x00-\x7F]+$/.test(error.message) ? error.message : 'The operation failed. Please try again.');
}
async function api(route,body,signal) {
  const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:signal ? AbortSignal.any([signal,AbortSignal.timeout(10000)]) : AbortSignal.timeout(25000)});
  const result=await response.json();
  if (!response.ok) {
    if (result.requires_calibration && route==='/api/check') {calibrationId=null;phase='idle';}
    throw new Error(result.error || 'The request failed. Please try again.');
  }
  return result;
}
function controls() {
  $('calibrationStatus').textContent=calibrationId ? 'Bed outline confirmed' : 'Bed not calibrated';
  $('recalibrate').hidden=!calibrationId || phase==='review';
  $('mainAction').hidden=phase==='review' || !!calibrationId;
  $('examActions').hidden=!calibrationId || phase==='review';
  $('headCT').hidden=monitoring && selectedExam==='head_ct';
  $('bodyCT').hidden=monitoring && selectedExam==='body_ct';
  $('headCT').disabled=busy;$('bodyCT').disabled=busy;
  $('stopMonitoring').hidden=!monitoring;
  $('mainAction').textContent='Calibrate';
  $('reviewActions').hidden=phase!=='review';
  $('bedActions').hidden=phase!=='review';$('bedHint').hidden=phase!=='review';
  $('frame').className=markingBed ? 'drawing' : '';
  for (const id of ['mainAction','recalibrate','confirm','retake','cancel','markBed','clearBed','swapEnds','bedConfirmed']) $(id).disabled=busy;
  $('confirm').disabled=busy || bedPoints.length!==4 || !$('bedConfirmed').checked;
  $('progress').hidden=!busy;
}
function clearView() {
  hasResult=false;
  ['title','frame','download','error','cameraNote','legend','guidance','monitorStatus'].forEach(id => {$(id).hidden=true;});
  $('overlay').replaceChildren();$('hint').textContent='';
}
async function photo(data,filename) {
  $('photo').src=data;await $('photo').decode();$('frame').hidden=false;
  $('download').href=data;$('download').download=filename;$('download').hidden=false;
}
async function run(operation) {
  if (busy) return;
  busy=true;$('error').hidden=true;controls();
  try {await operation();} catch (error) {$('error').textContent=errorText(error);$('error').hidden=false;}
  finally {busy=false;controls();}
}
async function calibrate() {
  await stopMonitoring();
  await run(async () => {
    phase='idle';candidateId=null;markingBed=false;bedPoints=[];$('bedConfirmed').checked=false;clearView();
    $('progress').textContent='Opening camera…';
    const capture=await cameraCapture.capture(5,(n,total)=>{$('progress').textContent=`Capturing bed ${n} of ${total}…`;});
    $('progress').textContent='Preparing bed outline…';
    const result=await api('/api/calibration/capture',capture);
    candidateId=result.candidate_id;
    bedPoints=result.bed_corners || [];
    await photo(result.preview,'bed-outline-preview.jpg');
    phase='review';$('title').textContent='Review bed outline';$('title').className='';$('title').hidden=false;
    $('hint').textContent='Check the yellow bed outline and head end, then confirm them. Use an unobstructed bed for automatic detection, or mark the corners manually.';
    drawCalibration();
  });
}
function outside(message) {
  $('title').textContent=hasResult ? 'Outside criteria' : '';
  $('title').className=hasResult ? 'blocked' : '';$('title').hidden=!hasResult;
  $('hint').textContent=message;
}
function invalidateResult(message) {
  clearTimeout(freshnessTimer);outside(message);
  $('overlay').replaceChildren();$('guidance').hidden=true;
}
async function stopMonitoring() {
  if(monitoring) invalidateResult('Monitoring paused.');
  monitoring=false;revision++;clearTimeout(freshnessTimer);
  requestController?.abort();cameraCapture.stop();
  const pending=loopPromise;
  if(pending) await pending;
  loopPromise=null;controls();
}
async function monitor(exam) {
  if(busy) return;
  hasResult=false;$('title').hidden=true;
  busy=true;controls();
  await stopMonitoring();
  selectedExam=exam;monitorId=crypto.randomUUID();
  const currentRevision=revision;
  clearView();outside('Starting monitoring. Keep still while your position is checked.');
  $('monitorStatus').textContent=EXAMS[exam]+' - starting camera...';$('monitorStatus').hidden=false;
  try {await cameraCapture.start();}
  catch(error) {
    outside('Monitoring unavailable.');$('error').textContent=errorText(error);$('error').hidden=false;
    busy=false;controls();return;
  }
  if(revision!==currentRevision) {cameraCapture.stop();busy=false;controls();return;}
  busy=false;monitoring=true;controls();
  loopPromise=(async()=>{
    while(monitoring && revision===currentRevision) {
      const started=performance.now();requestController=new AbortController();
      try {
        const capture=await cameraCapture.snapshot();
        if(revision!==currentRevision) break;
        const result=await api('/api/check',{...capture,calibration_id:calibrationId,
          exam_type:exam,monitor_id:monitorId},requestController.signal);
        if(revision!==currentRevision) break;
        await photo(capture.images[0],`patient-monitor-${Date.now()}.jpg`);
        if(revision!==currentRevision) break;
        if(performance.now()-started>3000) {
          result.ready=false;result.status='Outside criteria';
          result.message='Processing is too slow for a fresh result.';result.pose_ready=false;
        }
        hasResult=true;
        $('title').textContent=result.status;
        $('title').className=result.ready ? 'within' : 'blocked';$('title').hidden=false;
        $('hint').textContent=result.message==='Processing is too slow for a fresh result.' ? result.message : '';
        $('guidance').textContent=(result.guidance || []).join(' ');
        $('guidance').hidden=!(result.pose_boxes?.length && result.guidance?.length);
        drawBoxes(result.pose_boxes || [],'box pose');
        $('legend').hidden=false;
        $('monitorStatus').textContent=EXAMS[exam]+' - monitoring - '+new Date().toLocaleTimeString('en-GB');
        clearTimeout(freshnessTimer);
        freshnessTimer=setTimeout(()=>invalidateResult('Waiting for a fresh camera result.'),3000);
      } catch(error) {
        if(revision!==currentRevision) break;
        invalidateResult('Monitoring interrupted. Select a CT examination to restart.');
        $('error').textContent=errorText(error);$('error').hidden=false;
        monitoring=false;cameraCapture.stop();controls();break;
      }
      // Serialized requests avoid an accumulating queue of stale frames.
      const delay=Math.max(0,SAMPLE_INTERVAL_MS-(performance.now()-started));
      await new Promise(resolve=>setTimeout(resolve,delay));
    }
  })();
}
$('mainAction').onclick=calibrate;
$('headCT').onclick=()=>monitor('head_ct');
$('bodyCT').onclick=()=>monitor('body_ct');
$('stopMonitoring').onclick=async()=>{await stopMonitoring();outside('Monitoring stopped. Select a CT examination to restart.');$('monitorStatus').hidden=true;};
window.addEventListener('pagehide',()=>{monitoring=false;revision++;requestController?.abort();clearTimeout(freshnessTimer);cameraCapture.stop();});
document.addEventListener('visibilitychange',()=>{if(document.hidden && monitoring){
  stopMonitoring();invalidateResult('Monitoring paused. Select a CT examination when you return.');
}});
$('recalibrate').onclick=calibrate;$('retake').onclick=calibrate;
$('confirm').onclick=()=>run(async()=>{
  $('progress').textContent='Confirming bed outline…';
  const result=await api('/api/calibration/confirm',{candidate_id:candidateId,bed_corners:bedPoints,bed_confirmed:$('bedConfirmed').checked});
  calibrationId=result.calibration_id;candidateId=null;phase='idle';clearView();
  $('hint').textContent='Bed outline confirmed. Select Head CT or Chest / Abdomen / Pelvis CT to start monitoring.';
});
$('cancel').onclick=()=>{candidateId=null;phase='idle';clearView();$('hint').textContent=calibrationId ? 'Previous bed outline is still active. Keep the camera fixed.' : 'Capture the bed, then confirm its outline and head end.';controls();};
$('markBed').onclick=()=>{bedPoints=[];markingBed=true;$('bedConfirmed').checked=false;drawCalibration();controls();};
$('clearBed').onclick=()=>{bedPoints=[];markingBed=false;$('bedConfirmed').checked=false;drawCalibration();controls();};
$('bedConfirmed').onchange=controls;
$('swapEnds').onclick=()=>{if(bedPoints.length===4){bedPoints=[...bedPoints.slice(2),...bedPoints.slice(0,2)];$('bedConfirmed').checked=false;drawCalibration();controls();}};
function point(event) {
  const rect=$('frame').getBoundingClientRect();
  return {x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
}
$('frame').onpointerdown=event=>{
  if(markingBed && !busy && phase==='review'){
    event.preventDefault();const p=point(event);bedPoints.push([p.x,p.y]);
    if(bedPoints.length===4){
      markingBed=false;
      const w=$('photo').naturalWidth,h=$('photo').naturalHeight;
      const len=(a,b)=>Math.hypot((a[0]-b[0])*w,(a[1]-b[1])*h);
      if(len(bedPoints[0],bedPoints[1])>len(bedPoints[1],bedPoints[2])*1.25)bedPoints=[bedPoints[0],bedPoints[3],bedPoints[2],bedPoints[1]];
    }
    drawCalibration();controls();return;
  }
};
fetch('/api/state',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('Could not connect to the local service.');return response.json();}).then(state=>{
  calibrationId=state.calibration_id;
  bedPoints=state.bed_corners || [];
  if(calibrationId)$('hint').textContent='Bed outline confirmed for this server session. Recalibrate if the camera or bed was moved.';
  controls();
}).catch(error=>{$('error').textContent=errorText(error);$('error').hidden=false;controls();});
