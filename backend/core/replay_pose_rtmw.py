"""Default offline RTMW-L 384x288 pose provider. Aliyun is historical only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
import time
from copy import deepcopy

import numpy as np

from core.climb_replay import (ReplayAnalyzerBase, ReplayConfigurationError,
                               REPLAY_PIPELINE_VERSION, VideoInfo)
from core.photo_route_colors import TWELVE_COLOR_VERSION
from core.replay_person_tracking import (VERSION as TRACKING_VERSION, MAX_RECOVERY_SECONDS,
                                         appearance, appearance_distance, near_route, recovery_geometry,
                                         route_in_frame)

MODEL = 'rtmw-l-384x288-cocktail14-20231122'
MODEL_DIRECTORY = Path(__file__).resolve().parents[1] / 'model_assets/rtmw-l-384x288'


def model_directory() -> Path:
    return Path(os.getenv('CLIMB_REPLAY_RTMW_MODEL_DIR') or MODEL_DIRECTORY)


def model_status(directory: Path | None = None) -> dict:
    directory = directory or model_directory()
    return {'name': MODEL, 'execution': 'local', 'requires_credentials': False,
            'available': all((directory / name).is_file()
                             for name in ('rtmw.onnx', 'detector.onnx', 'manifest.json'))}


class LocalRTMWReplayAnalyzer(ReplayAnalyzerBase):
    pose_model = MODEL
    pose_processing_notice = '岩点与 RTMW-L 骨架均在运行程序的本机分析；抽样画面不发送至阿里云。'

    def __init__(self, *, pose_fps: float | None = None, directory: Path | None = None,
                 device: str | None = None):
        try:
            self.pose_fps = max(1., min(20., float(pose_fps if pose_fps is not None
                                                 else os.getenv('CLIMB_REPLAY_POSE_FPS', '10'))))
        except (ValueError, TypeError):
            self.pose_fps = 10.
        self._default_fps = self.pose_fps
        self.focus_windows = []
        self.stage_timings = {'person': 0., 'skeleton': 0.}
        self.directory = directory or model_directory()
        self.device = device or os.getenv('CLIMB_REPLAY_RTMW_DEVICE', 'auto')
        self._models = None
        self._load_lock = threading.Lock()
        self._previous_box = None
        self._previous_appearance = None
        self._previous_source_frame = None
        self._pending_box = None
        self._pending_source_frame = None
        self._source_fps = 30.
        self._current_source_frame = 0
        self._current_frame = None
        self._active_frame_cache = None
        self._route_bounds = None
        self._reference_transform_supplied = False
        self._frame_route_bounds = None
        self._pose_cache = {}
        self._cache_path = None
        self._cache_binding = None
        self._cache_dirty = 0
        self.last_pose_cache_hit = False
        self.last_pose_failure = None
        self.failure_counts = {}

    def configure_cache(self, path, binding):
        # Selected identities depend on preceding observations. Cache raw detector
        # and per-box pose outputs, then select again even when adding dense frames.
        binding = {**binding, 'person_selection': TRACKING_VERSION, 'cache_schema': 3}
        self._cache_path, self._cache_binding = Path(path), binding
        self._pose_cache, self._cache_dirty = {}, 0
        try:
            saved = json.loads(self._cache_path.read_text('utf-8'))
            if saved.get('binding') == binding:
                self._pose_cache = saved['frames']
        except (OSError, ValueError, KeyError):
            pass

    def flush_pose_cache(self):
        if self._cache_path and self._cache_dirty:
            from .climb_replay import _atomic_json
            _atomic_json(self._cache_path, {'binding':self._cache_binding, 'frames':self._pose_cache})
            self._cache_dirty = 0

    def _load_models(self):
        with self._load_lock:
            if self._models is not None:
                return self._models
            try:
                manifest = json.loads((self.directory / 'manifest.json').read_text('utf-8'))
                expected = json.loads((MODEL_DIRECTORY / 'manifest.json').read_text('utf-8'))
                if manifest != expected or manifest['model'] != MODEL:
                    raise ValueError('model manifest mismatch')
                for item in expected['files']:
                    path = self.directory / item['file']
                    if path.stat().st_size != item['bytes']:
                        raise ValueError('model size mismatch')
                    with path.open('rb') as stream:
                        if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                            raise ValueError('model checksum mismatch')
                from vendor.rtmlib import RTMPose, YOLOX
                pose = RTMPose(str(self.directory / 'rtmw.onnx'),
                               model_input_size=(288, 384), device=self.device)
                detector = YOLOX(str(self.directory / 'detector.onnx'),
                                 model_input_size=(640, 640), score_thr=.35, device=self.device)
                self._models = pose, detector
            except Exception as exc:
                raise ReplayConfigurationError(
                    'RTMW 本地模型或运行依赖不可用。请运行 install-replay-rtmw-local.ps1 安装并校验；'
                    '已有复盘可继续查看。') from exc
            return self._models

    def _prepare_pose_run(self, confirmed_holds: dict) -> None:
        from core.replay_model_cache import release_local_model
        release_local_model()
        self._previous_box = None
        self._previous_appearance = None
        self._previous_source_frame = None
        self._pending_box = None
        self._pending_source_frame = None
        self._reference_transform_supplied = False
        self._frame_route_bounds = None
        self.stage_timings = {'person': 0., 'skeleton': 0.}
        self.failure_counts = {}
        boxes = [hold['bbox'] for hold in confirmed_holds.get('holds', [])
                 if hold.get('bbox') and hold.get('route_candidate') is not False]
        self._route_bounds = ([min(b[0] for b in boxes), min(b[1] for b in boxes),
                               max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)]
                              if boxes else None)
        self._load_models()

    def set_person_reference_transform(self, matrix, reference_size, frame_size):
        self._reference_transform_supplied = True
        self._frame_route_bounds = route_in_frame(self._route_bounds, matrix, reference_size, frame_size)

    def configure_sampling(self, options=None):
        options = options or {}
        self.pose_fps = options.get('pose_fps') or self._default_fps
        self.focus_windows = options.get('focus_windows') or []

    def _sampling_positions(self, video_info):
        from .replay_sampling import native_plan
        self._source_fps = video_info.fps
        fps, positions, self.sampling_plan = native_plan(video_info, self.pose_fps, self.focus_windows)
        return fps, positions

    def runtime_metadata(self) -> dict:
        if self._models is None:
            return {'requested_device': self.device, 'loaded': False}
        pose, detector = self._models
        return {'requested_device': self.device, 'loaded': True,
                'onnxruntime': pose.ort.__version__,
                'pose_providers': pose.session.get_providers(),
                'detector_providers': detector.session.get_providers(),
                'pose_fallback': pose.fallback_reason, 'detector_fallback': detector.fallback_reason,
                'missing_pose_reasons': dict(self.failure_counts),
                'person_selection': TRACKING_VERSION,
                'timings_ms': {key: round(value * 1000) for key, value in self.stage_timings.items()}}

    def analysis_contract(self, video_info: VideoInfo) -> dict:
        fps, positions = self._sampling_positions(video_info)
        return {
            'contract_version': 2, 'pipeline_version': REPLAY_PIPELINE_VERSION,
            'provider': {'name': 'local-rtmw', 'service': 'RTMW-L 384×288', 'region': 'local',
                         'execution': 'local', 'uploads_frames': False},
            'models': {'holds': {'name': self.hold_model, 'version': 'pending'},
                       'pose': {'name': MODEL, 'version': '20231122', 'keypoints': 133,
                                'input_size_wh': [288, 384], 'body_contract': 'coco17'},
                       'person': {'name': 'yolox-s-humanart', 'input_size_wh': [640, 640]}},
            'algorithms': {'hold_color': TWELVE_COLOR_VERSION,
                           'contact': 'mask-contour-dwell-0.4s-v2',
                           'person_selection': TRACKING_VERSION},
            'sampling': {'source_fps': round(video_info.fps, 6), 'requested_fps': self.pose_fps,
                         'effective_fps': round(fps, 6), **self.sampling_plan},
            # planned_requests retained as a historical display alias for sample count.
            'usage': {'planned_frames': len(positions), 'planned_requests': len(positions),
                      'actual_requests': 0, 'successful_requests': 0, 'failed_requests': 0,
                      'request_image_bytes': 0, 'local_inferences': 0,
                      'successful_local_inferences': 0, 'failed_local_inferences': 0,
                      'successful_pose_frames': 0, 'responses_without_pose': 0,
                      'decode_failed_frames': 0, 'unprocessed_frames': len(positions)},
            'cost': {'currency': 'CNY', 'unit_price': 0, 'billable_requests_estimate': 0,
                     'estimated_amount': 0., 'basis': '本地 RTMW 骨架分析，无付费姿态 API 调用。'},
            'timings_ms': {key: 0 for key in ('total', 'background', 'hold_inference', 'pose',
                                             'contact', 'overlay', 'report')},
            'runtime': self.runtime_metadata(),
        }

    @staticmethod
    def _box_iou(a, b):
        intersection = max(0., min(a[2], b[2]) - max(a[0], b[0])) * max(
            0., min(a[3], b[3]) - max(a[1], b[1]))
        area = lambda box: max(0., box[2] - box[0]) * max(0., box[3] - box[1])
        return intersection / max(1e-9, area(a) + area(b) - intersection)

    def _select_box(self, boxes, width, height):
        bounds = self._frame_route_bounds if self._reference_transform_supplied else self._route_bounds
        valid = []
        for box in np.asarray(boxes).reshape(-1, 4):
            if not np.isfinite(box).all():
                continue
            box = np.clip(box, [0, 0, 0, 0], [width, height, width, height]).astype(float)
            if box[2] - box[0] > 4 and box[3] - box[1] > 4:
                valid.append(box)
        if not valid:
            self._pending_box = None
            return None, 'person_not_detected'
        if self._previous_box is not None:
            ranked = sorted(((self._box_iou(self._previous_box, b), b) for b in valid),
                            key=lambda item: item[0], reverse=True)
            dt = ((self._current_source_frame - self._previous_source_frame) / self._source_fps
                  if self._previous_source_frame is not None else 0.)
            current_appearance = lambda b: appearance(self._current_frame, b) if self._current_frame is not None else None
            if (ranked[0][0] >= .1 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= .05)
                    and dt <= MAX_RECOVERY_SECONDS
                    and (self._previous_appearance is None or appearance_distance(
                        self._previous_appearance, current_appearance(ranked[0][1])) <= .65)):
                self._pending_box = None
                return ranked[0][1], 'iou_follow'
            # A short detector gap / abrupt box change may recover only with
            # matching appearance, bounded movement and two real observations.
            candidates = [b for b in valid if 0 < dt <= MAX_RECOVERY_SECONDS
                          and (self._route_bounds is None or bounds is not None)
                          and near_route(b, bounds, width, height)
                          and recovery_geometry(self._previous_box, b)
                          and appearance_distance(self._previous_appearance, current_appearance(b)) <= .3]
            if len(candidates) == 1:
                box = candidates[0]
                pending_dt = ((self._current_source_frame - self._pending_source_frame) / self._source_fps
                              if self._pending_source_frame is not None else 0.)
                if (self._pending_box is not None and 0 < pending_dt <= .35
                        and self._box_iou(self._pending_box, box) >= .3):
                    self._pending_box = None
                    return box, 'appearance_reacquired'
                self._pending_box, self._pending_source_frame = box.copy(), self._current_source_frame
                return None, 'track_recovery_pending'
            self._pending_box = None
            return None, 'track_missing_or_ambiguous'
        if self._route_bounds is not None and self._reference_transform_supplied and bounds is None:
            return None, 'route_reference_unavailable'
        valid = [b for b in valid if near_route(b, bounds, width, height)]
        if not valid:
            return None, 'person_outside_confirmed_route'
        def initial_score(box):
            area = (box[2] - box[0]) * (box[3] - box[1]) / (width * height)
            if bounds is None:
                return area
            center = (box[:2] + box[2:]) / 2 / [width, height]
            left, top, right, bottom = bounds
            dx = max(left - center[0], 0, center[0] - right)
            dy = max(top - center[1], 0, center[1] - bottom)
            return area - 2 * (dx * dx + dy * dy)
        ranked = sorted(valid, key=initial_score, reverse=True)
        if len(ranked) > 1 and initial_score(ranked[0]) - initial_score(ranked[1]) < .025:
            return None, 'initial_person_ambiguous'
        return ranked[0], 'route_initial_selection'

    def _pose_frame(self, frame, *, frame_id, source_frame_id, before_request=None):
        key = str(source_frame_id)
        self._current_frame, self._current_source_frame = frame, source_frame_id
        self._active_frame_cache = self._pose_cache.get(key, {})
        self.last_pose_cache_hit = 'boxes' in self._active_frame_cache
        self.last_pose_failure = None
        record = self._infer_pose_frame(frame, frame_id=frame_id, source_frame_id=source_frame_id)
        if self.last_pose_failure:
            self.failure_counts[self.last_pose_failure] = self.failure_counts.get(self.last_pose_failure, 0) + 1
        if self._cache_path:
            self._pose_cache[key] = self._active_frame_cache
            self._cache_dirty += 1
            if self._cache_dirty >= 20:
                self.flush_pose_cache()
        return record

    def _infer_pose_frame(self, frame, *, frame_id, source_frame_id):
        pose, detector = self._load_models()
        height, width = frame.shape[:2]
        started = time.perf_counter()
        cached = self._active_frame_cache
        boxes = cached.get('boxes')
        if boxes is None:
            boxes = np.asarray(detector(frame)).reshape(-1, 4).tolist()
            cached['boxes'] = boxes
        box, selection = self._select_box(boxes, width, height)
        self.stage_timings['person'] += time.perf_counter() - started
        if box is None:
            self.last_pose_failure = selection
            return None
        started = time.perf_counter()
        pose_key = json.dumps(box.round(6).tolist())
        poses = cached.setdefault('poses', {})
        if pose_key in poses:
            xy, raw_scores = poses[pose_key]
        else:
            self.last_pose_cache_hit = False
            xy, raw_scores = pose(frame, [box.tolist()])
            # Keep raw evidence only; do not cache a sequential tracking decision.
            poses[pose_key] = [np.where(np.isfinite(a), a, None).tolist()
                               for a in (np.asarray(xy), np.asarray(raw_scores))]
        self.stage_timings['skeleton'] += time.perf_counter() - started
        xy, raw_scores = np.asarray(xy[0], dtype=float), np.asarray(raw_scores[0], dtype=float)
        if xy.shape != (133, 2) or raw_scores.shape != (133,):
            raise RuntimeError('RTMW 模型输出格式与已核验版本不一致')
        finite = np.isfinite(xy).all(axis=1) & np.isfinite(raw_scores)
        inside = ((xy[:, 0] >= 0) & (xy[:, 0] < width)
                  & (xy[:, 1] >= 0) & (xy[:, 1] < height))
        scores = np.where(finite & inside, np.clip(raw_scores, 0, 1), 0.)
        coords = np.where(np.isfinite(xy), xy, 0.) / [width, height]
        if np.count_nonzero(scores[5:17] >= .15) < 6:
            self.last_pose_failure = 'insufficient_body_joints'
            return None
        # An entering hand / cropped body must not establish an identity that
        # subsequent full-person detections can never recover. Wait for visible
        # shoulders and hips before committing an initial track at the edge.
        edge_partial = (box[3] >= height * .98 or box[1] <= height * .02) and box[3] - box[1] < height * .3
        if self._previous_box is None and edge_partial and not np.all(scores[[5, 6, 11, 12]] >= .2):
            self.last_pose_failure = 'initial_body_incomplete'
            return None
        self._previous_box = box.copy()
        self._previous_source_frame = source_frame_id
        self._previous_appearance = appearance(frame, box)
        points, confidence = coords.round(6).tolist(), scores.round(6).tolist()
        return {
            'frame_id': frame_id, 'source_frame_id': source_frame_id, 'track_id': 0,
            'kpts_xy': points[:17], 'kpts_score': confidence[:17],
            'bbox_xywh': [round(float(box[0] / width), 6), round(float(box[1] / height), 6),
                          round(float((box[2] - box[0]) / width), 6),
                          round(float((box[3] - box[1]) / height), 6)],
            'wholebody': {'schema': 'coco-wholebody-133', 'coordinates': 'source_image_normalized',
                          'kpts_xy': points, 'kpts_score': confidence,
                          'raw_scores': np.nan_to_num(raw_scores, nan=0., posinf=0., neginf=0.).tolist()},
            'pose_evidence': {'provider': 'local-rtmw', 'model': MODEL,
                              'selection': selection, 'person_selection_version': TRACKING_VERSION,
                              'tracking': 'heuristic_not_identity_verified'},
        }
