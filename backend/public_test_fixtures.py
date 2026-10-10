from core.climb_replay import REPLAY_OVERLAY_FILENAME
from core.replay_torso_trajectory import WINDOW_BASIS
from core.replay_center_of_mass import VERSION as MASS_VERSION


class FakeAnalyzer:
    def detect_holds(self, video, **kwargs):
        return {"holds": [{"id": 1, "bbox": [.1, .1, .2, .2]}],
                "hold_evidence": {"reference_frame": 0}, "hold_candidates": [],
                "models": {"holds": "test-local"}, "route": {"color": kwargs["route_color"]}}

    def analysis_contract(self, video_info):
        return {"contract_version": 1, "pipeline_version": "test-pipeline",
                "usage": {"planned_requests": 1, "actual_requests": 0}}

    def analyze(self, video, *, route_color, video_info, progress, cancelled, telemetry, confirmed_holds, overlay_target=None):
        progress("测试分析", 50)
        analysis = self.analysis_contract(video_info)
        analysis["usage"]["actual_requests"] = 1
        telemetry(analysis)
        (overlay_target or video.with_name(REPLAY_OVERLAY_FILENAME)).write_bytes(b"test-overlay")
        return {"schema_version": 2, "route": {"color": route_color},
                "video": {"frame_count": video_info.frame_count},
                "pose_samples": [],
                "holds": confirmed_holds["holds"], "hold_evidence": confirmed_holds["hold_evidence"],
                "hold_review_version": confirmed_holds.get("hold_review_version", 0),
                "attempt": {"sequence": [1, 2], "topped_out": True, "contacts": []},
                "analysis": analysis,
                "overlay": {"pose_rendering": "sampled_only_no_interpolation"}}

def scene():
    poses=[]
    for frame in (0,2,4,6):
        xy=[[.5,.5] for _ in range(17)]
        for i,p in {5:[.4,.3],6:[.6,.3],7:[.3,.4],8:[.7,.4],9:[.2,.2],10:[.8,.2],11:[.4,.6],12:[.6,.6],13:[.35,.75],14:[.65,.75],15:[.3,.9],16:[.7,.9]}.items():xy[i]=p
        poses.append({'observed':True,'source_frame_id':frame,'time_seconds':frame/4,
            'kpts_xy':xy,'kpts_score':[.9]*17,'wall_alignment':'reference',
            'wall_reference_transform':[[1,0,0],[0,1,0],[0,0,1]]})
    return {'video':{'width':96,'height':64,'fps':4,'frame_count':8,'duration_seconds':2},
        'holds':[{'id':1,'polygon':[[.1,.1],[.3,.1],[.3,.3],[.1,.3]]}],
        'pose_samples':poses,'attempt':{'contacts':[{'limb':'left_hand','hold_id':1,'start_source_frame':0,'end_source_frame':1}]},
        'center_of_mass_trajectory':{'version':MASS_VERSION,'climbing_window':{'basis':WINDOW_BASIS},'segments':[[{'time_seconds':0,'xy':[.5,.7]},{'time_seconds':1,'xy':[.3,.7]},{'time_seconds':1.5,'xy':[.3,.9]}]]}}
