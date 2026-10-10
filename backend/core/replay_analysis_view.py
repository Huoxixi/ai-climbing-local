"""Original on the left; registered evidence only on the right."""
from copy import deepcopy
import math
import cv2
import numpy as np

from .replay_action_trajectory import registered_points
from .replay_torso_trajectory import center_of_mass_trajectory, WINDOW_BASIS
from .replay_center_of_mass import center_of_mass_point, VERSION as MASS_VERSION

LAYOUT = 'split_analysis_right_v11'
EDGES = ((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16))
COLORS = {'left_hand':(235,196,80),'right_hand':(193,92,237),
          'left_foot':(106,179,255),'right_foot':(87,222,143)}


def visual_evidence(result):
    video = result.get('video') or {}
    poses = []
    for sample in result.get('pose_samples', []):
        frame = sample.get('source_frame_id')
        if not isinstance(frame,int) or isinstance(frame,bool):
            time,fps = sample.get('time_seconds'),video.get('fps')
            if not isinstance(time,(int,float)) or not isinstance(fps,(int,float)) or not math.isfinite(time) or not math.isfinite(fps) or time<0 or fps<=0:
                continue
            frame = round(time*fps)
        if frame<0:
            continue
        mapped = registered_points(sample, video)
        poses.append({'source_frame_id':frame,
            'time_seconds':sample.get('time_seconds'), 'observed':mapped is not None,
            'kpts_xy':mapped[0].round(6).tolist() if mapped is not None else [[0.,0.]]*17,
            'kpts_score':[float(s) if valid else 0. for s,valid in zip(sample['kpts_score'],mapped[1])] if mapped is not None else [0.]*17})
    poses.sort(key=lambda s:s['source_frame_id'])
    contacts = deepcopy((result.get('attempt') or {}).get('contacts') or [])
    fps = video.get('fps') or 0
    for contact in contacts:
        for prefix in ('start','end'):
            time = contact.get(f'{prefix}_time_seconds')
            if isinstance(time,(int,float)) and math.isfinite(time) and fps>0:
                contact[f'{prefix}_source_frame'] = time*fps
    return {'version':LAYOUT, 'video':deepcopy(video), 'pose_samples':poses,
            'contacts':contacts,
            'center_of_mass_trajectory':deepcopy(result.get('center_of_mass_trajectory'))
                if (result.get('center_of_mass_trajectory') or {}).get('version')==MASS_VERSION
                and ((result.get('center_of_mass_trajectory') or {}).get('climbing_window') or {}).get('basis')==WINDOW_BASIS
                else center_of_mass_trajectory(result),
            'center_of_mass':{'version':MASS_VERSION,'label':'估算重心','dimensionality':'2d_projection'}}


class AnalysisView:
    def __init__(self, result):
        from .climb_replay import build_pose_render_timeline
        self.video = result['video']
        evidence = visual_evidence(result)
        self.timeline = build_pose_render_timeline(evidence['pose_samples'], self.video['frame_count'])
        samples = {s['source_frame_id']:s for s in evidence['pose_samples']}
        missing = {s['source_frame_id'] for s in evidence['pose_samples'] if not s['observed']}
        self.timeline = {frame:sample for frame,sample in self.timeline.items()
            if sample.get('render_mode')!='edge_hold' and not (sample.get('render_mode')=='interpolated'
                and (any(sample['left_sample_frame']<bad<sample['right_sample_frame'] for bad in missing)
                    or (sample['right_sample_frame']-sample['left_sample_frame'])/self.video['fps']>.6))}
        for sample in self.timeline.values():
            if sample.get('render_mode')=='interpolated':
                left,right = samples[sample['left_sample_frame']],samples[sample['right_sample_frame']]
                sample['kpts_score'] = [min(a,b) for a,b in zip(left['kpts_score'],right['kpts_score'])]
        self.trajectory = evidence['center_of_mass_trajectory']
        self.holds = result.get('holds') or []
        self.contacts = evidence['contacts']

    def frame(self, raw, index, size):
        width,height = size
        pane = width//2
        scale = min(pane/raw.shape[1],height/raw.shape[0])
        w,h = max(1,round(raw.shape[1]*scale)),max(1,round(raw.shape[0]*scale))
        x,y = (pane-w)//2,(height-h)//2
        canvas = np.full((height,width,3),(13,16,18),np.uint8)
        canvas[y:y+h,x:x+w] = cv2.resize(raw,(w,h),interpolation=cv2.INTER_AREA)
        right = canvas[:,pane:]
        stroke = max(1,round(min(w,h)/240))
        def point(xy):
            return (round(x+xy[0]*w),round(y+xy[1]*h))
        active = {}
        for contact in self.contacts:
            start,end = contact.get('start_source_frame'),contact.get('end_source_frame')
            limb = contact.get('limb')
            if (limb in COLORS and isinstance(start,(int,float)) and isinstance(end,(int,float))
                    and start <= index <= end and (limb not in active or start > active[limb][0])):
                active[limb] = (start,str(contact.get('hold_id')))
        occupied = {hold:limb for limb,(_,hold) in active.items()}
        finished = index >= self.video['frame_count'] - 1
        used = {str(c.get('hold_id')) for c in self.contacts if c.get('limb') in COLORS
            and isinstance(c.get('start_source_frame'),(int,float)) and isinstance(c.get('end_source_frame'),(int,float))
            and math.isfinite(c['start_source_frame']) and math.isfinite(c['end_source_frame'])
            and 0 <= c['start_source_frame'] <= c['end_source_frame'] and c['start_source_frame'] <= index}
        for hold in self.holds:
            polygon = hold.get('polygon') or []
            if len(polygon)<3 and len(hold.get('bbox') or [])>=4:
                bx,by,bw,bh = hold['bbox'][:4]
                polygon = [[bx,by],[bx+bw,by],[bx+bw,by+bh],[bx,by+bh]]
            if len(polygon)<3:
                continue
            poly = np.asarray([point(p) for p in polygon],np.int32)
            limb = occupied.get(str(hold.get('id')))
            color = COLORS.get(limb,(128,135,129))
            if finished and str(hold.get('id')) in used:
                color = (75,208,241)
            if limb or finished and str(hold.get('id')) in used:
                cv2.fillPoly(right,[poly],color,cv2.LINE_AA)
            cv2.polylines(right,[poly],True,color,stroke,cv2.LINE_AA)
        time = index/self.video['fps']
        for run in self.trajectory.get('segments',[]):
            points = [point(p['xy']) for p in run if p['time_seconds'] <= time]
            if len(points)>=2:
                cv2.polylines(right,[np.asarray(points,np.int32)],False,(238,231,117),stroke,cv2.LINE_AA)
        sample = self.timeline.get(index)
        if sample:
            xy,scores = sample['kpts_xy'],sample['kpts_score']
            for a,b in EDGES:
                if min(scores[a],scores[b])>=.5:
                    cv2.line(right,point(xy[a]),point(xy[b]),(144,222,232),stroke+1,cv2.LINE_AA)
            for p,score in zip(xy,scores):
                if score>=.5:
                    cv2.circle(right,point(p),stroke+1,(151,232,245),-1,cv2.LINE_AA)
            center = center_of_mass_point(sample)
            if center is not None:
                cv2.circle(right,point(center),max(3,stroke+2),(255,255,255),-1,cv2.LINE_AA)
        return canvas
