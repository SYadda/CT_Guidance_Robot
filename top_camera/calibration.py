"""Session-based empty-room background calibration; no trained classifier."""
from dataclasses import dataclass
import io
import numpy as np
from PIL import Image, ImageFilter, ImageOps


def read_image(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError('Images must not exceed 16 megapixels.')
        return ImageOps.exif_transpose(image).convert('RGB').copy()


def jpeg(image):
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=90)
    return out.getvalue()


def pixels(image):
    copy = image.copy()
    copy.thumbnail((480, 360), Image.Resampling.BILINEAR)
    return np.asarray(copy, dtype=np.float32) / 255


def roi_mask(shape, regions):
    if not isinstance(regions, list) or len(regions) > 8:
        raise ValueError('Use at most eight ignored areas.')
    height, width = shape[:2]
    mask = np.ones((height, width), dtype=bool)
    mask[:3] = mask[-3:] = False
    mask[:, :3] = mask[:, -3:] = False
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError('Invalid ignored area.')
        try:
            x, y, w, h = [float(region[key]) for key in ('x','y','width','height')]
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid ignored area.') from None
        if not all(np.isfinite(v) for v in (x,y,w,h)) or min(x,y) < 0 or min(w,h) <= 0 or x+w > 1.00001 or y+h > 1.00001:
            raise ValueError('Ignored areas must stay within the image.')
        mask[int(y*height):int(np.ceil((y+h)*height)), int(x*width):int(np.ceil((x+w)*width))] = False
    if mask.mean() < .65:
        raise ValueError('Ignored areas must leave at least 65% of the image visible.')
    return mask


def quality_ok(a):
    return .035 < float(a.mean()) < .96 and float(a.std()) > .025


def photometric_difference(a, reference, mask):
    """Bounded global exposure correction and low-frequency lighting suppression."""
    aq = np.quantile(a[mask], [.1,.5,.9], axis=0)
    rq = np.quantile(reference[mask], [.1,.5,.9], axis=0)
    gain = np.clip((rq[2]-rq[0])/np.maximum(aq[2]-aq[0], .05), .65, 1.55)
    offset = np.clip(rq[1]-aq[1]*gain, -.18, .18)
    corrected = np.clip(a*gain+offset, 0, 1)
    residual = corrected-reference
    # Weighted smoothing excludes ignored regions from the lighting estimate.
    weight = np.asarray(Image.fromarray((mask*255).astype('uint8')).filter(ImageFilter.GaussianBlur(14)), dtype=np.float32)/255
    smooth = []
    for channel in range(3):
        encoded = ((np.clip(residual[...,channel],-.5,.5)+.5)*mask*255).astype('uint8')
        blurred = np.asarray(Image.fromarray(encoded).filter(ImageFilter.GaussianBlur(14)), dtype=np.float32)/255
        smooth.append(blurred/np.maximum(weight,.01)-.5)
    residual -= .65*np.stack(smooth, axis=2)
    diff = np.mean(np.abs(residual), axis=2)
    diff[~mask] = 0
    return diff


def tolerant_difference(a, reference, mask):
    """Suppress smooth, colour-preserving illumination, retain new edges/colour.

    This deliberately trades small-object sensitivity for a usable demonstration
    under moving shadows. Dark, low-contrast objects can still be missed.
    """
    import cv2
    aq=np.quantile(a[mask],[.1,.5,.9],axis=0)
    rq=np.quantile(reference[mask],[.1,.5,.9],axis=0)
    gain=np.clip((rq[2]-rq[0])/np.maximum(aq[2]-aq[0],.05),.5,2)
    offset=np.clip(rq[1]-aq[1]*gain,-.25,.25)
    corrected=np.clip(a*gain+offset,0,1).astype('float32')
    residual=corrected-reference
    weights=cv2.GaussianBlur(mask.astype('float32'),(0,0),7)
    smooth=cv2.GaussianBlur(residual*mask[:,:,None],(0,0),7)/np.maximum(weights[:,:,None],.02)
    diff=np.mean(np.abs(residual-.95*smooth),axis=2)
    ratio=(corrected.mean(2)+.03)/(reference.mean(2)+.03)
    ac=(corrected+.03)/(corrected.mean(2,keepdims=True)+.09)
    rc=(reference+.03)/(reference.mean(2,keepdims=True)+.09)
    neutral=np.mean(np.abs(ac-rc),axis=2)<.10
    def edges(rgb):
        gray=cv2.GaussianBlur(rgb.mean(2),(3,3),0)
        return cv2.magnitude(cv2.Sobel(gray,cv2.CV_32F,1,0),cv2.Sobel(gray,cv2.CV_32F,0,1))
    existing=cv2.dilate((edges(reference)>.18).astype('uint8'),np.ones((9,9),np.uint8))>0
    added=(edges(corrected)>.30)&~existing
    support=cv2.dilate(added.astype('uint8'),np.ones((5,5),np.uint8))>0
    lighting=neutral&(ratio>.28)&(ratio<2.8)&~support
    diff[lighting]*=.15
    diff[~mask]=0
    return diff


