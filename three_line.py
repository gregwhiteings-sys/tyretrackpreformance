"""Horizontal or zigzag three-line geometry, one accepted count per tyre track.
No hidden tyre estimates. Conservative continuation across short tracker-ID gaps.
"""
import math

MODES = ("horizontal", "zigzag", "zigzag_reverse")

def line_segments(width, height, middle=.59, direction="Bottom to Top", mode="horizontal", top=.22, bottom=.78, left_ratio=0., right_ratio=1.):
    if not (.05<=top<bottom<=.95 and bottom-top>=.099999):raise ValueError("Bounds require 5–95% and at least 10% separation")
    if not (0<=left_ratio<right_ratio<=1 and right_ratio-left_ratio>=.099999):raise ValueError("Line span must be within frame and at least 10% wide")
    if mode not in MODES: raise ValueError("Unknown count geometry: " + str(mode))
    if width <= 1 or height <= 1: raise ValueError("Frame dimensions must exceed one pixel")
    middle=max(top+.04,min(bottom-.04,middle))
    start,end=(top,bottom) if direction=="Top to Bottom" else (bottom,top)
    left=left_ratio*(width-1);right=right_ratio*(width-1);bottom=height-1
    first=(left,start*bottom,right,start*bottom)
    last=(left,end*bottom,right,end*bottom)
    diagonal=(left,start*bottom,right,end*bottom)
    if mode=="zigzag_reverse": diagonal=(left,end*bottom,right,start*bottom)
    if mode=="horizontal": diagonal=(left,middle*bottom,right,middle*bottom)
    return (first,diagonal,last)

