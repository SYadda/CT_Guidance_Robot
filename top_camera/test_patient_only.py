"""Regression tests for the independent patient-only variant."""
import base64
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
from app import DemoServer
from calibration import BedCalibration, jpeg
from positioning import BedReference, Observation, PoseDetector, evaluate_pose

CAMERA={'device_id':'test','width':1000,'height':1000}
CORNERS=[[.25,.05],[.75,.05],[.75,.95],[.25,.95]]
BED=BedReference(CORNERS)


def patient(overhead=False):
    p=np.ones((33,5));p[:,:3]=[.5,.2,0]
    for i,xy in {0:(.5,.15),11:(.4,.25),12:(.6,.25),13:(.38,.38),14:(.62,.38),
                 15:(.39,.51),16:(.61,.51),23:(.44,.50),24:(.56,.50),
                 25:(.44,.70),26:(.56,.70),27:(.44,.89),28:(.56,.89)}.items():p[i,:2]=xy
    if overhead:
        for i,xy in {13:(.38,.16),14:(.62,.16),15:(.43,.08),16:(.57,.08)}.items():p[i,:2]=xy
    return Observation(p,None,(1000,1000))


class Detector:
    def __init__(self):self.overhead=False;self.missing=False;self.calls=0
    def observe(self,image,bed):
        self.calls+=1
        return None if self.missing else patient(self.overhead)
    def close(self):pass


class PatientOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.detector=Detector()
        self.server=DemoServer(('127.0.0.1',0),self.temp.name,self.detector)
        self.server.active=BedCalibration(CAMERA,(1000,1000));self.server.bed=BED
        self.server.active_id='calibration'
        self.image=Image.new('RGB',(1000,1000),'white')
    def tearDown(self):self.server.server_close();self.temp.cleanup()

    def test_background_changes_and_absent_segmentation_do_not_block(self):
        changed=self.image.copy();ImageDraw.Draw(changed).rectangle((0,0,200,999),fill='red')
        # Whole-frame colour changes are intentionally irrelevant to this branch.
        result=self.server.inspect([self.image,changed,Image.new('RGB',(1000,1000),'black')],'head_ct')
        self.assertTrue(result['ready']);self.assertFalse(result['scene_checked'])
        self.assertNotIn('scene_ready',result);self.assertNotIn('anomaly_boxes',result)

    def test_selected_protocol_controls_acceptance(self):
        self.assertTrue(self.server.inspect([self.image]*3,'head_ct')['ready'])
        result=self.server.inspect([self.image]*3,'body_ct')
        self.assertFalse(result['ready']);self.assertIn('Raise both arms above your head.',result['guidance'])
        self.detector.overhead=True
        self.assertTrue(self.server.inspect([self.image]*3,'body_ct')['ready'])
        self.assertFalse(self.server.inspect([self.image]*3,'head_ct')['ready'])

    def test_hands_on_chest_that_previously_passed_are_rejected(self):
        # These wrists are on their own sides and far enough apart to pass
        # the old side-of-midline rule, but lie inside the tapered torso.
        o=patient()
        o.points[15,:2]=[.425,.40];o.points[16,:2]=[.575,.40]
        result=evaluate_pose(o,BED,'head_ct')
        self.assertFalse(result['ready'])
        self.assertTrue(any('chest or abdomen' in b['reason'] for b in result['pose_boxes']))
        self.assertIn('Place both arms at your sides.',__import__('positioning').patient_result(result)['guidance'])
        # One hand is sufficient to fail, even if the other remains beside hip.
        o=patient();o.points[15,:2]=[.425,.40]
        self.assertFalse(evaluate_pose(o,BED,'head_ct')['ready'])

    def test_normal_arm_positions_allow_body_sizes_and_rotation(self):
        for scale in [.7,1,1.1]:
            for angle in [0,12,25]:
                o=patient();r=np.deg2rad(angle)
                rotation=np.array([[np.cos(r),-np.sin(r)],[np.sin(r),np.cos(r)]])
                o.points[:,:2]=.5+(o.points[:,:2]-.5)@rotation.T*scale
                self.assertTrue(evaluate_pose(o,BED,'head_ct')['ready'],(scale,angle))
        o=patient(True);o.points[15,0]=.49;o.points[16,0]=.51
        self.assertTrue(evaluate_pose(o,BED,'body_ct')['ready'])

    def test_automatic_bed_outline_on_light_dark_and_shorter_beds(self):
        from bed_detection import suggest_bed
        for background,bed_color,rectangle in [('#454550','#d0d3d5',(110,160,690,290)),
                                                ('#dadada','#555565',(110,160,690,290)),
                                                ('#454550','#d0d3d5',(190,100,610,340))]:
            image=Image.new('RGB',(800,450),background)
            ImageDraw.Draw(image).rectangle(rectangle,fill=bed_color)
            corners=suggest_bed(image)
            self.assertIsNotNone(corners,(background,rectangle))
            self.assertEqual(len(corners),4)
            BedReference(corners,image.size)
        self.assertIsNone(suggest_bed(Image.new('RGB',(800,450),'gray')))

    def test_daylight_white_table_is_preferred_over_black_floor_mat(self):
        from bed_detection import suggest_bed
        source=Image.open(Path(__file__).resolve().parent/'test_fixtures'/'daylight_calibration.jpg').convert('RGB')
        variants=[ImageEnhance.Brightness(source).enhance(gain) for gain in [.55,.75,1,1.25]]
        yy,xx=np.mgrid[:source.height,:source.width]
        shade=1-.30*np.exp(-((xx-source.width*.35)**2)/(2*(source.width*.2)**2))
        variants.append(Image.fromarray(np.clip(np.asarray(source)*shade[:,:,None],0,255).astype('uint8')))
        variants.append(source.rotate(2))
        target_lo=np.array([.14,.35]);target_hi=np.array([.79,.69])
        for index,image in enumerate(variants):
            corners=suggest_bed(image)
            self.assertIsNotNone(corners,index)
            a=np.asarray(corners);lo=a.min(axis=0);hi=a.max(axis=0)
            intersection=np.maximum(0,np.minimum(hi,target_hi)-np.maximum(lo,target_lo)).prod()
            iou=intersection/((hi-lo).prod()+(target_hi-target_lo).prod()-intersection)
            self.assertGreater(iou,.85,(index,corners))

    def test_monitoring_stability_and_missing_patient(self):
        for expected in [False,False,True]:
            self.assertEqual(self.server.inspect([self.image],'head_ct','session')['ready'],expected)
        self.assertEqual(self.detector.calls,3)
        self.detector.missing=True
        self.assertFalse(self.server.inspect([self.image],'head_ct','session')['ready'])

    def test_bed_confirmation_does_not_require_empty_room(self):
        self.server.pending={'id':'candidate','images':[self.image]*5,'camera':CAMERA,'time':__import__('time').monotonic()}
        state=self.server.confirm({'candidate_id':'candidate','bed_confirmed':True,'bed_corners':CORNERS})
        self.assertTrue(state['calibrated'])
        self.assertTrue((self.server.storage/'bed_reference.json').exists())
        self.assertFalse((self.server.storage/'baseline.jpg').exists())

    def test_people_outside_bed_are_not_selected_or_counted(self):
        def landmarks(points):
            return [SimpleNamespace(x=q[0],y=q[1],z=q[2],visibility=q[3],presence=q[4]) for q in points]
        outside=patient();outside.points[:,0]+=.45
        fake=SimpleNamespace(detect=lambda _:SimpleNamespace(pose_landmarks=[landmarks(outside.points),landmarks(patient().points)]))
        detector=PoseDetector();detector.detector=fake
        mp=SimpleNamespace(Image=lambda **kwargs:None,ImageFormat=SimpleNamespace(SRGB=0))
        with patch.dict('sys.modules',{'mediapipe':mp}):
            observation=detector.observe(self.image,BED)
            self.assertIsNotNone(observation);self.assertFalse(observation.extra_people)
            self.assertIsNone(observation.mask)
            self.assertTrue(evaluate_pose(observation,BED,'head_ct')['ready'])
            fake.detect=lambda _:SimpleNamespace(pose_landmarks=[landmarks(outside.points)])
            self.assertIsNone(detector.observe(self.image,BED))

    def test_real_http_monitoring_contract(self):
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        body={'images':['data:image/jpeg;base64,'+base64.b64encode(jpeg(self.image)).decode()],
              'camera':CAMERA,'calibration_id':'calibration','exam_type':'head_ct','monitor_id':'http'}
        try:
            for expected in [False,False,True]:
                request=urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/check',json.dumps(body).encode(),{'Content-Type':'application/json'})
                with urllib.request.urlopen(request) as response:result=json.load(response)
                self.assertEqual(result['ready'],expected)
                self.assertFalse(result['scene_checked'])
            self.assertEqual(result['status'],'Within criteria')
        finally:self.server.shutdown();thread.join()


if __name__=='__main__':unittest.main()
