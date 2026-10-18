"""Real model loading and synthetic inference; no personal media or paid API."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
os.environ.update(LOCAL_ONLY='true', PYTHON_DOTENV_DISABLED='1', HF_HUB_OFFLINE='1')
from installer.engine import sha, HOLD_SHA, MOBILESAM_SHA
assert sha(ROOT / 'models/verified-model_final.pth') == HOLD_SHA, '岩点模型校验失败'
assert sha(ROOT / 'models/mobile_sam.pt') == MOBILESAM_SHA, '补充分割模型校验失败'
import numpy as np
import torch
torch.set_num_threads(min(4, os.cpu_count() or 1))
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from core.replay_pose_rtmw import LocalRTMWReplayAnalyzer

cfg = get_cfg()
cfg.merge_from_file(str(ROOT / 'backend/model_assets/climbing-mask-rcnn-r50-fpn-1200.yaml'))
cfg.MODEL.WEIGHTS = str(ROOT / 'models/verified-model_final.pth')
cfg.MODEL.DEVICE = 'cpu'
predictor = DefaultPredictor(cfg)
with torch.inference_mode():
    output = predictor(np.zeros((64,64,3),dtype=np.uint8))
assert 'instances' in output
del predictor
sys.path.insert(0,str(ROOT/'vendor/MobileSAM'))
from mobile_sam import sam_model_registry, SamPredictor
sam = sam_model_registry['vit_t'](checkpoint=str(ROOT/'models/mobile_sam.pt'))
sam.eval()
sam_predictor=SamPredictor(sam)
sam_predictor.set_image(np.zeros((64,64,3),dtype=np.uint8))
sam_masks, _, _=sam_predictor.predict(point_coords=np.array([[32,32]]),point_labels=np.array([1]))
assert sam_masks.shape[-2:]==(64,64)
del sam_predictor,sam
pose = LocalRTMWReplayAnalyzer(device='cpu', directory=ROOT / 'backend/model_assets/rtmw-l-384x288')
pose_network, person_network = pose._load_models()
blank = np.zeros((64,64,3),dtype=np.uint8)
person_network(blank)
keypoints, scores = pose_network(blank)
assert keypoints.size and scores.size
import imageio_ffmpeg
import subprocess
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-version'],check=True,stdout=subprocess.DEVNULL)
import webview
from desktop.server import create_app
from core.replay_pose_clip import LocalClipReplayAnalyzer
print('岩点模型、骨架模型、视频组件与应用入口检查通过',flush=True)
