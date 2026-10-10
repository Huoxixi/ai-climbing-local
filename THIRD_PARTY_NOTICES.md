# Third-party sources, modifications and distribution scope

This source release preserves the local boulder application. It is not a model training release or a redistribution of the internal native desktop package. See README.md for the dependency table and links.

## Source actually included

- `backend/vendor/rtmlib`: RTMPose/YOLOX preprocessing and decoding subset from https://github.com/Tau-J/rtmlib . Apache-2.0. The original LICENSE and NOTICE are included. Upstream source ZIP SHA-256: `0c21e062674e31b92218974727fe5126e4cae365abff6f243f93d37d22f16df7`. The upstream BaseTool was replaced by a local-file-only ONNX adapter with explicit CPU/DirectML settings; no downloader/viewer/telemetry initialization is included. Other retained helpers are identified as unchanged in the original NOTICE.
- Detectron2-style YAML configurations under `backend/model_assets`: configuration structure for Mask R-CNN/R50-FPN from https://github.com/facebookresearch/detectron2 , Apache-2.0. Local configuration sets two classes, CPU, ROI p2/p3, threshold 0.4, short edge 1200 and at most 300 candidates. The upstream Apache license is retained in `licenses/Detectron2-LICENSE`. Detectron2 itself and its compiled extension are not bundled.
- `backend/vendor/NotoSansSC-VF.ttf`: Noto CJK font, SIL Open Font License 1.1; original `NotoSansSC-OFL.txt` retained. https://github.com/notofonts/noto-cjk . Unmodified font used for Chinese labels.
- `frontend/public/fonts`: original MiSans font files from Xiaomi; embedding terms are the original vendor's terms, not GPL. Source and copyright retained in its NOTICE.md: https://hyperos.mi.com/font/en/download/ and https://hyperos.mi.com/font/en/faq/ . Files are embedded as application assets, not sold separately or converted.
- Synthetic sample SVGs are newly authored geometric demonstration assets. Internal sample photographs, user media and third-party login photography are not included.

## External model assets (not bundled)

RTMW-L and YOLOX-S ONNX exports come from official OpenMMLab downloads. The installer fixes archive SHA-256 and the manifest fixes extracted file hashes. MMPose and YOLOX source licenses are Apache-2.0; this is not an assertion that all model or training-data conditions are interchangeable with the source license.

The climbing hold model originates from Tomáš Sláma's Kaggle Indoor Climbing Gym Hold And Route Segmentation: https://www.kaggle.com/datasets/tomasslama/indoor-climbing-gym-hold-segmentation . Internal provenance records state CC BY-SA 4.0 for dataset metadata and GPL-3.0 for research code. They do not establish that the exact model artifact may be publicly mirrored under the dataset license. No private checkpoint or public weight mirror is distributed here; users must verify their own rights to any externally obtained compatible checkpoint. Attribution does not imply endorsement.

## Installed dependencies (not vendored here)

Frontend and Python packages are obtained by users from their package sources. Their licenses remain in original packages. Vue, Vite, Element Plus, Axios, FastAPI, Pydantic and ONNX Runtime use MIT; Uvicorn and pywebview use BSD-3-Clause. NumPy and PyTorch/TorchVision retain BSD and native component notices; OpenCV is Apache-2.0 and includes additional native component notices; Pillow uses HPND. Other packages in requirements-local.txt retain their original licenses, including the openai SDK used by historical compatibility code.

`imageio-ffmpeg` wrapper is BSD-2-Clause. The FFmpeg executable supplied by an installed wheel may be GPL-enabled. A redistribution of such a binary requires the exact corresponding source/build and linked-library license materials, or a compliant source offer; the wrapper license is insufficient. The internal FFmpeg source bundle was not complete, so this repository and its source ZIP do not contain FFmpeg binaries or a bundled runtime. https://github.com/imageio/imageio-ffmpeg and https://ffmpeg.org/legal.html .

CPython uses the PSF license. Microsoft WebView2 is an external prerequisite under Microsoft's own terms, not copied from the developer browser profile.

## Research references, not claimed as copied implementations

Historical design work referenced vision-demos/rock_climbing, Climbing Analysis Toolbox, PoseAnalysis and Dynalytix. Their code is not present as a vendored tree in this snapshot; research mention does not prove copied code or completed feature integration. Earlier records disagreed about some project licenses; they are not used as redistribution authority. FreeMoCap, Pose2Sim, Sports2D, OpenCap, VideoPose3D, Ultralytics and MobileSAM were research candidates or older experiments, and are not the default local runtime.

Project-authored code is GPL-3.0. Third-party files keep their original license and copyright notices. Never replace their notices with the top-level project license.
