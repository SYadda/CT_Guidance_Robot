'use strict';
const cameraCapture = (() => {
  let activeStream = null;
  const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
  const stop = () => { if (activeStream) activeStream.getTracks().forEach(t => t.stop()); activeStream = null; };
  async function nextFrame(video) {
    if (video.requestVideoFrameCallback) {
      await new Promise((resolve,reject) => {
        const timer = setTimeout(() => {video.cancelVideoFrameCallback(callback);reject(new Error('No camera frame received. Please try again.'));},5000);
        const callback = video.requestVideoFrameCallback(() => {clearTimeout(timer);resolve();});
      });
    }
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) throw new Error('The camera frame is not ready. Please try again.');
  }
  async function capture(count,onProgress) {
    const media = navigator.mediaDevices;
    if (!media?.getUserMedia) throw new Error('Open this page on localhost in Chrome or Edge to enable camera access.');
    const note = document.getElementById('cameraNote'); note.hidden = true;
    const video = document.getElementById('video');
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
      if (!preferred) {note.textContent = devices.length === 1 ? 'No Global camera found. Using the laptop/default camera.' : 'No Global camera found. Using the default camera.';note.hidden = false;}
      video.srcObject = activeStream;
      let startupTimer;
      try {
        await Promise.race([video.play(),new Promise((_,reject) => {
          startupTimer=setTimeout(() => reject(new Error('The camera did not start. Please try again.')),7000);
        })]);
      } finally {clearTimeout(startupTimer);}
      await sleep(800); // Let exposure settle before collecting the baseline.
      const images = [];
      for (let i=0;i<count;i++) {
        if (i) await sleep(220);
        await nextFrame(video);
        const canvas = document.createElement('canvas');
        const scale = Math.min(1,1280/video.videoWidth);
        canvas.width = Math.round(video.videoWidth*scale);canvas.height = Math.round(video.videoHeight*scale);
        canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
        images.push(canvas.toDataURL('image/jpeg',.92));
        onProgress?.(i+1,count);
      }
      const settings = activeStream.getVideoTracks()[0].getSettings();
      return {images,camera:{device_id:settings.deviceId || preferred?.deviceId || devices[0]?.deviceId,
        width:video.videoWidth,height:video.videoHeight}};
    } finally {stop();video.srcObject = null;}
  }
  window.addEventListener('pagehide',stop);
  return {capture};
})();
