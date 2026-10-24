'use strict';
const cameraCapture = (() => {
  let activeStream = null;
  let camera = null;
  const video = document.getElementById('video');
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  function stop() {
    if (activeStream) activeStream.getTracks().forEach(track => track.stop());
    activeStream = null; camera = null; video.srcObject = null;
  }
  async function start() {
    if (activeStream?.active) return;
    const media = navigator.mediaDevices;
    if (!media?.getUserMedia) throw new Error('Open this page on localhost in Chrome or Edge to enable camera access.');
    const note = document.getElementById('cameraNote'); note.hidden = true;
    try {
      let devices = (await media.enumerateDevices()).filter(d => d.kind === 'videoinput');
      let preferred = devices.find(d => d.label.startsWith('Global'));
      const constraints = {width:{ideal:1920},height:{ideal:1080}};
      activeStream = await media.getUserMedia({video:{...constraints,...(preferred ? {deviceId:{exact:preferred.deviceId}} : {})},audio:false});
      devices = (await media.enumerateDevices()).filter(d => d.kind === 'videoinput');
      preferred = devices.find(d => d.label.startsWith('Global'));
      if (preferred && activeStream.getVideoTracks()[0].getSettings().deviceId !== preferred.deviceId) {
        stop();
        activeStream = await media.getUserMedia({video:{...constraints,deviceId:{exact:preferred.deviceId}},audio:false});
      }
      if (!preferred) {note.textContent='No Global camera found. Using the default camera.';note.hidden=false;}
      video.srcObject = activeStream;
      let timer;
      try {
        await Promise.race([video.play(),new Promise((_,reject) => {
          timer=setTimeout(() => reject(new Error('The camera did not start. Please try again.')),7000);
        })]);
      } finally {clearTimeout(timer);}
      await sleep(800);
      const settings=activeStream.getVideoTracks()[0].getSettings();
      camera={device_id:settings.deviceId || preferred?.deviceId || devices[0]?.deviceId,
        width:video.videoWidth,height:video.videoHeight};
    } catch (error) {stop();throw error;}
  }
  async function snapshot() {
    if (!activeStream?.active || activeStream.getVideoTracks()[0].readyState !== 'live') {
      throw new Error('Camera disconnected. Reconnect it and select a CT examination.');
    }
    if (video.requestVideoFrameCallback) {
      await new Promise((resolve,reject) => {
        const timer=setTimeout(() => {video.cancelVideoFrameCallback(callback);reject(new Error('No camera frame received. Please try again.'));},3000);
        const callback=video.requestVideoFrameCallback(() => {clearTimeout(timer);resolve();});
      });
    }
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) throw new Error('The camera frame is unavailable.');
    const canvas=document.createElement('canvas');
    const scale=Math.min(1,1280/video.videoWidth);
    canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
    canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
    return {images:[canvas.toDataURL('image/jpeg',.92)],camera:{...camera,width:video.videoWidth,height:video.videoHeight}};
  }
  async function capture(count,onProgress) {
    try {
      await start();
      const images=[];
      for(let i=0;i<count;i++) {
        if(i) await sleep(220);
        images.push((await snapshot()).images[0]);onProgress?.(i+1,count);
      }
      return {images,camera};
    } finally {stop();}
  }
  window.addEventListener('pagehide',stop);
  return {start,snapshot,stop,capture};
})();