class ThreeLineCounter:
    def __init__(self, direction="Bottom to Top", margin=4, max_gap=12, mode="horizontal"):
        if mode not in MODES: raise ValueError("Unknown count geometry")
        self.mode = mode
        self.top_ratio=.22
        self.bottom_ratio=.78
        self.left_ratio=0.;self.right_ratio=1.
        self._geometry = None
        self.direction = direction
        self.margin = margin
        self.max_gap = max_gap
        self.records = {}
        self.visible = set()
        self.positions = {}
        self.last_observed = {}
        self.counted = set()
        self.crossed = set()
        self.total = 0
        self.crossings = [0, 0, 0]
        self.recoveries = [0, 0, 0]

    def set_mode(self, mode):
        if mode not in MODES: raise ValueError("Unknown count geometry")
        if mode != self.mode:
            self.mode=mode
            self.reset_positions()

    def set_bounds(self, top, bottom):
        line_segments(100,100,.5,self.direction,self.mode,top,bottom)
        if (top,bottom)!=(self.top_ratio,self.bottom_ratio):
            self.top_ratio,self.bottom_ratio=top,bottom
            self.reset_positions()

    def set_span(self, left, right):
        line_segments(100,100,.5,self.direction,self.mode,self.top_ratio,self.bottom_ratio,left,right)
        if (left,right)!=(self.left_ratio,self.right_ratio):
            self.left_ratio,self.right_ratio=left,right
            self.reset_positions()

    def begin_frame(self, visible):
        self.visible = set(visible)

    def _continue_id(self, ident, x, y, frame, size):
        if ident in self.records or size is None:
            return
        candidates = []
        bw, bh = size
        for old, record in self.records.items():
            ox, oy, vx, vy, seen, ow, oh = record
            gap = frame-seen
            if old in self.visible or not 1 <= gap <= self.max_gap:
                continue
            if not (.85 <= bw/max(ow,1) <= 1.18 and .85 <= bh/max(oh,1) <= 1.18):
                continue
            # Require forward, close, predicted continuation. Ambiguity never merges.
            forward = y >= oy-2 if self.direction == "Top to Bottom" else y <= oy+2
            tolerance = max(3, min(bw,bh)*.18)
            if forward and abs(x-(ox+vx*gap)) <= tolerance and abs(y-(oy+vy*gap)) <= tolerance:
                candidates.append(old)
        if len(candidates) != 1:
            return
        old = candidates[0]
        if old in self.counted:
            self.counted.add(ident)
        for index in range(3):
            oldkey, newkey = (old,index), (ident,index)
            if oldkey in self.positions:
                self.positions[newkey] = self.positions[oldkey]
            if oldkey in self.crossed:
                self.crossed.add(newkey)
            if oldkey in self.last_observed:
                self.last_observed[newkey] = self.last_observed[oldkey]
        self.records[ident] = self.records.pop(old)

    def reset_positions(self):
        # Retain count history through pauses; discard motion spanning a pause.
        self.positions.clear()
        self.last_observed.clear()
        self.records.clear()

    def observe(self, ident, x, y, width, height, middle, frame, confirmed=True, size=None):
        if not confirmed:
            return None
        geometry=(width,height,middle,self.direction,self.mode,self.top_ratio,self.bottom_ratio,self.left_ratio,self.right_ratio)
        if geometry != self._geometry:
            self.reset_positions()
            self._geometry=geometry
        self._continue_id(ident,x,y,frame,size)
        prior = self.records.get(ident)
        if size is not None:
            vx = (x-prior[0])/max(1,frame-prior[4]) if prior else 0
            vy = (y-prior[1])/max(1,frame-prior[4]) if prior else 0
            self.records[ident] = (x,y,vx,vy,frame,*size)
        reverse = self.direction == "Top to Bottom"
        segments=line_segments(width,height,middle,self.direction,self.mode,self.top_ratio,self.bottom_ratio,self.left_ratio,self.right_ratio)
        event = None
        for index,(left,yl,right,yr) in enumerate(segments):
            key = (ident, index)
            slope=(yr-yl)/(right-left)
            # Signed perpendicular distance; margin remains in image pixels.
            side=(y-(yl+slope*(x-left)))/math.hypot(1,slope)
            previous = self.positions.get(key)
            if previous is not None:
                old, old_frame, old_x, old_y = previous
                crossed = old <= -self.margin and side > 0 if reverse else old >= self.margin and side < 0
                forward = y-old_y >= .5 if reverse else y-old_y <= -.5
                denominator=old-side
                fraction=old/denominator if denominator else -1
                cross_x=old_x+fraction*(x-old_x)
                on_segment=0 <= fraction <= 1 and left <= cross_x <= right
                if (crossed and forward and on_segment
                        and frame-self.last_observed.get(key,old_frame) <= self.max_gap
                        and key not in self.crossed):
                    self.crossed.add(key)
                    self.crossings[index] += 1
                    if ident not in self.counted:
                        self.counted.add(ident)
                        self.total += 1
                        if index:
                            self.recoveries[index] += 1
                        event = (ident, index)
            self.last_observed[key] = frame
            if abs(side) >= self.margin:
                self.positions[key] = (side, frame, x, y)
        if frame % 300 == 0:
            self.records = {key:value for key,value in self.records.items() if frame-value[4] <= 90}
            self.positions = {key:value for key,value in self.positions.items() if frame-self.last_observed.get(key,value[1]) <= 90}
            self.last_observed = {key:value for key,value in self.last_observed.items() if frame-value <= 90}
        return event


def simulation_checks(mode="horizontal"):
    results = []
    def drive(counter, ident, ys, start=1):
        return [event for frame,y in enumerate(ys,start)
                if (event := counter.observe(ident,50,y,100,101,.5,frame))]
    c=ThreeLineCounter(mode=mode);drive(c,1,[90,80,70,60,40,30,15])
    results.append(("All three lines: one count",c.total==1 and c.crossings==[1,1,1]))
    c=ThreeLineCounter(mode=mode);drive(c,1,[65,55,45,30,15])
    results.append(("Middle recovery",c.total==1 and c.recoveries[1]==1))
    c=ThreeLineCounter(mode=mode);drive(c,1,[35,28,18])
    results.append(("End recovery",c.total==1 and c.recoveries[2]==1))
    c=ThreeLineCounter(mode=mode);drive(c,1,[51,49,51,49])
    results.append(("Line jitter rejected",c.total==0))
    c=ThreeLineCounter(mode=mode);drive(c,1,[90,70]);drive(c,2,[90,70])
    results.append(("Two tyres counted separately",c.total==2))
    c=ThreeLineCounter(mode=mode)
    for frame,y in enumerate((90,80,70),1):
        c.begin_frame([1]);c.observe(1,50,y,100,101,.5,frame,True,(30,30))
    c.begin_frame([2]);c.observe(2,50,60,100,101,.5,4,True,(30,30))
    c.observe(2,50,40,100,101,.5,5,True,(30,30))
    results.append(("Short ID change does not duplicate",c.total==1 and 2 in c.counted))
    return results
