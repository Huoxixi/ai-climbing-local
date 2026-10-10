import { centerOfMass } from './replayCenterOfMass.js'

const edges = [[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]]
const colors = { left_hand:'#50c4eb',right_hand:'#ed5cc1',left_foot:'#ffb36a',right_foot:'#8fde57' }
export function displayedHoldColors(contacts, index, finished = false) {
  const active = new Map(), used = new Map()
  for(const c of contacts || []) {
    if(!colors[c.limb] || !Number.isFinite(c.start_source_frame) || !Number.isFinite(c.end_source_frame)
      || c.start_source_frame<0 || c.end_source_frame<c.start_source_frame || c.start_source_frame>index)continue
    used.set(String(c.hold_id),'#f1d04b')
    if(index<=c.end_source_frame && (!active.has(c.limb) || active.get(c.limb).start_source_frame<c.start_source_frame))active.set(c.limb,c)
  }
  return finished ? used : new Map([...active.values()].map(c=>[String(c.hold_id),colors[c.limb]]))
}
export function analysisFrame(video) {
  if (!(video?.width > 0 && video?.height > 0)) return null
  const { width, height } = video
  return { width:width*2, height, video:[0,0,width,height], panel:[width,0,width,height], map:[width,0,width,height], source:video }
}

export function registeredDisplayPoses(result) {
  const {width,height} = result?.video || {}
  if (!(width>0 && height>0)) return []
  return (result?.pose_samples || []).map(sample => {
    const m=sample.wall_reference_transform, diagnostics=sample.wall_alignment_diagnostics || sample.motion_registration || {}
    const determinant=m?.length===3 && m.every(r=>r?.length===3) ? m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]) : 0
    const valid=sample.observed && ['aligned','reference'].includes(sample.wall_alignment)
      && Number.isFinite(determinant) && Math.abs(determinant)>1e-8
      && m?.length===3 && m.every(r=>r?.length===3 && r.every(Number.isFinite))
      && sample.kpts_xy?.length===17 && sample.kpts_score?.length===17
      && !(Number.isFinite(diagnostics.median_error_px) && diagnostics.median_error_px>3)
      && !(Number.isFinite(diagnostics.inliers) && diagnostics.inliers<12)
    const points=[], scores=[]
    for(let i=0;i<17;i++) {
      const xy=sample.kpts_xy?.[i], score=sample.kpts_score?.[i]
      const p=valid && xy?.length===2 && xy.every(v=>Number.isFinite(v)&&v>0&&v<1) && score>=.5 && score<=1
        ? m.map(r=>r[0]*xy[0]*width+r[1]*xy[1]*height+r[2]) : null
      const okay=p?.every(Number.isFinite) && Math.abs(p[2])>1e-6
      points.push(okay ? [p[0]/p[2]/width,p[1]/p[2]/height] : [0,0]); scores.push(okay?score:0)
    }
    return {source_frame_id:sample.source_frame_id,time_seconds:sample.time_seconds,observed:Boolean(valid),kpts_xy:points,kpts_score:scores}
  }).sort((a,b)=>a.source_frame_id-b.source_frame_id)
}

export function displayPoseAt(samples, frame, fps) {
  if (!samples?.length || !(fps>0)) return null
  let low=0,high=samples.length-1
  while(low<=high) {const mid=(low+high)>>1;if(samples[mid].source_frame_id<frame)low=mid+1;else high=mid-1}
  const b=samples[low],a=samples[low-1]
  if(b?.source_frame_id===frame)return b.observed?b:null
  // Keep interpolation inside adjacent observations; never bridge a missing pose.
  if(!a?.observed || !b?.observed || (b.source_frame_id-a.source_frame_id)/fps>.6)return null
  const alpha=(frame-a.source_frame_id)/(b.source_frame_id-a.source_frame_id)
  return {observed:true,kpts_xy:a.kpts_xy.map((p,i)=>p.map((v,j)=>v*(1-alpha)+b.kpts_xy[i][j]*alpha)),
    kpts_score:a.kpts_score.map((s,i)=>Math.min(s,b.kpts_score[i]))}
}

export function drawAnalysisView(ctx, video, frame, holds, contacts, visualization, time) {
  const f=frame, fps=f.source.fps || 30, index=Math.floor(time*fps+1e-6)
  ctx.fillStyle='#0e100f';ctx.fillRect(0,0,f.width,f.height)
  // All image pixels on the left come directly from the original video.
  ctx.drawImage(video,0,0,video.videoWidth,video.videoHeight,...f.video)
  ctx.save();ctx.beginPath();ctx.rect(...f.panel);ctx.clip()
  const project=p=>[f.map[0]+p[0]*f.map[2],f.map[1]+p[1]*f.map[3]]
  const line=points=>{ctx.beginPath();points.forEach((p,i)=>ctx[i?'lineTo':'moveTo'](...project(p)))}
  const finished=video.ended || f.source.frame_count>0 && index>=f.source.frame_count-1
  const occupied=displayedHoldColors(contacts,index,finished)
  for(const hold of holds || []) {
    if(!hold.polygon?.length || hold.polygon.length<3)continue
    line(hold.polygon);ctx.closePath();ctx.strokeStyle=occupied.get(String(hold.id))||'#818780';ctx.lineWidth=Math.max(2,f.source.width/240)
    if(occupied.has(String(hold.id))){ctx.fillStyle=ctx.strokeStyle;ctx.fill()}ctx.stroke()
  }
  ctx.strokeStyle='#75e7ee';ctx.lineWidth=Math.max(2,f.source.width/240)
  for(const run of visualization?.center_of_mass_trajectory?.segments || []) {
    const shown=run.filter(p=>p.time_seconds<=time && p.xy?.length===2 && p.xy.every(Number.isFinite))
    if(shown.length>=2){line(shown.map(p=>p.xy));ctx.stroke()}
  }
  const pose=displayPoseAt(visualization?.pose_samples,index,fps)
  if(pose) {
    ctx.strokeStyle='#e8de90';ctx.lineWidth=Math.max(2,f.source.width/220)
    for(const [a,b]of edges)if(Math.min(pose.kpts_score[a],pose.kpts_score[b])>=.5){line([pose.kpts_xy[a],pose.kpts_xy[b]]);ctx.stroke()}
    const center=centerOfMass(pose)
    if(center){const p=project(center);ctx.beginPath();ctx.arc(...p,Math.max(4,f.source.width/110),0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill()}
  }
  ctx.restore()
}
