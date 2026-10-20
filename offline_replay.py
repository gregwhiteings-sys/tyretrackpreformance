"""PC-only replay tester. Writes test output only; no camera, production DB or email."""
import argparse,csv,json,os,time
from pathlib import Path
import cv2
from ultralytics import YOLO
from three_line import ThreeLineCounter, line_segments, MODES
from count_line import count_point

class PreviewWriter:
    """One atomic metadata/JPEG packet, at most eight previews per second."""
    def __init__(self, output):
        self.output=Path(output);self.last_publish=0
    def publish(self, frame, state, force=False):
        now=time.monotonic()
        if not force and now-self.last_publish < .125:return
        ok,jpeg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,78])
        if not ok:return
        packet=json.dumps(state,separators=(',',':')).encode('utf-8')+b'\n'+jpeg.tobytes()
        temporary=self.output/'preview.tmp'
        try:
            temporary.write_bytes(packet)
            os.replace(temporary,self.output/'preview.packet')
            self.last_publish=now
        except OSError:
            pass  # A busy Windows reader must never interrupt counting or the saved MP4.


def main(argv=None,default_model=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',required=True)
    parser.add_argument('--model',default=str(default_model or Path(__file__).with_name('tyre_detector.pt')))
    parser.add_argument('--output',required=True)
    parser.add_argument('--left',type=float,default=0.)
    parser.add_argument('--right',type=float,default=1.)
    parser.add_argument('--top',type=float,default=.22)
    parser.add_argument('--bottom',type=float,default=.78)
    parser.add_argument('--middle',type=float,default=.59)
    parser.add_argument('--direction',choices=['Bottom to Top','Top to Bottom'],default='Bottom to Top')
    parser.add_argument('--mode',choices=MODES,default='zigzag')
    parser.add_argument('--compare-modes',action='store_true')
    parser.add_argument('--hand-count',type=int)
    parser.add_argument('--stop-file')
    parser.add_argument('--max-frames',type=int,default=0)
    args=parser.parse_args(argv)
    try:line_segments(480,270,args.middle,args.direction,args.mode,args.top,args.bottom,args.left,args.right)
    except ValueError as exc:parser.error(str(exc))
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    capture=cv2.VideoCapture(args.video)
    if not capture.isOpened():raise RuntimeError('Cannot open recording')
    fps=capture.get(cv2.CAP_PROP_FPS) or 15
    total_frames=capture.get(cv2.CAP_PROP_FRAME_COUNT)
    preview=PreviewWriter(output)
    started=time.monotonic();last_frame=None;last_state=None
    model=YOLO(args.model)
    counters={mode:ThreeLineCounter(args.direction,mode=mode) for mode in (MODES if args.compare_modes else (args.mode,))}
    for candidate in counters.values():
        candidate.set_bounds(args.top,args.bottom);candidate.set_span(args.left,args.right)
    counter=counters[args.mode]
    geometry_changes=[dict(frame=1,top=args.top,bottom=args.bottom,middle=args.middle,left=args.left,right=args.right)]
    control_stamp=None
    writer=cv2.VideoWriter(str(output/'annotated_test.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(480,270))
    if not writer.isOpened():raise RuntimeError('Cannot create annotated test video')
    events=[];frame_number=0
    try:
        while True:
            if args.stop_file and Path(args.stop_file).exists():break
            ok,frame=capture.read()
            if not ok or (args.max_frames and frame_number>=args.max_frames):break
            frame_number+=1;frame=cv2.resize(frame,(480,270))
            request=output/'geometry.request.json'
            try:
                stamp=request.stat().st_mtime_ns
                if stamp!=control_stamp:
                    change=json.loads(request.read_text(encoding='utf-8'))
                    top,bottom,middle=float(change['top']),float(change['bottom']),float(change['middle'])
                    left,right=float(change.get('left',args.left)),float(change.get('right',args.right))
                    line_segments(480,270,middle,args.direction,args.mode,top,bottom,left,right)
                    args.top,args.bottom,args.middle,args.left,args.right=top,bottom,middle,left,right
                    for candidate in counters.values():
                        candidate.set_bounds(top,bottom);candidate.set_span(left,right)
                    geometry_changes.append(dict(frame=frame_number,top=top,bottom=bottom,middle=middle,left=left,right=right))
                    control_stamp=stamp
            except (OSError,ValueError,KeyError):pass
            result=model.track(frame,persist=True,tracker='bytetrack.yaml',device='cpu',imgsz=384,
                               conf=.10,iou=.5,agnostic_nms=True,verbose=False)[0]
            if result.boxes is not None and result.boxes.id is not None:
                ids=result.boxes.id.int().cpu().tolist()
                for candidate in counters.values():candidate.begin_frame(ids)
                for box,ident,conf,cls in zip(result.boxes.xyxy.cpu().numpy(),ids,result.boxes.conf.cpu().tolist(),result.boxes.cls.int().cpu().tolist()):
                    x1,y1,x2,y2=map(int,box);bw=max(1,x2-x1);bh=max(1,y2-y1)
                    if bw/480>.68 or bh/270>.70 or bw*bh/(480*270)>.32 or max(bw/bh,bh/bw)>3.6:continue
                    x,y=count_point(box,480,270)
                    event=None
                    for mode,candidate in counters.items():
                        candidate_event=candidate.observe(ident,x,y,480,270,args.middle,frame_number,conf>=.35,(bw,bh))
                        if mode==args.mode:event=candidate_event
                    if event:events.append(dict(frame=frame_number,seconds=frame_number/fps,track_id=ident,line=('start','middle','end')[event[1]],total=counter.total))
                    name=str(model.names[cls]);suv=any(token in name.lower() for token in ('4x4','suv','fourwheel'))
                    colour=(255,140,35) if suv else (60,220,80)
                    cv2.rectangle(frame,(x1,y1),(x2,y2),colour,1)
                    cv2.putText(frame,f'{name} {ident}',(x1,max(15,y1-4)),cv2.FONT_HERSHEY_SIMPLEX,.4,colour,1)
            for (x1,y1,x2,y2),name in zip(line_segments(480,270,args.middle,args.direction,args.mode,args.top,args.bottom,args.left,args.right),('START','DIAGONAL' if args.mode!='horizontal' else 'MIDDLE','END')):
                cv2.line(frame,(round(x1),round(y1)),(round(x2),round(y2)),(0,255,255),1)
                cv2.putText(frame,name,(5,max(16,round((y1+y2)/2)-3)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
            cv2.putText(frame,f'TEST ONLY | unique {counter.total} | S/M/E {counter.crossings}',(5,265),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
            writer.write(frame)
            percent=min(100.0,frame_number/total_frames*100) if total_frames>0 else None
            state=dict(frame=frame_number,geometry=args.mode,top=args.top,bottom=args.bottom,left=args.left,right=args.right,percent=percent,total=counter.total,
                       crossings=list(counter.crossings),recoveries=list(counter.recoveries),
                       processing_fps=frame_number/max(.001,time.monotonic()-started))
            preview.publish(frame,state)
            last_frame,last_state=frame,state
    finally:
        capture.release();writer.release()
        if last_frame is not None:preview.publish(last_frame,last_state,force=True)
    cancelled=bool(args.stop_file and Path(args.stop_file).exists())
    if cancelled:args.hand_count=None
    report=dict(stopped_early=cancelled,mode='offline PC replay',video=str(Path(args.video).resolve()),model=str(Path(args.model).resolve()),
                frames=frame_number,middle=args.middle,top=args.top,bottom=args.bottom,left=args.left,right=args.right,geometry_changes=geometry_changes,direction=args.direction,count_geometry=args.mode,
                crossings=counter.crossings,recoveries=counter.recoveries,final_unique_total=counter.total,
                hand_count=args.hand_count,difference=counter.total-args.hand_count if args.hand_count is not None else None,
                production_totals_modified=False,note='Same count logic; CPU PT inference can differ from compiled OAK inference and live frame skips.')
    (output/'test_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (output/'crossings.csv').open('w',newline='',encoding='utf-8') as file:
        csvout=csv.DictWriter(file,fieldnames=['frame','seconds','track_id','line','total']);csvout.writeheader();csvout.writerows(events)
    if args.compare_modes:
        comparison={mode:dict(final_unique_total=c.total,crossings=c.crossings,recoveries=c.recoveries,
                              hand_count=args.hand_count,difference=c.total-args.hand_count if args.hand_count is not None else None)
                    for mode,c in counters.items()}
        (output/'mode_comparison.json').write_text(json.dumps(dict(shared_detections=True,geometry_changes=geometry_changes,results=comparison),indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
