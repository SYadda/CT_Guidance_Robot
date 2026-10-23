import unittest
import numpy as np
from PIL import Image, ImageDraw
from positioning import BedReference, Observation, evaluate_pose, patient_exclusion, combine_checks
from calibration import BackgroundCalibration
from app import DemoServer
from test_demo import scene, with_object, CAMERA

BED = BedReference([[.25,.05],[.75,.05],[.75,.95],[.25,.95]])


def patient():
    p = np.ones((33,5)); p[:,:3] = [.5,.2,0]
    for i,xy in {0:(.5,.15),11:(.4,.25),12:(.6,.25),13:(.38,.38),14:(.62,.38),
                 15:(.39,.51),16:(.61,.51),23:(.44,.50),24:(.56,.50),
                 25:(.44,.70),26:(.56,.70),27:(.44,.89),28:(.56,.89)}.items(): p[i,:2]=xy
    return Observation(p,np.zeros((360,640)),(1000,1000))


class PoseRulesTests(unittest.TestCase):
    def test_accepts_sides_and_overhead_without_silhouette_match(self):
        for scale in [.65,1,1.1]:
            o=patient();o.points[:,:2]=.5+(o.points[:,:2]-.5)*scale
            self.assertTrue(evaluate_pose(o,BED)['ready'])
        for width in [.75,1.25]:
            o=patient();o.points[:,0]=.5+(o.points[:,0]-.5)*width
            self.assertTrue(evaluate_pose(o,BED)['ready'])
        o=patient()
        o.points[13,:2]=[.38,.16];o.points[14,:2]=[.62,.16]
        o.points[15,:2]=[.43,.08];o.points[16,:2]=[.57,.08]
        self.assertTrue(evaluate_pose(o,BED)['ready'])

    def test_arms_torso_direction_bending_and_unknown(self):
        variations = [
            {15:(.2,.3)}, {15:(.51,.46),16:(.49,.46)},
            {25:(.63,.67)}, {0:(.5,.7)},
        ]
        for change in variations:
            o=patient()
            for i,xy in change.items(): o.points[i,:2]=xy
            result=evaluate_pose(o,BED)
            self.assertFalse(result['ready']);self.assertTrue(result['pose_boxes'])
        o=patient();o.points[:,0]+=.16
        self.assertFalse(evaluate_pose(o,BED)['ready'])
        o=patient();o.points[[11,12],2]=-.6;o.points[[11,12],1]+=.10
        self.assertFalse(evaluate_pose(o,BED)['ready'])
        o=patient();o.points[15,3]=.1
        self.assertFalse(evaluate_pose(o,BED)['ready'])
        self.assertFalse(evaluate_pose(None,BED)['ready'])

    def test_bed_validation(self):
        for corners in [[],[[0,0]]*4,[[0,0],[1,1],[1,0],[0,1]]]:
            with self.assertRaises(ValueError): BedReference(corners)
        np.testing.assert_allclose(BED.project(BED.corners),[[0,0],[1,0],[1,1],[0,1]],atol=1e-9)

    def test_small_body_rotation_is_allowed_but_large_rotation_is_not(self):
        for angle,expected in [(12,True),(25,True),(40,False)]:
            o=patient();r=np.deg2rad(angle)
            rotation=np.array([[np.cos(r),-np.sin(r)],[np.sin(r),np.cos(r)]])
            o.points[:,:2]=(o.points[:,:2]-.5)@rotation.T+.5
            self.assertEqual(evaluate_pose(o,BED)['ready'],expected,angle)


