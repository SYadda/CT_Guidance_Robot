'use strict';
const $ = id => document.getElementById(id);
let calibrationId = null, candidateId = null, phase = 'idle', busy = false;
let ignored = [], drawing = false, drag = null;
let bedPoints = [], markingBed = false;

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
  drawBoxes(ignored,'box ignored');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 1000 1000');svg.setAttribute('preserveAspectRatio','none');svg.classList.add('bed-map');
  if(bedPoints.length>1){
    const line=document.createElementNS(svg.namespaceURI,bedPoints.length===4?'polygon':'polyline');
    line.setAttribute('points',bedPoints.map(p=>`${p[0]*1000},${p[1]*1000}`).join(' '));
    line.setAttribute('fill',bedPoints.length===4?'#ffd70015':'none');line.setAttribute('stroke','#f2c400');line.setAttribute('stroke-width','5');svg.append(line);
  }
  $('overlay').append(svg);
  bedPoints.forEach((p,i)=>{const marker=document.createElement('span');marker.className='bed-point';marker.textContent=i+1;
    Object.assign(marker.style,{left:`${p[0]*100}%`,top:`${p[1]*100}%`});$('overlay').append(marker);});
  $('bedHint').textContent=markingBed ? ['Click a corner at the HEAD end.','Continue around the bed perimeter.','Click the third bed corner.','Click the remaining bed corner.'][bedPoints.length] : bedPoints.length===4 ? 'Review the yellow outline. Corners 1–2 mark the HEAD end; swap ends if needed.' : 'Bed was not identified reliably. Mark its four corners, starting at a HEAD corner.';
}
function errorText(error) {
  const known={NotAllowedError:'Camera permission was denied. Allow camera access and try again.',NotFoundError:'No camera was found. Connect a camera and try again.',NotReadableError:'The camera is unavailable or in use by another application.',OverconstrainedError:'The selected camera is unavailable. Reconnect it and try again.',AbortError:'The request timed out. Please try again.'};
  return known[error.name] || (error.message && /^[\x00-\x7F]+$/.test(error.message) ? error.message : 'The operation failed. Please try again.');
}
async function api(route,body) {
  const response=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(25000)});
  const result=await response.json();
  if (!response.ok) {
    if (result.requires_calibration && route==='/api/check') {calibrationId=null;phase='idle';}
    throw new Error(result.error || 'The request failed. Please try again.');
  }
  return result;
}
function controls() {
  $('calibrationStatus').textContent=calibrationId ? 'Baseline confirmed' : 'Not calibrated';
  $('recalibrate').hidden=!calibrationId || phase==='review';
  $('mainAction').hidden=phase==='review';
  $('mainAction').textContent=calibrationId ? (phase==='result' ? 'Check again' : 'Check') : 'Calibrate';
  $('reviewActions').hidden=phase!=='review';$('maskActions').hidden=phase!=='review';
  $('maskHint').hidden=phase!=='review' || !drawing;
  $('bedActions').hidden=phase!=='review';$('bedHint').hidden=phase!=='review';
  $('ignore').textContent=drawing ? 'Done drawing' : 'Ignore area';
  $('ignore').className='secondary'+(drawing ? ' active' : '');
  $('frame').className=drawing || markingBed ? 'drawing' : '';
  for (const id of ['mainAction','recalibrate','confirm','retake','cancel','ignore','clearIgnored','markBed','clearBed','swapEnds','bedConfirmed']) $(id).disabled=busy;
  $('confirm').disabled=busy || bedPoints.length!==4 || !$('bedConfirmed').checked;
  $('progress').hidden=!busy;
}
function clearView() {
  ['title','frame','download','error','cameraNote','legend'].forEach(id => {$(id).hidden=true;});
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
  await run(async () => {
    phase='idle';candidateId=null;drawing=false;markingBed=false;bedPoints=[];ignored=[];$('bedConfirmed').checked=false;clearView();
    $('progress').textContent='Opening camera…';
    const capture=await cameraCapture.capture(5,(n,total)=>{$('progress').textContent=`Capturing baseline ${n} of ${total}…`;});
    $('progress').textContent='Building baseline preview…';
    const result=await api('/api/calibration/capture',capture);
    candidateId=result.candidate_id;
    bedPoints=result.bed_corners || [];
    await photo(result.preview,'room-baseline-preview.jpg');
    phase='review';$('title').textContent='Review baseline';$('title').className='';$('title').hidden=false;
    $('hint').textContent='The bed must be empty. Check the automatically detected yellow bed outline, then confirm it.';
    drawCalibration();
  });
}
async function check() {
  await run(async () => {
    phase='idle';clearView();$('progress').textContent='Opening camera…';
    const capture=await cameraCapture.capture(3,(n,total)=>{$('progress').textContent=`Capturing patient ${n} of ${total}…`;});
    await photo(capture.images[capture.images.length-1],`patient-check-${Date.now()}.jpg`);
    $('progress').textContent='Checking patient position and visible surroundings…';
    const result=await api('/api/check',{...capture,calibration_id:calibrationId});
    phase='result';$('title').textContent=result.ready ? 'ready' : 'not ready';
    $('title').className=result.ready ? 'ready' : 'blocked';$('title').hidden=false;
    $('hint').textContent=result.ready ? '' : result.message;
    drawBoxes(result.anomaly_boxes || []);
    drawBoxes(result.pose_boxes || [],'box pose',true);
    $('legend').hidden=false;
  });
}
$('mainAction').onclick=()=>calibrationId ? check() : calibrate();
$('recalibrate').onclick=calibrate;$('retake').onclick=calibrate;
$('confirm').onclick=()=>run(async()=>{
  $('progress').textContent='Confirming baseline…';
  const result=await api('/api/calibration/confirm',{candidate_id:candidateId,empty_room_confirmed:true,ignored_regions:ignored,bed_corners:bedPoints,bed_confirmed:$('bedConfirmed').checked});
  calibrationId=result.calibration_id;candidateId=null;phase='idle';drawing=false;clearView();
  $('hint').textContent='Baseline confirmed. Keep the camera fixed. Patient: lie on your back, both arms beside the torso or both overhead, and hold still.';
});
$('cancel').onclick=()=>{candidateId=null;phase='idle';drawing=false;clearView();$('hint').textContent=calibrationId ? 'Previous baseline is still active. Keep the camera fixed.' : 'Clear the room, then capture an empty-room baseline.';controls();};
$('ignore').onclick=()=>{drawing=!drawing;markingBed=false;drawCalibration();controls();};
$('clearIgnored').onclick=()=>{ignored=[];drawCalibration();};
$('markBed').onclick=()=>{bedPoints=[];markingBed=true;drawing=false;$('bedConfirmed').checked=false;drawCalibration();controls();};
$('clearBed').onclick=()=>{bedPoints=[];markingBed=false;$('bedConfirmed').checked=false;drawCalibration();controls();};
$('bedConfirmed').onchange=controls;
$('swapEnds').onclick=()=>{if(bedPoints.length===4){bedPoints=[...bedPoints.slice(2),...bedPoints.slice(0,2)];$('bedConfirmed').checked=false;drawCalibration();controls();}};
function point(event) {
  const rect=$('frame').getBoundingClientRect();
  return {x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};
}
function rectangle(a,b) {return {x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y)};}
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
  if (!drawing || busy || phase!=='review' || ignored.length>=8) return;
  event.preventDefault();drag=point(event);$('frame').setPointerCapture(event.pointerId);
};
$('frame').onpointermove=event=>{if(drag)drawBoxes([...ignored,rectangle(drag,point(event))],'box ignored');};
$('frame').onpointerup=event=>{
  if (!drag) return;
  const box=rectangle(drag,point(event));drag=null;
  if(box.width>.005 && box.height>.005)ignored.push(box);
  drawCalibration();
};
$('frame').onpointercancel=()=>{drag=null;drawCalibration();};
fetch('/api/state',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('Could not connect to the local service.');return response.json();}).then(state=>{
  calibrationId=state.calibration_id;
  if(calibrationId)$('hint').textContent='Baseline confirmed for this server session. Recalibrate if the camera was moved.';
  controls();
}).catch(error=>{$('error').textContent=errorText(error);$('error').hidden=false;controls();});
