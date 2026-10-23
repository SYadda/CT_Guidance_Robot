"""Local pose geometry and patient masking for the fixed-camera demonstration.

No comparison with a person's silhouette. Rules use bed coordinates, joint
angles, and distances divided by this patient's shoulder/torso dimensions.
"""
from dataclasses import dataclass
from pathlib import Path
import threading
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

MODEL = Path(__file__).resolve().parent / 'models' / 'pose_landmarker_full.task'
CORE = [0, 11, 12, 23, 24, 25, 26, 27, 28]


def box_for(points, padding=.025):
    a = np.asarray(points, dtype=float)[:, :2]
    lo = np.clip(a.min(axis=0)-padding, 0, 1)
    hi = np.clip(a.max(axis=0)+padding, 0, 1)
    hi = np.maximum(hi, np.minimum(lo+.02, 1))
    return dict(x=float(lo[0]), y=float(lo[1]), width=float(hi[0]-lo[0]), height=float(hi[1]-lo[1]))


@dataclass
class BedReference:
    # Four corners in order: head-left, head-right, foot-right, foot-left.
    corners: list
    image_size: tuple = (1, 1)

    def __post_init__(self):
        a = np.asarray(self.corners, dtype=float)
        if a.shape != (4, 2) or not np.isfinite(a).all() or (a < 0).any() or (a > 1).any():
            raise ValueError('Mark four bed corners inside the photo.')
        edges = np.roll(a, -1, axis=0)-a
        crosses = edges[:, 0]*np.roll(edges, -1, axis=0)[:, 1]-edges[:, 1]*np.roll(edges, -1, axis=0)[:, 0]
        area = abs(np.dot(a[:, 0], np.roll(a[:, 1], 1))-np.dot(a[:, 1], np.roll(a[:, 0], 1)))/2
        if not ((crosses > 0).all() or (crosses < 0).all()) or area < .015:
            raise ValueError('Bed corners must form a non-crossing quadrilateral of useful size.')
        head = a[:2].mean(axis=0); foot = a[2:].mean(axis=0)
        if np.linalg.norm(foot-head) < .15:
            raise ValueError('The head and foot ends are too close.')
        # Users may start at either neighbour of the first head corner. The
        # two short edges are the ends; never interpret a long rail as head.
        lengths = np.linalg.norm(edges*np.asarray(self.image_size), axis=1)
        if lengths[[0,2]].mean() > lengths[[1,3]].mean()*1.25:
            a = a[[0,3,2,1]]
        self.corners = a.tolist()
        # Projective coordinates: bed width u=0..1, head-to-foot v=0..1.
        dest = [(0, 0), (1, 0), (1, 1), (0, 1)]
        rows, values = [], []
        for (x, y), (u, v) in zip(a, dest):
            rows.extend([[x,y,1,0,0,0,-u*x,-u*y], [0,0,0,x,y,1,-v*x,-v*y]])
            values.extend([u,v])
        self.matrix = np.append(np.linalg.solve(rows, values), 1).reshape(3,3)

    def project(self, points):
        p = np.asarray(points)[:, :2]
        h = np.column_stack([p, np.ones(len(p))]) @ self.matrix.T
        if (np.abs(h[:,2]) < 1e-6).any():
            raise ValueError('Position cannot be mapped to the bed.')
        return h[:, :2]/h[:, 2:3]

    def rotation(self, size):
        # Put the head end at the top for the model; preserve original UI axes.
        a = np.asarray(self.corners)*size
        vector = a[:2].mean(axis=0)-a[2:].mean(axis=0)
        directions = [vector, [vector[1],-vector[0]], -vector, [-vector[1],vector[0]]]
        return int(np.argmin([v[1] for v in directions]))


@dataclass
class Observation:
    points: np.ndarray
    mask: np.ndarray
    size: tuple
    extra_people: bool = False


