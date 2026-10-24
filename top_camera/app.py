"""Bed-only calibration and continuous patient posture API."""
import argparse
import base64
import binascii
import json
import threading
import time
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from PIL import Image, UnidentifiedImageError
import numpy as np
from calibration import BedCalibration, read_image, jpeg, pixels
from positioning import BedReference, PoseDetector, evaluate_pose, patient_result, box_for, EXAM_PRESETS
from bed_detection import suggest_bed

ROOT = Path(__file__).resolve().parent
MAX_BODY = 24*1024*1024


class Conflict(ValueError):
    pass


def camera_details(value):
    if not isinstance(value,dict) or not isinstance(value.get('device_id'),str) or not value['device_id']:
        raise ValueError('A camera device ID is required.')
    for key in ('width','height'):
        if type(value.get(key)) is not int or not 1 <= value[key] <= 16000:
            raise ValueError('Invalid camera capture dimensions.')
    return {key:value[key] for key in ('device_id','width','height')}


def decode_images(body, count):
    values = body.get('images')
    if not isinstance(values,list) or len(values) != count:
        raise ValueError(f'Exactly {count} image(s) required.')
    result = []
    for value in values:
        if not isinstance(value,str) or not value.startswith('data:image/jpeg;base64,'):
            raise ValueError('Images must be JPEG data URLs.')
        result.append(read_image(base64.b64decode(value.split(',',1)[1],validate=True)))
    return result


