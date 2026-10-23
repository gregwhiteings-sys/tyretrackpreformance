"""Visible instance-polygon centroid in original frame coordinates; no box fallback."""
import cv2
import numpy as np

def mask_centroid(polygon,width,height):
    points=np.asarray(polygon,dtype=np.float32)
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<3 or not np.isfinite(points).all():return None
    points=points.copy();points[:,0]=np.clip(points[:,0],0,width-1);points[:,1]=np.clip(points[:,1],0,height-1)
    m=cv2.moments(points)
    if abs(m['m00'])<1:return None
    return float(m['m10']/m['m00']),float(m['m01']/m['m00'])