class PoseDetector:
    def __init__(self):
        self.detector = None
        self.lock = threading.RLock()

    def observe(self, image, bed):
        import mediapipe as mp
        with self.lock:
            if self.detector is None:
                if not MODEL.is_file():
                    raise RuntimeError('Pose model is missing. Run setup_demo.ps1 first.')
                options = mp.tasks.vision.PoseLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
                    num_poses=2, output_segmentation_masks=True,
                    min_pose_detection_confidence=.3, min_pose_presence_confidence=.5)
                self.detector = mp.tasks.vision.PoseLandmarker.create_from_options(options)
            small = image.copy(); small.thumbnail((1280,1280))
            rotation = bed.rotation(small.size)
            # The second orientation permits recognizing a reversed patient.
            # Retry exposure before reversing the person: a bright mattress
            # can suppress detection in the correct orientation.
            for k,gain in ((rotation,1),(rotation,.75),(rotation,1.35),((rotation+2)%4,1)):
                adjusted = small if gain == 1 else ImageEnhance.Brightness(small).enhance(gain)
                a = np.ascontiguousarray(np.rot90(np.asarray(adjusted), k))
                result = self.detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=a))
                if not result.pose_landmarks:
                    continue
                people = []
                for i, landmarks in enumerate(result.pose_landmarks):
                    p = np.array([[l.x,l.y,l.z,l.visibility,l.presence] for l in landmarks],dtype=float)
                    # Inverse normalized rotation (numpy rotates anticlockwise).
                    x,y = p[:,0].copy(),p[:,1].copy()
                    if k == 1: p[:,0],p[:,1] = 1-y,x
                    elif k == 2: p[:,0],p[:,1] = 1-x,1-y
                    elif k == 3: p[:,0],p[:,1] = y,1-x
                    # Depth is normalized to the model-input width.
                    p[:,2] *= a.shape[1]/small.width
                    mapped = bed.project(p)
                    center = mapped[[23,24]].mean(axis=0)
                    score = float(p[CORE,3].mean())-min(float(np.linalg.norm(center-[.5,.5]))*.2, .5)
                    people.append((score, i, p))
                people.sort(key=lambda item:item[0],reverse=True)
                _, i, p = people[0]
                if not result.segmentation_masks:
                    return None
                mask = result.segmentation_masks[i].numpy_view().squeeze().copy()
                mask = np.rot90(mask, -k)
                # Ignore duplicate detections of the same patient, but block a
                # spatially separate, confident second person.
                center = p[[11,12,23,24],:2].mean(axis=0)
                extent = max(np.ptp(p[CORE,:2],axis=0))
                extra = any(np.linalg.norm(other[[11,12,23,24],:2].mean(axis=0)-center) > extent*.45
                            and other[CORE,3].mean() > .65 for _,_,other in people[1:])
                return Observation(p, mask, image.size, extra)
        return None

    def close(self):
        with self.lock:
            if self.detector is not None:
                self.detector.close(); self.detector = None