class DemoServer(ThreadingHTTPServer):
    def __init__(self,address,storage=None,detector=None):
        super().__init__(address,Handler)
        self.storage = Path(storage) if storage else ROOT/'runtime'
        self.storage.mkdir(parents=True,exist_ok=True)
        self.lock = threading.RLock()
        self.pending = None
        self.monitoring = {}
        self.active = None
        self.active_id = None
        self.created_at = None
        self.bed = None
        self.pose_detector = detector if detector is not None else PoseDetector()

    def state(self):
        with self.lock:
            return {'calibrated':self.active is not None,'calibration_id':self.active_id,'created_at':self.created_at,
                    'bed_corners':self.bed.corners if self.bed else None}

    def confirm(self,body):
        with self.lock:
            pending = self.pending
            if not pending or body.get('candidate_id') != pending['id'] or time.monotonic()-pending['time'] > 300:
                raise Conflict('The bed preview expired or was replaced. Capture it again.')
            bed_calibration = BedCalibration(pending['camera'],pending['images'][0].size)
            if body.get('bed_confirmed') is not True:
                raise ValueError('Confirm the yellow bed outline before monitoring.')
            bed = BedReference(body.get('bed_corners'),pending['images'][0].size)
            identifier = uuid.uuid4().hex
            preview = pending['images'][0]
            # Persist before publishing the new bed calibration. Previous calibration remains on failure.
            (self.storage/'bed_reference.jpg').write_bytes(jpeg(preview))
            metadata = {'calibration_id':identifier,'camera':bed_calibration.camera,
                        'created_at':time.time(),'patient_only':True,'frames':5,'bed_corners':bed.corners}
            (self.storage/'bed_reference.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            self.active,self.active_id,self.created_at = bed_calibration,identifier,metadata['created_at']
            self.bed = bed
            self.monitoring.clear()
            self.pending = None
            return self.state()

    def inspect(self, images, exam_type=None, monitor_id=None):
        # Infer only new frames. Keep at most three observations per monitoring
        # session; no image buffers or repeated inference on historical frames.
        records = []
        now = time.monotonic()
        if monitor_id is not None:
            key = (monitor_id, exam_type, self.active_id)
            self.monitoring = {k:v for k,v in self.monitoring.items() if now-v[0] < 3}
            records = list(self.monitoring.get(key,(now,[]))[1])
        for image in images:
            try:
                observation = self.pose_detector.observe(image,self.bed)
                pose = evaluate_pose(observation,self.bed,exam_type)
            except (ImportError,RuntimeError,OSError,ValueError):
                import logging
                logging.exception('Patient analysis failed')
                observation = None
                pose = {'ready':False,'pose_boxes':[{'reason':'Patient analysis unavailable. Check local model and dependencies.',
                        **box_for(self.bed.corners)}],'arm_mode':None}
            records.append((observation,pose))
        records = records[-3:]
        if monitor_id is not None:
            if len(self.monitoring) >= 16 and key not in self.monitoring:
                self.monitoring.pop(next(iter(self.monitoring)))
            self.monitoring[key] = (time.monotonic(),records)
        observations = [r[0] for r in records]
        poses = [r[1] for r in records]
        pose = {**poses[-1], 'pose_boxes':list(poses[-1]['pose_boxes'])}
        if len(records) < 3:
            pose['pose_boxes'].append({'reason':'Capture three frames to verify that the patient is still.',**box_for(self.bed.corners)})
        elif observations[-1] is not None and sum(o is not None for o in observations)>=2:
            selected = [0,11,12,13,14,15,16,23,24,25,26,27,28]
            for earlier in observations[:-1]:
                if earlier is None: continue
                current = observations[-1]
                q = current.points[:,:2]*current.size
                r = earlier.points[:,:2]*earlier.size
                scale = max(np.linalg.norm(q[11]-q[12]),10)
                moves = np.linalg.norm(q[selected]-r[selected],axis=1)/scale
                if moves.max() > .60 or (moves>.30).sum()>=3:
                    ids = [selected[i] for i in np.flatnonzero(moves>.30)]
                    pose['pose_boxes'].append({'reason':'Patient moved during capture.',**box_for(current.points[ids])})
            if sum(item['ready'] for item in poses)<2:
                pose['pose_boxes'].append({'reason':'Position was not stable throughout capture.',**box_for(self.bed.corners)})
        else:
            pose['pose_boxes'].append({'reason':'Patient could not be tracked throughout capture.',**box_for(self.bed.corners)})
        pose['ready'] = not pose['pose_boxes']
        result = patient_result(pose)
        if exam_type is not None:
            result.update(exam_type=exam_type,reference_map=EXAM_PRESETS[exam_type]['reference_map'])
        result['observed_at'] = time.time()
        return result

    def server_close(self):
        self.pose_detector.close()
        super().server_close()

    def save_check(self,image,result):
        directory = self.storage/'checks'
        directory.mkdir(exist_ok=True)
        identifier = f'{time.time_ns()}_{uuid.uuid4().hex[:8]}'
        result['check_id'] = identifier
        image.thumbnail((1920,1920))
        (directory/f'{identifier}.jpg').write_bytes(jpeg(image))
        (directory/f'{identifier}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        files = sorted(p for p in directory.iterdir() if p.is_file())
        total = sum(p.stat().st_size for p in files)
        while len(files)>400 or total>250*1024*1024:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()


class Handler(BaseHTTPRequestHandler):
    def reply(self,code,payload,content_type='application/json; charset=utf-8'):
        data = json.dumps(payload).encode() if isinstance(payload,dict) else payload
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Permissions-Policy','camera=(self), microphone=()')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = urlsplit(self.path).path
        pages = {'/':('index.html','text/html'),'/check':('index.html','text/html'),'/check/':('index.html','text/html'),
                 '/app.js':('app.js','text/javascript'),'/camera.js':('camera.js','text/javascript')}
        if route in pages:
            filename,mime = pages[route]
            self.reply(200,(ROOT/'web'/filename).read_bytes(),mime+'; charset=utf-8')
        elif route == '/api/state':
            self.reply(200,self.server.state())
        else:
            self.reply(404,{'error':'Not found.'})

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in {'/api/calibration/capture','/api/calibration/confirm','/api/check'}:
            self.reply(404,{'error':'Not found.'})
            return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= MAX_BODY:
                self.close_connection = True
                self.reply(413,{'error':'Request must be no larger than 24 MB.'})
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body,dict):
                raise ValueError('Expected a JSON object.')
            if route == '/api/calibration/confirm':
                self.reply(200,self.server.confirm(body))
                return
            camera = camera_details(body.get('camera'))
            if route == '/api/calibration/capture':
                images = decode_images(body,5)
                if any(im.size != images[0].size for im in images):
                    raise ValueError('Calibration images must have the same dimensions.')
                identifier = uuid.uuid4().hex
                median = np.median(np.stack([pixels(im) for im in images]),axis=0)
                preview = Image.fromarray((median*255).astype('uint8'))
                with self.server.lock:
                    self.server.pending = {'id':identifier,'images':images,'camera':camera,'time':time.monotonic()}
                suggestion=suggest_bed(preview)
                self.reply(200,{'candidate_id':identifier,'preview':'data:image/jpeg;base64,'+base64.b64encode(jpeg(preview)).decode(),
                                'bed_corners':suggestion})
                return
            exam_type = body.get('exam_type')
            if exam_type not in EXAM_PRESETS:
                raise ValueError('Select Head CT or Chest / Abdomen / Pelvis CT.')
            monitor_id = body.get('monitor_id')
            if monitor_id is not None and (not isinstance(monitor_id,str) or not 1 <= len(monitor_id) <= 80):
                raise ValueError('Invalid monitoring session.')
            count = len(body.get('images',[]))
            if count not in (1,3):
                raise ValueError('Provide one review image or three camera frames.')
            if monitor_id is not None and count != 1:
                raise ValueError('Monitoring requires one new frame per request.')
            images = decode_images(body,count)
            image = images[-1]
            with self.server.lock:
                if self.server.active is None:
                    raise Conflict('Calibrate the bed before monitoring.')
                if body.get('calibration_id') != self.server.active_id:
                    raise Conflict('The calibration changed. Reload the page and calibrate again.')
                if camera != self.server.active.camera:
                    raise Conflict('The camera or capture resolution changed. Calibrate again.')
                if any(im.size != self.server.active.image_size for im in images):
                    raise Conflict('Capture size changed. Calibrate the bed again.')
                start = time.perf_counter()
                result = self.server.inspect(images,exam_type,monitor_id)
                result.update(calibration_id=self.server.active_id,elapsed_ms=round((time.perf_counter()-start)*1000))
                self.server.save_check(image,result)
                self.reply(200,result)
        except Conflict as error:
            self.reply(409,{'error':str(error),'requires_calibration':True})
        except (ValueError,TypeError,binascii.Error,UnidentifiedImageError,Image.DecompressionBombError) as error:
            self.reply(400,{'error':str(error)})
        except OSError:
            self.reply(500,{'error':'Could not read the image or save files locally. Please try again.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8001)
    parser.add_argument('--storage',type=Path,default=None)
    args = parser.parse_args()
    with DemoServer(('127.0.0.1',args.port),storage=args.storage) as server:
        print(f'Patient-only monitoring: http://localhost:{args.port}',flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