def align_background(a, reference, threshold, mask):
    """Warp reference to current coordinates for <=2.5 degree camera roll."""
    import cv2
    identity=np.eye(2,3,dtype='float32')
    try:
        score,warp=cv2.findTransformECC(reference.mean(2),a.mean(2),identity,cv2.MOTION_EUCLIDEAN,
            (cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.0001),mask.astype('uint8')*255,5)
    except cv2.error:
        return reference,threshold,mask
    angle=abs(np.rad2deg(np.arctan2(warp[1,0],warp[0,0])))
    h,w=mask.shape
    # A centered rotation includes translation in its matrix. Bound the actual
    # center displacement rather than rejecting a valid 2-degree rotation.
    center=np.array([w/2,h/2,1.],dtype='float32')
    displacement=np.linalg.norm(warp@center-center[:2])
    if score<.80 or angle>2.5 or displacement>min(w,h)*.025:
        return reference,threshold,mask
    ref=cv2.warpAffine(reference,warp,(w,h),flags=cv2.INTER_LINEAR)
    th=cv2.warpAffine(threshold,warp,(w,h),flags=cv2.INTER_LINEAR,borderValue=.1)
    # Keep all ignored/current-patient pixels out; exclude warped image borders.
    valid=cv2.warpAffine(np.ones((h,w),np.uint8),warp,(w,h),flags=cv2.INTER_NEAREST)>0
    return ref,th,mask&valid


def regions_from_mask(mask, min_area):
    height, width = mask.shape
    visited = np.zeros_like(mask)
    boxes = []
    for y,x in zip(*np.nonzero(mask)):
        if visited[y,x]:
            continue
        pending = [(int(y),int(x))]
        visited[y,x] = True
        count, x1, x2, y1, y2 = 0,int(x),int(x),int(y),int(y)
        while pending:
            cy,cx = pending.pop()
            count += 1
            x1,x2 = min(x1,cx),max(x2,cx)
            y1,y2 = min(y1,cy),max(y2,cy)
            for ny,nx in ((cy-1,cx),(cy+1,cx),(cy,cx-1),(cy,cx+1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny,nx] and not visited[ny,nx]:
                    visited[ny,nx] = True
                    pending.append((ny,nx))
        if count < min_area or x2-x1 < 4 or y2-y1 < 4:
            continue
        x1,y1 = max(0,x1-3),max(0,y1-3)
        x2,y2 = min(width,x2+4),min(height,y2+4)
        boxes.append({'x':round(x1/width,6),'y':round(y1/height,6),
                      'width':round((x2-x1)/width,6),'height':round((y2-y1)/height,6),'area':count})
    return sorted(boxes,key=lambda box:box['area'],reverse=True)


@dataclass
class BackgroundCalibration:
    reference: np.ndarray
    threshold: np.ndarray
    mask: np.ndarray
    camera: dict
    image_size: tuple
    ignored_regions: list

    @classmethod
    def create(cls, images, camera, ignored_regions):
        if len(images) != 5 or any(im.size != images[0].size for im in images):
            raise ValueError('Calibration requires five images of the same size.')
        samples = np.stack([pixels(image) for image in images])
        if not all(quality_ok(sample) for sample in samples):
            raise ValueError('Calibration images are too dark, too bright or lack useful detail.')
        reference = np.median(samples, axis=0)
        mask = roi_mask(reference.shape, ignored_regions)
        differences = np.stack([photometric_difference(sample,reference,mask) for sample in samples])
        # Refuse a moving/unstable room rather than learning its movement as normal.
        if np.mean(np.mean(differences[:,mask] > .08, axis=1)) > .018:
            raise ValueError('The room changed during calibration. Clear the room, keep the camera still and retake.')
        noise = np.quantile(differences,.95,axis=0)
        threshold = np.clip(noise*2.5+.035, .065, .12)
        return cls(reference,threshold,mask,camera,images[0].size,ignored_regions)

    def predict(self, image, excluded_mask=None):
        if image.size != self.image_size:
            raise ValueError('Capture size changed. Calibrate again.')
        a = pixels(image)
        if not quality_ok(a):
            return {'ready':False,'status':'not ready','anomaly_boxes':[],
                    'message':'The photo is too dark, too bright or lacks useful detail. Please capture it again.'}
        mask = self.mask.copy()
        if excluded_mask is not None:
            excluded = np.asarray(excluded_mask, dtype=bool)
            if excluded.shape != mask.shape:
                raise ValueError('Patient mask dimensions do not match the scene.')
            mask &= ~excluded
        if mask.sum() < self.mask.sum()*.35:
            return {'ready':False,'status':'not ready','anomaly_boxes':[],
                    'message':'Too little background is visible for the scene check.'}
        reference,threshold,mask=align_background(a,self.reference,self.threshold,mask)
        diff = tolerant_difference(a,reference,mask)
        changes = Image.fromarray(((diff > np.maximum(threshold,.085))*255).astype('uint8'))
        changes = changes.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
        changes = changes.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
        binary = (np.asarray(changes)>0) & mask
        boxes = regions_from_mask(binary,max(120,int(mask.sum()*.001)))
        fraction = float(binary[mask].mean())
        ready = not boxes and fraction < .012
        return {'ready':ready,'status':'ready' if ready else 'not ready',
                'anomaly_boxes':boxes[:20] if not ready else [],'changed_fraction':round(fraction,5),
                'message': 'The scene matches the confirmed empty-room baseline.' if ready else
                ('Red boxes highlight visual differences from the empty-room baseline.' if boxes else
                 'Differences are spread across the scene. Check the room, lighting and camera position.')}