def evaluate_pose(observation, bed):
    issues = []
    def issue(code, ids=None, points=None):
        region = points if points is not None else (observation.points[ids] if observation is not None and ids else bed.corners)
        issues.append({'reason':code, **box_for(region)})
    if observation is None:
        issue('Patient could not be identified')
        return {'ready':False, 'pose_boxes':issues, 'arm_mode':None}
    p = observation.points
    if p.shape != (33,5) or not np.isfinite(p).all():
        issue('Pose could not be evaluated', points=bed.corners)
        return {'ready':False, 'pose_boxes':issues, 'arm_mode':None}
    uv = bed.project(p)
    xy = p[:,:2]*observation.size
    shoulder = (xy[11]+xy[12])/2
    hip = (xy[23]+xy[24])/2
    width = np.linalg.norm(xy[11]-xy[12])
    torso = np.linalg.norm(hip-shoulder)
    if observation.extra_people:
        issue('More than one person', points=bed.corners)
    for name, ids in [('Head',[0]),('Torso',[11,12,23,24]),('Legs',[25,26,27,28]),('Left arm',[13,15]),('Right arm',[14,16])]:
        if any(p[i,3] < .25 or p[i,4] < .5 or not (0 <= p[i,0] <= 1 and 0 <= p[i,1] <= 1) for i in ids):
            issue(name+' is not reliably visible', ids)
    if width < 10 or torso < 10:
        issue('Body geometry is uncertain',[11,12,23,24])
        return {'ready':False,'pose_boxes':issues,'arm_mode':None}
    axis = (hip-shoulder)/torso
    side = np.array([-axis[1],axis[0]])
    # Relative to patient's torso, not fixed image pixels or a reference body.
    body_uv = uv[[11,12,23,24]].mean(axis=0)
    if abs(body_uv[0]-.5) > .28:
        issue('Body is off the bed center',[11,12,23,24])
    delta = uv[[23,24]].mean(axis=0)-uv[[11,12]].mean(axis=0)
    if delta[1] <= .03 or uv[0,1] > uv[[23,24],1].mean():
        issue('Head-to-foot direction is incorrect',[0,11,12,23,24])
    # Compare the body direction in real image pixel geometry with the bed axis.
    corners = np.asarray(bed.corners)*observation.size
    bed_axis = corners[2:].mean(axis=0)-corners[:2].mean(axis=0)
    bed_axis /= np.linalg.norm(bed_axis)
    if np.dot(axis,bed_axis) < np.cos(np.deg2rad(28)):
        issue('Body is diagonal or rotated',[11,12,23,24])
    # Depth is a model estimate, used only as a conservative sitting/leaning cue.
    dz = (p[[11,12],2].mean()-p[[23,24],2].mean())*observation.size[0]
    # Depth alone is unstable in an overhead view. Require foreshortening as
    # well, so a relaxed, flat patient is not rejected by estimated depth.
    leg_length = np.linalg.norm(xy[[27,28]].mean(axis=0)-hip)
    foreshortened = torso/width < 1.12 or torso/max(leg_length,1) < .48
    if torso/np.hypot(torso,dz) < .58 and foreshortened:
        issue('Upper body is raised or not lying flat',[0,11,12,23,24])
    if np.linalg.norm(xy[0]-shoulder) < width*.18:
        issue('Head / upper-body posture is uncertain',[0,11,12])

    arm_modes = []
    for name,s,e,w in [('Left',11,13,15),('Right',12,14,16)]:
        elbow = xy[e]-xy[s]; wrist = xy[w]-xy[s]
        e_long,w_long = np.dot(elbow,axis)/torso,np.dot(wrist,axis)/torso
        e_side,w_side = abs(np.dot(elbow,side))/width,abs(np.dot(wrist,side))/width
        # Sides: hand near the same-side hip, no crossing across the chest.
        wrist_center = np.dot(xy[w]-shoulder,side)/width
        shoulder_side = np.dot(xy[s]-shoulder,side)
        down = (e_long > .08 and .35 < w_long < 1.95 and e_side < .62 and w_side < .68
                and wrist_center*shoulder_side > 0 and abs(wrist_center) > .24
                and np.linalg.norm(xy[w]-xy[23 if s==11 else 24])/torso < .82)
        # Overhead: both elbow and wrist towards the head, not a sideways V.
        up = (e_long < -.14 and w_long < -.48 and e_side < 1.0 and w_side < 1.0
              and -np.dot(elbow,axis)/max(np.linalg.norm(elbow),1) > .45)
        arm_modes.append('sides' if down else 'overhead' if up else None)
        if not (down or up): issue(name+' arm is outside the allowed position',[s,e,w])
    if all(arm_modes) and arm_modes[0] != arm_modes[1]:
        issue('Both arms must use the same position',[11,12,13,14,15,16])
    if arm_modes == ['sides','sides'] and abs(np.dot(xy[15]-xy[16],side))/width < .65:
        issue('Hands must remain beside the torso',[13,14,15,16])
    # Legs should run along the body; allow natural spacing and support pads.
    for name,h,k,a in [('Left',23,25,27),('Right',24,26,28)]:
        thigh,shin = xy[k]-xy[h],xy[a]-xy[k]
        cosine = np.dot(thigh,shin)/max(np.linalg.norm(thigh)*np.linalg.norm(shin),1)
        if cosine < np.cos(np.deg2rad(45)) or np.dot(xy[a]-xy[h],axis) < torso*.50:
            issue(name+' leg is bent or raised',[h,k,a])
        if abs(np.dot(xy[a]-xy[h],side))/width > .85:
            issue(name+' leg is spread away from the body',[h,k,a])
    if np.dot(xy[27]-xy[28],xy[23]-xy[24]) < -width*width*.025:
        issue('Legs are crossed',[23,24,25,26,27,28])
    for name,ids in [('Head',[0]),('Torso',[11,12,23,24]),('Legs',[25,26,27,28]),('Arms',[13,14,15,16])]:
        # Small end margins permit headrests; side margins permit soft tissues.
        q=uv[ids]
        end_margin = -.38 if name == 'Arms' and arm_modes == ['overhead','overhead'] else -.20
        if (q[:,0] < -.25).any() or (q[:,0] > 1.25).any() or (q[:,1] < end_margin).any() or (q[:,1] > 1.12).any():
            issue(name+' extend outside the bed',[*ids])
    return {'ready':not issues,'pose_boxes':issues,'arm_mode':arm_modes[0] if all(arm_modes) else None}


def patient_exclusion(observation, size):
    # Tight segmentation, not the whole bed or a rectangular patient envelope.
    mask = Image.fromarray((observation.mask > .35).astype('uint8')*255)
    mask = mask.resize(size, Image.Resampling.NEAREST).filter(ImageFilter.MaxFilter(11))
    # Shoes are often omitted from the model's mask in a bright overhead view.
    # Extend only the narrow, joint-defined foot corridors, not the whole bed.
    from PIL import ImageDraw
    draw=ImageDraw.Draw(mask)
    xy=observation.points[:,:2]*size
    shoulder_width=np.linalg.norm((observation.points[11,:2]-observation.points[12,:2])*observation.size)
    radius=max(3,shoulder_width*.24*size[0]/observation.size[0])
    for knee,ankle in [(25,27),(26,28)]:
        if observation.points[[knee,ankle],3].min()<.5:continue
        end=xy[ankle]+.65*(xy[ankle]-xy[knee])
        draw.line([tuple(xy[ankle]),tuple(end)],fill=255,width=max(3,int(radius*2)))
        for x,y in (xy[ankle],end):draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
    return np.asarray(mask)>0


def combine_checks(scene, pose):
    ready = bool(scene['ready'] and pose['ready'])
    reasons = list(dict.fromkeys(b['reason'] for b in pose['pose_boxes']))
    return {**scene, 'ready':ready, 'status':'ready' if ready else 'not ready',
            'scene_ready':bool(scene['ready']), 'pose_ready':bool(pose['ready']),
            'pose_boxes':pose['pose_boxes'], 'arm_mode':pose.get('arm_mode'),
            'message': ' '.join(([scene['message']] if not scene['ready'] else [])+reasons)}
