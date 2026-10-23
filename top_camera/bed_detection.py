"""Propose a bed quadrilateral from an EMPTY frame; always require review."""
import numpy as np
from PIL import Image
from positioning import BedReference


def suggest_bed(image):
    import cv2
    small=image.copy();small.thumbnail((800,600))
    rgb=np.asarray(small);gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    h,w=gray.shape;total=h*w
    smooth=cv2.GaussianBlur(gray,(5,5),0)
    sources=[cv2.Canny(smooth,35,100)]
    otsu,_=cv2.threshold(smooth,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    for threshold in sorted(set([int(otsu),65,90,115,145,175,205])):
        sources.append(cv2.threshold(smooth,threshold,255,cv2.THRESH_BINARY)[1])
    candidates=[]
    for source in sources:
        closed=cv2.morphologyEx(source,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        contours,_=cv2.findContours(closed,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area=cv2.contourArea(contour)
            if not .055*total < area < .45*total: continue
            rect=cv2.minAreaRect(contour);rw,rh=rect[1]
            if min(rw,rh)<12: continue
            ratio=max(rw,rh)/min(rw,rh);fill=area/(rw*rh)
            if not 2.0 < ratio < 7.0 or fill < .70: continue
            corners=cv2.boxPoints(rect)
            if (corners[:,0]<2).any() or (corners[:,0]>w-2).any() or (corners[:,1]<2).any() or (corners[:,1]>h-2).any():continue
            polygon=np.zeros((h,w),np.uint8);cv2.fillConvexPoly(polygon,corners.astype('int32'),1)
            mean=float(gray[polygon>0].mean())
            if mean<65:continue
            # Prefer a large bright elongated surface over small floor tiles.
            score=area*fill*(.6+mean/255)
            candidates.append((score,corners))
    if not candidates:return None
    _,corners=max(candidates,key=lambda entry:entry[0])
    # A floor reflection can join the bright bed component. Refine the two
    # long rails using edge support across most of its length, rather than
    # allowing a small glare patch to expand the whole suggested rectangle.
    vectors=np.roll(corners,-1,axis=0)-corners
    lengths=np.linalg.norm(vectors,axis=1)
    long=float(lengths.max());short=float(lengths.min())
    axis=vectors[int(np.argmax(lengths))]/long
    side=np.array([-axis[1],axis[0]])
    center=corners.mean(axis=0)
    gx=cv2.Sobel(smooth,cv2.CV_32F,1,0)
    gy=cv2.Sobel(smooth,cv2.CV_32F,0,1)
    edge=np.abs(gx*side[0]+gy*side[1])
    along=np.linspace(-long*.4,long*.4,160)
    across=np.linspace(-short*.75,short*.75,max(20,int(short*1.5)))
    grid=center+along[None,:,None]*axis+across[:,None,None]*side
    profile=cv2.remap(edge,grid[:,:,0].astype('float32'),grid[:,:,1].astype('float32'),cv2.INTER_LINEAR).mean(axis=1)
    pairs=[(float((profile[i]+profile[j])*np.sqrt((across[j]-across[i])/short)),i,j)
           for i in range(len(across)) if across[i]<-short*.20
           for j in range(len(across)) if across[j]>short*.20 and short*.65<across[j]-across[i]<short*1.12]
    if pairs:
        _,i,j=max(pairs)
        corners=np.array([center-axis*long/2+side*across[i],center+axis*long/2+side*across[i],
                          center+axis*long/2+side*across[j],center-axis*long/2+side*across[j]])
    # Walk around the perimeter; choose the upper/left short end as default.
    center=corners.mean(axis=0)
    corners=corners[np.argsort(np.arctan2(corners[:,1]-center[1],corners[:,0]-center[0]))]
    lengths=np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)
    short_indices=[i for i in range(4) if lengths[i] < lengths.max()*.65]
    if len(short_indices)!=2:return None
    horizontal=np.ptp(corners[:,0])>np.ptp(corners[:,1])
    head=min(short_indices,key=lambda i:((corners[i]+corners[(i+1)%4])/2)[0 if horizontal else 1])
    corners=np.roll(corners,-head,axis=0)/[w,h]
    return BedReference(corners.tolist(),small.size).corners
