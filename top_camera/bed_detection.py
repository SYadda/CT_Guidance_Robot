"""Automatically propose a bed outline; confirm the outline and head end."""
import numpy as np
from PIL import Image
from positioning import BedReference


def rail_candidates(gray, smooth):
    """Find paired bed rails when daylight glare joins bed and floor contours.

    Keep the interval whose surface is brighter than BOTH-side surroundings on
    average. This distinguishes the white table from a dark floor mat without
    hard-coding its position or the direction in which the camera is mounted.
    """
    import cv2
    h,w=gray.shape
    edges=cv2.Canny(smooth,25,75)
    found=cv2.HoughLinesP(edges,1,np.pi/720,60,
                          minLineLength=max(50,int(max(w,h)*.20)),maxLineGap=35)
    if found is None:return []
    lines=[]
    for raw in np.asarray(found).reshape(-1,4):
        a,b=raw.reshape(2,2).astype(float)
        vector=b-a;length=np.linalg.norm(vector)
        if length<1:continue
        axis=vector/length
        if axis[0]<0 or (abs(axis[0])<1e-6 and axis[1]<0):axis=-axis
        lines.append((length,a,b,axis))
    lines=sorted(lines,key=lambda item:item[0],reverse=True)[:45]
    candidates=[]
    for i,(_,a,b,axis1) in enumerate(lines):
        for _,c,d,axis2 in lines[i+1:]:
            if np.dot(axis1,axis2)<np.cos(np.deg2rad(4)):continue
            axis=axis1+axis2;axis/=np.linalg.norm(axis)
            side=np.array([-axis[1],axis[0]])
            first=np.sort(np.array([a,b])@axis);second=np.sort(np.array([c,d])@axis)
            overlap=min(first[1],second[1])-max(first[0],second[0])
            # Each rail may be visible at a different end because of glare.
            # Allow a small gap instead of requiring long common support.
            if overlap < -min(np.diff(first)[0],np.diff(second)[0])*.25:continue
            offset1=np.mean(np.array([a,b])@side);offset2=np.mean(np.array([c,d])@side)
            width=abs(offset2-offset1)
            start=min(first[0],second[0]);end=max(first[1],second[1])
            if width<15 or not 1.5<(end-start)/width<9:continue
            center=(offset1+offset2)/2
            along=np.linspace(start,end,256)
            def sample(across):
                grid=along[None,:,None]*axis+(center+np.asarray(across)[:,None,None]*width)*side
                return cv2.remap(gray,grid[:,:,0].astype('float32'),grid[:,:,1].astype('float32'),
                                 cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE).astype(float)
            inside=np.median(sample(np.linspace(-.35,.35,9)),axis=0)
            outside=(np.median(sample([-.80,-.65,-.55]),axis=0)+
                     np.median(sample([.55,.65,.80]),axis=0))/2
            contrast=inside-outside
            positive=(np.convolve(contrast,np.ones(7)/7,mode='same')>15).astype('uint8')[None,:]
            positive=cv2.morphologyEx(positive,cv2.MORPH_CLOSE,np.ones((1,9),np.uint8))
            positive=cv2.morphologyEx(positive,cv2.MORPH_OPEN,np.ones((1,7),np.uint8))[0]>0
            transitions=np.diff(np.r_[False,positive,False].astype(int))
            runs=list(zip(np.flatnonzero(transitions==1),np.flatnonzero(transitions==-1)))
            if not runs:continue
            lo,hi=max(runs,key=lambda run:run[1]-run[0])
            length=(hi-lo)/255*(end-start)
            if not 1.8<length/width<7.5 or length<max(w,h)*.28:continue
            # Reject isolated reflections: most of the proposed surface needs
            # positive contrast, rather than one small, very bright patch.
            if np.mean(contrast[lo:hi]>10)<.7:continue
            left=along[lo];right=along[min(hi,255)]
            corners=np.array([axis*left+side*(center-width/2),axis*right+side*(center-width/2),
                              axis*right+side*(center+width/2),axis*left+side*(center+width/2)])
            if (corners<2).any() or (corners[:,0]>w-3).any() or (corners[:,1]>h-3).any():continue
            aspect_prior=np.exp(-np.log((length/width)/3.8)**2/(2*.45**2))
            score=length*width*(.6+np.median(contrast[lo:hi])/128)*aspect_prior
            candidates.append((score,corners))
    return candidates


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
        sources.append(cv2.threshold(smooth,threshold,255,cv2.THRESH_BINARY_INV)[1])
    candidates=rail_candidates(gray,smooth)
    # A second edge scale retains long rails in brighter, partly clipped frames.
    candidates+=rail_candidates(gray,cv2.GaussianBlur(gray,(3,3),0))
    for source in sources:
        closed=cv2.morphologyEx(source,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        contours,_=cv2.findContours(closed,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area=cv2.contourArea(contour)
            if not .04*total < area < .70*total: continue
            rect=cv2.minAreaRect(contour);rw,rh=rect[1]
            if min(rw,rh)<12: continue
            ratio=max(rw,rh)/min(rw,rh);fill=area/(rw*rh)
            if not 1.5 < ratio < 8.0 or fill < .65: continue
            corners=cv2.boxPoints(rect)
            if (corners[:,0]<2).any() or (corners[:,0]>w-2).any() or (corners[:,1]<2).any() or (corners[:,1]>h-2).any():continue
            polygon=np.zeros((h,w),np.uint8);cv2.fillConvexPoly(polygon,corners.astype('int32'),1)
            mean=float(gray[polygon>0].mean())
            if mean<20:continue
            # Support darker mattresses as well as bright ones. A useful bed
            # candidate contrasts with its local surroundings, not just white.
            ring=cv2.dilate(polygon,np.ones((21,21),np.uint8))>0
            ring &= polygon==0
            signed_contrast=mean-float(np.median(gray[ring])) if ring.any() else 0
            contrast=abs(signed_contrast)
            score=area*fill*(.45+mean/510+contrast/255)
            # A dark mat has strong absolute contrast too. Keep dark-bed
            # fallback support, but prefer a coherent bright table surface.
            if signed_contrast<0:score*=.35
            candidates.append((score,corners))
    if not candidates:return None
    _,corners=max(candidates,key=lambda entry:entry[0])
    selected_mask=np.zeros((h,w),np.uint8)
    cv2.fillConvexPoly(selected_mask,corners.astype('int32'),1)
    selected_ring=(cv2.dilate(selected_mask,np.ones((21,21),np.uint8))>0)&(selected_mask==0)
    polarity=1
    if selected_ring.any() and np.median(gray[selected_mask>0])<np.median(gray[selected_ring]):
        polarity=-1
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
    edge=(gx*side[0]+gy*side[1])*polarity
    along=np.linspace(-long*.4,long*.4,160)
    across=np.linspace(-short*.75,short*.75,max(20,int(short*1.5)))
    grid=center+along[None,:,None]*axis+across[:,None,None]*side
    sampled=cv2.remap(edge,grid[:,:,0].astype('float32'),grid[:,:,1].astype('float32'),cv2.INTER_LINEAR)
    # Direction matters: enter the bright bed at one rail and leave it at the
    # other. A bright floor reflection beyond the rail has the opposite sign.
    enter=np.clip(sampled,0,160);leave=np.clip(-sampled,0,160)
    profile_in=enter.mean(axis=1)*(.25+.75*(enter>15).mean(axis=1))
    profile_out=leave.mean(axis=1)*(.25+.75*(leave>15).mean(axis=1))
    pairs=[(float((profile_in[i]+profile_out[j])*np.sqrt((across[j]-across[i])/short)),i,j)
           for i in range(len(across)) if across[i]<-short*.10
           for j in range(len(across)) if across[j]>short*.10 and short*.40<across[j]-across[i]<short*1.12]
    if pairs:
        _,i,j=max(pairs)
        corners=np.array([center-axis*long/2+side*across[i],center+axis*long/2+side*across[i],
                          center+axis*long/2+side*across[j],center-axis*long/2+side*across[j]])
    # Contrast against the floor can disappear near either end under daylight.
    # Recover the short ends from transverse edges across the actual table,
    # rather than ending the bed at a change in floor illumination.
    center=corners.mean(axis=0)
    short=np.linalg.norm(corners[3]-corners[0])
    edge_along=(gx*axis[0]+gy*axis[1])*polarity
    positions=[]
    for sign in [-1,1]:
        offsets=np.linspace(-short*.85,short*.85,160)
        coordinates=sign*long/2+offsets
        cross=np.linspace(-short*.45,short*.45,60)
        grid=center+coordinates[:,None,None]*axis+cross[None,:,None]*side
        # Entering the bright bed and leaving it have opposite edge signs.
        # Do not snap a short end to the bright cabinet beyond the dark gap.
        directed_edge=np.minimum(np.maximum(-sign*edge_along,0),160)
        response=cv2.remap(directed_edge,grid[:,:,0].astype('float32'),grid[:,:,1].astype('float32'),cv2.INTER_LINEAR).mean(axis=1)
        index=int(np.argmax(response))
        positions.append(float(coordinates[index]) if response[index]>12 else sign*long/2)
    if 1.5<(positions[1]-positions[0])/short<8:
        corners=np.array([center+axis*positions[0]-side*short/2,center+axis*positions[1]-side*short/2,
                          center+axis*positions[1]+side*short/2,center+axis*positions[0]+side*short/2])
        if (corners<0).any() or (corners[:,0]>w-1).any() or (corners[:,1]>h-1).any():return None
    # Walk around the perimeter; choose the upper/left short end as default.
    center=corners.mean(axis=0)
    corners=corners[np.argsort(np.arctan2(corners[:,1]-center[1],corners[:,0]-center[0]))]
    lengths=np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)
    short_indices=[i for i in range(4) if lengths[i] < lengths.max()*.75]
    if len(short_indices)!=2:return None
    horizontal=np.ptp(corners[:,0])>np.ptp(corners[:,1])
    head=min(short_indices,key=lambda i:((corners[i]+corners[(i+1)%4])/2)[0 if horizontal else 1])
    corners=np.roll(corners,-head,axis=0)/[w,h]
    return BedReference(corners.tolist(),small.size).corners
