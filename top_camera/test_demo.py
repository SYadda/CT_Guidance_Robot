import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
from app import DemoServer
from calibration import BackgroundCalibration, jpeg
from positioning import BedReference, Observation, evaluate_pose, patient_exclusion, combine_checks

CAMERA = {'device_id':'test-camera','width':640,'height':360}
BED = [[.22,.28],[.22,.61],[.78,.61],[.78,.28]]


class NoPatient:
    def observe(self,image,bed): return None
    def close(self): pass


def scene():
    rng = np.random.default_rng(12)
    yy,xx = np.mgrid[0:360,0:640]
    gray = np.clip(100+xx*.08+yy*.05+rng.normal(0,2,(360,640)),0,255).astype('uint8')
    image = Image.fromarray(np.stack([gray,gray,gray],axis=2))
    draw = ImageDraw.Draw(image)
    for x in range(0,640,80):
        draw.line((x,0,x,360), fill=(90,95,100),width=2)
    draw.rectangle((140,100,500,220),fill=(205,210,215))
    draw.rectangle((170,120,470,200),fill=(155,165,175))
    return image


def with_object(image):
    result = image.copy()
    ImageDraw.Draw(result).rectangle((55,240,135,320),fill=(180,35,20))
    return result


def encoded(image):
    return 'data:image/jpeg;base64,'+base64.b64encode(jpeg(image)).decode()


class CalibrationTests(unittest.TestCase):
    def test_reference_light_and_objects(self):
        image = scene()
        baseline = BackgroundCalibration.create([image]*5,CAMERA,[])
        self.assertTrue(baseline.predict(image)['ready'])
        for gain in (.75,1.2):
            self.assertTrue(baseline.predict(ImageEnhance.Brightness(image).enhance(gain))['ready'])
        result = baseline.predict(with_object(image))
        self.assertFalse(result['ready'])
        self.assertTrue(result['anomaly_boxes'])
        box = result['anomaly_boxes'][0]
        self.assertLess(box['x'],.15)
        self.assertGreater(box['x']+box['width'],.20)

    def test_ignored_area(self):
        image = scene()
        baseline = BackgroundCalibration.create([image]*5,CAMERA,[{'x':.05,'y':.6,'width':.2,'height':.33}])
        self.assertTrue(baseline.predict(with_object(image))['ready'])
        changed = image.copy()
        ImageDraw.Draw(changed).rectangle((360,260,450,330),fill='black')
        self.assertFalse(baseline.predict(changed)['ready'])

    def test_bad_calibration_and_photo(self):
        image = scene()
        with self.assertRaises(ValueError):
            BackgroundCalibration.create([Image.new('RGB',(640,360))]*5,CAMERA,[])
        changed = image.copy()
        ImageDraw.Draw(changed).rectangle((20,20,620,340),fill='white')
        with self.assertRaises(ValueError):
            BackgroundCalibration.create([image,image,changed,changed,image],CAMERA,[])
        with self.assertRaises(ValueError):
            BackgroundCalibration.create([image]*5,CAMERA,[{'x':0,'y':0,'width':1,'height':1}])
        self.assertFalse(BackgroundCalibration.create([image]*5,CAMERA,[]).predict(Image.new('RGB',image.size))['ready'])


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = DemoServer(('127.0.0.1',0),self.temp.name,detector=NoPatient())
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.image = scene()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self,path,body):
        req = urllib.request.Request(self.url+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as result:
                return result.status,json.load(result)
        except urllib.error.HTTPError as result:
            with result:
                return result.code,json.load(result)

    def capture(self):
        code,result = self.post('/api/calibration/capture',{'images':[encoded(self.image)]*5,'camera':CAMERA})
        self.assertEqual(code,200)
        return result['candidate_id']

    def confirm(self,candidate):
        return self.post('/api/calibration/confirm',{'candidate_id':candidate,'empty_room_confirmed':True,'ignored_regions':[],'bed_corners':BED,'bed_confirmed':True})

    def check(self,identifier,image=None,camera=None):
        return self.post('/api/check',{'images':[encoded(image if image is not None else self.image)],'camera':camera or CAMERA,'calibration_id':identifier})

    def test_full_flow_and_archive_output(self):
        self.assertEqual(self.check('missing')[0],409)
        candidate = self.capture()
        self.assertEqual(self.check('missing')[0],409)
        self.assertEqual(self.post('/api/calibration/confirm',{'candidate_id':candidate})[0],400)
        self.assertEqual(self.post('/api/calibration/confirm',{'candidate_id':candidate,
            'empty_room_confirmed':True,'bed_corners':BED,'bed_confirmed':False})[0],400)
        code,state = self.confirm(candidate)
        self.assertEqual(code,200)
        self.assertTrue(state['calibrated'])
        code,result = self.check(state['calibration_id'])
        self.assertEqual(code,200)
        self.assertFalse(result['ready'])  # Empty room is no longer sufficient.
        self.assertTrue(result['scene_ready'])
        self.assertFalse(result['pose_ready'])
        self.assertTrue(result['pose_boxes'])
        code,result = self.check(state['calibration_id'],with_object(self.image))
        self.assertEqual(code,200)
        self.assertFalse(result['ready'])
        self.assertTrue(result['anomaly_boxes'])
        self.assertTrue((Path(self.temp.name)/'baseline.jpg').exists())
        self.assertTrue((Path(self.temp.name)/'checks'/f"{result['check_id']}.jpg").exists())

    def test_recalibration_camera_and_session(self):
        _,first = self.confirm(self.capture())
        first_id = first['calibration_id']
        self.assertEqual(self.check(first_id,camera={**CAMERA,'device_id':'different'})[0],409)
        self.assertEqual(self.check(first_id,camera={**CAMERA,'width':1280})[0],409)
        candidate = self.capture()
        self.assertTrue(self.check(first_id)[1]['scene_ready'])
        _,second = self.confirm(candidate)
        self.assertNotEqual(first_id,second['calibration_id'])
        self.assertEqual(self.check(first_id)[0],409)
        self.assertEqual(self.confirm(candidate)[0],409)
        another = DemoServer(('127.0.0.1',0),self.temp.name)
        try:
            self.assertFalse(another.state()['calibrated'])
        finally:
            another.server_close()

    def test_invalid_inputs_and_expired_candidate(self):
        for body in ([],{}, {'images':['bad']*5,'camera':CAMERA}):
            self.assertEqual(self.post('/api/calibration/capture',body)[0],400)
        candidate = self.capture()
        self.server.pending['time'] -= 301
        self.assertEqual(self.confirm(candidate)[0],409)
        self.assertFalse(self.server.state()['calibrated'])

    def test_current_pages_only(self):
        for path,mime in [('/','text/html'),('/check','text/html'),('/app.js','text/javascript'),('/camera.js','text/javascript'),('/api/state','application/json')]:
            with urllib.request.urlopen(self.url+path) as result:
                self.assertIn(mime,result.headers['Content-Type'])
                self.assertTrue(result.read())
        self.assertEqual(self.post('/api/quick-check',{})[0],404)


if __name__ == '__main__':
    unittest.main()