class CombinedTests(unittest.TestCase):
    def test_only_all_ready_is_ready(self):
        for sr in [False,True]:
            for pr in [False,True]:
                result=combine_checks({'ready':sr,'anomaly_boxes':[],'message':'Scene changed'},
                                      {'ready':pr,'pose_boxes':[] if pr else [{'reason':'Arm'}]})
                self.assertEqual(result['ready'],sr and pr)
                self.assertEqual(result['status'],'ready' if sr and pr else 'not ready')

    def test_mask_excludes_patient_but_not_objects_elsewhere_on_bed(self):
        base=scene();cal=BackgroundCalibration.create([base]*5,CAMERA,[])
        current=base.copy();ImageDraw.Draw(current).rectangle((220,120,300,200),fill='navy')
        mask=np.zeros((360,640),bool);mask[115:205,215:305]=True
        small=Image.fromarray(mask).resize(cal.mask.shape[::-1],Image.Resampling.NEAREST)
        self.assertTrue(cal.predict(current,np.asarray(small))['ready'])
        ImageDraw.Draw(current).rectangle((370,125,430,190),fill='red')
        result=cal.predict(current,np.asarray(small))
        self.assertFalse(result['ready']);self.assertTrue(result['anomaly_boxes'])
        # Occluding most of the image must not pass the scene check.
        self.assertFalse(cal.predict(base,np.ones_like(cal.mask))['ready'])

    def test_three_frame_stability_and_combined_path(self):
        import tempfile
        class Detector:
            def __init__(self): self.items=[]
            def observe(self,image,bed): return self.items.pop(0)
            def close(self): pass
        det=Detector()
        with tempfile.TemporaryDirectory() as temp:
            server=DemoServer(('127.0.0.1',0),temp,detector=det)
            try:
                base=scene();server.active=BackgroundCalibration.create([base]*5,CAMERA,[]);server.bed=BED
                def obs():
                    o=patient();o.mask[120:200,220:300]=1;return o
                det.items=[obs(),obs(),obs()]
                self.assertTrue(server.inspect([base]*3)['ready'])
                det.items=[obs(),obs(),obs()]
                result=server.inspect([with_object(base)]*3)
                self.assertFalse(result['ready']);self.assertTrue(result['pose_ready']);self.assertTrue(result['anomaly_boxes'])
                moved=obs();moved.points[0,0]+=.16
                det.items=[obs(),moved,obs()]
                result=server.inspect([base]*3)
                self.assertFalse(result['ready']);self.assertTrue(result['pose_boxes'])
                det.items=[obs()]
                self.assertFalse(server.inspect([base])['ready'])
                det.items=[None,None,None]
                self.assertFalse(server.inspect([base]*3)['ready'])
                det.items=[None,obs(),obs()]
                self.assertTrue(server.inspect([base]*3)['ready'])
                noisy=obs();noisy.points[0,0]+=.035
                det.items=[obs(),noisy,obs()]
                self.assertTrue(server.inspect([base]*3)['ready'])
            finally: server.server_close()

    def test_minor_rotation_and_smooth_shadow_but_real_objects_block(self):
        import cv2
        base=scene();cal=BackgroundCalibration.create([base]*5,CAMERA,[])
        a=np.asarray(base).astype('float32')
        yy,xx=np.mgrid[:360,:640]
        shadow=1-.3*np.exp(-((xx-320)**2+(yy-180)**2)/(2*95**2))
        changed=Image.fromarray(np.clip(a*shadow[:,:,None],0,255).astype('uint8'))
        self.assertTrue(cal.predict(changed)['ready'])
        warp=cv2.getRotationMatrix2D((320,180),1.5,1)
        rotated=Image.fromarray(cv2.warpAffine(np.asarray(base),warp,(640,360),borderMode=cv2.BORDER_REFLECT))
        self.assertTrue(cal.predict(rotated)['ready'])
        for color in ['red','black','white']:
            actual=changed.copy();ImageDraw.Draw(actual).rectangle((350,135,430,200),fill=color)
            self.assertFalse(cal.predict(actual)['ready'],color)

    def test_bed_suggestion_and_long_edge_click_order(self):
        from bed_detection import suggest_bed
        # A clean elongated bright bed against a darker room.
        image=Image.new('RGB',(800,450),'#454550')
        ImageDraw.Draw(image).rectangle((110,160,690,290),fill='#d0d3d5')
        corners=suggest_bed(image)
        self.assertIsNotNone(corners)
        mapped=BedReference(corners,image.size)
        center=np.mean(mapped.corners,axis=0)
        self.assertLess(np.linalg.norm(center-[.5,.5]),.05)
        bed=BedReference([[.1,.3],[.9,.3],[.9,.7],[.1,.7]],image.size)
        np.testing.assert_allclose(bed.corners,[[.1,.3],[.1,.7],[.9,.7],[.9,.3]])
        # Uniform empty input does not receive a fabricated bed proposal.
        self.assertIsNone(suggest_bed(Image.new('RGB',(800,450),'gray')))


if __name__=='__main__': unittest.main()
