"""SAM 2 video masks, masked edges and source-only static motion per shot/view."""
from __future__ import annotations

import gc
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path
import sys
import tempfile
import time
import urllib.request

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .video import (PROJECT, data_root, decode_selected, frame_range, key_indices,
                    load_shots, sha256, verify_pts, video_path, write_json)

MODEL = "sam2.1_hiera_small"
MODEL_URL = f"https://dl.fbaipublicfiles.com/segment_anything_2/092824/{MODEL}.pt"
MODEL_CONFIG = "configs/sam2.1/sam2.1_hiera_s.yaml"


def log(event: str, **fields) -> None:
    record = {"at": time.time(), "event": event, **fields}
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, allow_nan=False)
    print(line, file=sys.stderr, flush=True)
    with (root / "source.jsonl").open("a") as handle:
        handle.write(line + "\n")


def selected_shots(census: dict, shot_id: str | None) -> list[dict]:
    shots = [s for s in census["shots"] if s["classification"] in ("machine", "transition")]
    if shot_id is not None:
        shots = [s for s in shots if s["id"] == shot_id]
        if not shots:
            raise ValueError(f"No machine/transition shot {shot_id!r}")
    return shots


def imwrite(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write image: {path}")


def crop_half(image: np.ndarray, view: dict) -> np.ndarray:
    x, y, w, h = view["rectSourcePixels"]
    crop = image[y:y+h, x:x+w]
    return cv2.resize(crop, (max(1, round(w / 2)), max(1, round(h / 2))), interpolation=cv2.INTER_AREA)


def keyframes(video_id: str, shot_id: str | None = None) -> Path:
    census = load_shots(video_id)
    fps = Fraction(*census["fps"])
    root = data_root() / video_id
    shots = selected_shots(census, shot_id)
    requested = sorted({i for shot in shots for i in key_indices(shot, fps)})
    owners = {}
    for shot in shots:
        for index in key_indices(shot, fps):
            owners.setdefault(index, []).append(shot)
    for index, image in decode_selected(video_path(video_id), requested, fps):
        for shot in owners[index]:
            for view in shot["views"]:
                imwrite(root / shot["id"] / view["viewId"] / "frames" / f"{index}.png", image)
    sheet = make_review(video_id, overlay=False)
    log("keyframes", videoId=video_id, shots=len(shots), path=str(sheet))
    return sheet


def model_checkpoint() -> Path:
    path = data_root() / "models" / f"{MODEL}.pt"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".download")
        log("model-download", url=MODEL_URL)
        urllib.request.urlretrieve(MODEL_URL, temporary)
        temporary.replace(path)
    return path


def input_hash(census: dict, shot: dict, view: dict, prompts: list[dict], checkpoint_hash: str) -> str:
    code_hash = hashlib.sha256()
    for name in ("source.py", "video.py", "motion.py"):
        code_hash.update((Path(__file__).parent / name).read_bytes())
    value = {"source": census["sourceSha256"], "fps": census["fps"], "shot": shot,
             "view": view, "prompts": prompts, "checkpoint": checkpoint_hash,
             "code": code_hash.hexdigest(), "stride": 2, "scale": 0.5}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def complete(root: Path, fingerprint: str, indices: list[int], keys: list[int]) -> bool:
    try:
        index = json.loads((root / "index.json").read_text())
        if index["inputHash"] != fingerprint or [f["index"] for f in index["frames"]] != indices:
            return False
        if not (root / "motion.json").is_file():
            return False
        return all((root / folder / f"{i}.png").is_file()
                   for folder, values in (("frames", keys), ("masks", indices), ("edges", indices))
                   for i in values)
    except (OSError, KeyError, ValueError):
        return False


def validate_prompts(prompts: list[dict], shot: dict, view: dict) -> None:
    if not prompts:
        raise ValueError(f"Missing SAM2 prompt: {shot['id']}/{view['viewId']}")
    x, y, w, h = view["rectSourcePixels"]
    for prompt in prompts:
        if not shot["start"] <= prompt["t"] < shot["end"]:
            raise ValueError(f"Prompt outside shot time: {prompt}")
        if not prompt.get("points") and not prompt.get("box"):
            raise ValueError(f"Empty prompt: {prompt}")
        for px, py, label in prompt.get("points", []):
            if not x <= px < x+w or not y <= py < y+h or label not in (0, 1):
                raise ValueError(f"Invalid source-space prompt point: {prompt}")
        if "box" in prompt:
            x0, y0, x1, y1 = prompt["box"]
            if not (x <= x0 < x1 <= x+w and y <= y0 < y1 <= y+h):
                raise ValueError(f"Invalid source-space prompt box: {prompt}")


def mask_stats(rows: list[dict]) -> dict:
    coverage = np.array([f["maskCoverage"] for f in rows])
    areas = np.array([f["maskArea"] for f in rows])
    return {"sampledFrames": len(rows), "nonemptyFrames": int(np.count_nonzero(areas)),
            "emptyFrames": int(np.count_nonzero(areas == 0)),
            "maskArea": {"min": int(areas.min()), "median": float(np.median(areas)), "max": int(areas.max())},
            "maskCoverage": {"min": float(coverage.min()), "median": float(np.median(coverage)),
                             "max": float(coverage.max())}}


def run_view(video_id: str, census: dict, shot: dict, view: dict, prompts: list[dict],
             predictor, fingerprint: str) -> dict:
    import torch
    from .motion import MotionEstimator

    started = time.perf_counter()
    fps = Fraction(*census["fps"])
    indices = frame_range(shot, fps, 2)
    keys = key_indices(shot, fps)
    if not indices:
        raise ValueError(f"Shot {shot['id']} has no every-second-frame samples")
    root = data_root() / video_id / shot["id"] / view["viewId"]
    root.mkdir(parents=True, exist_ok=True)
    # An interrupted/re-prompted view must never look complete to a later run.
    (root / "index.json").unlink(missing_ok=True)
    log("view-start", videoId=video_id, shotId=shot["id"], viewId=view["viewId"], samples=len(indices))
    with tempfile.TemporaryDirectory(prefix="sam2-", dir=root) as directory:
        samples = Path(directory)
        position = {index: local for local, index in enumerate(indices)}
        temporal = []
        for index, image in decode_selected(video_path(video_id), sorted(set(indices + keys)), fps):
            if index in keys:
                imwrite(root / "frames" / f"{index}.png", image)
            if index in position:
                crop = crop_half(image, view)
                imwrite(samples / f"{position[index]:06d}.jpg", crop)
                if len(temporal) < 24 and position[index] % max(1, len(indices) // 24) == 0:
                    temporal.append(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32))
        prompt_positions = []
        x, y, w, h = view["rectSourcePixels"]
        width, height = max(1, round(w/2)), max(1, round(h/2))
        scale = np.array([width/w, height/h], dtype=np.float32)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = predictor.init_state(str(samples), offload_video_to_cpu=True, offload_state_to_cpu=True)
            for prompt in prompts:
                local = min(range(len(indices)), key=lambda i: abs(indices[i] / float(fps) - prompt["t"]))
                prompt_positions.append(local)
                points = prompt.get("points", [])
                coordinates = (np.array([p[:2] for p in points], dtype=np.float32) - [x, y]) * scale if points else None
                labels = np.array([p[2] for p in points], dtype=np.int32) if points else None
                box = (np.array(prompt["box"], dtype=np.float32).reshape(2, 2) - [x,y]) * scale if "box" in prompt else None
                predictor.add_new_points_or_box(state, frame_idx=local, obj_id=1, points=coordinates,
                                                labels=labels, box=box.reshape(4) if box is not None else None)
            first_prompt = min(prompt_positions)
            passes = [(first_prompt, False)]
            if first_prompt > 0:
                passes.append((first_prompt, True))
            for start, reverse in passes:
                for local, _, logits in predictor.propagate_in_video(state, start_frame_idx=start, reverse=reverse):
                    mask = (logits[0, 0] > 0).cpu().numpy().astype(np.uint8) * 255
                    imwrite(root / "masks" / f"{indices[local]}.png", mask)
                    if local % 100 == 0:
                        log("view-progress", videoId=video_id, shotId=shot["id"], viewId=view["viewId"],
                            sampledFrame=local, samples=len(indices), seconds=time.perf_counter()-started)
            del state
        gc.collect()
        torch.cuda.empty_cache()
        ref_local = prompt_positions[0]
        ref_index = indices[ref_local]
        reference = cv2.imread(str(samples / f"{ref_local:06d}.jpg"))
        reference_mask = cv2.imread(str(root / "masks" / f"{ref_index}.png"), cv2.IMREAD_GRAYSCALE)
        # Temporal variance excludes crank/rocker motion before matching static source texture.
        deviation = np.std(np.stack(temporal), axis=0) if len(temporal) > 1 else np.zeros((height, width))
        static_mask = ((deviation < 10) & (reference_mask > 0)).astype(np.uint8) * 255
        estimator = MotionEstimator(ref_index, reference, reference_mask, static_mask)
        rows, motion = [], []
        for local, index in enumerate(indices):
            image = cv2.imread(str(samples / f"{local:06d}.jpg"))
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            mask = cv2.imread(str(root / "masks" / f"{index}.png"), cv2.IMREAD_GRAYSCALE)
            support = cv2.dilate(mask, np.ones((5,5), np.uint8))
            edges = cv2.bitwise_and(cv2.Canny(gray, 60, 160), support)
            imwrite(root / "edges" / f"{index}.png", edges)
            area = int(np.count_nonzero(mask))
            laplacian = cv2.Laplacian(gray, cv2.CV_32F)
            sharpness = float(np.var(laplacian[mask > 0])) if area else 0.0
            t = index / float(fps)
            rows.append({"index": index, "t": t, "maskArea": area,
                         "maskCoverage": area / mask.size, "sharpness": sharpness})
            motion.append(estimator.estimate(index, t, image, mask))
    seconds = time.perf_counter() - started
    write_json(root / "motion.json", {"refFrame": ref_index, "space": "view-crop-halfres", "frames": motion})
    result = {"inputHash": fingerprint, "sourceSha256": census["sourceSha256"],
              "videoId": video_id, "shotId": shot["id"], "viewId": view["viewId"],
              "width": width, "height": height, "fps": census["fps"],
              "rectSourcePixels": view["rectSourcePixels"], "cropOriginSourcePixels": [x,y],
              "maskScale": [width/w, height/h], "frames": rows, "stats": mask_stats(rows),
              "timingSeconds": seconds, "model": MODEL}
    write_json(root / "index.json", result)
    log("view-done", videoId=video_id, shotId=shot["id"], viewId=view["viewId"], seconds=seconds, stats=result["stats"])
    return result


def source(video_id: str, shot_id: str | None = None) -> dict:
    os.environ.setdefault("TQDM_DISABLE", "1")
    import torch
    from sam2.build_sam import build_sam2_video_predictor

    started = time.perf_counter()
    census = load_shots(video_id)
    path = video_path(video_id)
    if sha256(path) != census["sourceSha256"]:
        raise ValueError("Video hash changed; re-run shots and inspect prompts against the new video")
    pts = verify_pts(path, Fraction(*census["fps"]))
    shots = selected_shots(census, shot_id)
    all_prompts = json.loads((PROJECT / "videos" / video_id / "prompts.json").read_text())["prompts"]
    jobs = []
    for shot in shots:
        for view in shot["views"]:
            prompts = [p for p in all_prompts if p["shotId"] == shot["id"] and p["viewId"] == view["viewId"]]
            validate_prompts(prompts, shot, view)
            jobs.append((shot, view, prompts))
    checkpoint = model_checkpoint()
    checkpoint_hash = sha256(checkpoint)
    predictor = None
    results = []
    current_shot = None
    shot_started = time.perf_counter()
    shot_timings = []
    for shot, view, prompts in jobs:
        if shot["id"] != current_shot:
            if current_shot is not None:
                seconds = time.perf_counter() - shot_started
                shot_timings.append({"shotId": current_shot, "seconds": seconds})
                log("shot-done", videoId=video_id, shotId=current_shot, seconds=seconds)
            current_shot = shot["id"]
            shot_started = time.perf_counter()
            log("shot-start", videoId=video_id, shotId=current_shot)
        fingerprint = input_hash(census, shot, view, prompts, checkpoint_hash)
        root = data_root() / video_id / shot["id"] / view["viewId"]
        if complete(root, fingerprint, frame_range(shot, Fraction(*census["fps"]), 2), key_indices(shot, Fraction(*census["fps"]))):
            result = json.loads((root / "index.json").read_text())
            results.append({"shotId": shot["id"], "viewId": view["viewId"], "cached": True,
                            "seconds": 0, "stats": result["stats"]})
            log("view-skip", videoId=video_id, shotId=shot["id"], viewId=view["viewId"])
            continue
        if predictor is None:
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is required for this source pipeline")
            torch.set_num_threads(4)
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            predictor = build_sam2_video_predictor(MODEL_CONFIG, str(checkpoint), device="cuda",
                                                  apply_postprocessing=False)
        result = run_view(video_id, census, shot, view, prompts, predictor, fingerprint)
        results.append({"shotId": shot["id"], "viewId": view["viewId"], "cached": False,
                        "seconds": result["timingSeconds"], "stats": result["stats"]})
    if current_shot is not None:
        seconds = time.perf_counter() - shot_started
        shot_timings.append({"shotId": current_shot, "seconds": seconds})
        log("shot-done", videoId=video_id, shotId=current_shot, seconds=seconds)
    summary = {"videoId": video_id, "seconds": time.perf_counter()-started, "pts": pts,
               "shots": shot_timings, "views": results}
    destination = data_root() / video_id / ("source-stats.json" if shot_id is None else f"source-stats-{shot_id}.json")
    write_json(destination, summary)
    make_review(video_id)
    log("video-done", videoId=video_id, seconds=summary["seconds"], views=len(results), report=str(destination))
    return summary


def make_review(video_id: str, overlay: bool = True) -> Path:
    """One tile per shot; each includes every simultaneous view with its own mask."""
    census = load_shots(video_id)
    root = data_root() / video_id
    shots = selected_shots(census, None)
    tile_w, tile_h, columns = 480, 300, 4
    sheet = Image.new("RGB", (columns*tile_w, ((len(shots)+columns-1)//columns)*tile_h), "#161b22")
    draw = ImageDraw.Draw(sheet)
    fps = Fraction(*census["fps"])
    for number, shot in enumerate(shots):
        sx, sy = (number % columns)*tile_w, (number // columns)*tile_h
        draw.text((sx+6,sy+4), shot["id"], fill="white")
        views = shot["views"]
        sub_w = tile_w // max(1, len(views))
        for v, view in enumerate(views):
            directory = root / shot["id"] / view["viewId"]
            frames = sorted((directory / "frames").glob("*.png"), key=lambda p: int(p.stem))
            if not frames:
                continue
            prompt_file = PROJECT / "videos" / video_id / "prompts.json"
            prompts = json.loads(prompt_file.read_text())["prompts"] if prompt_file.exists() else []
            matches = [p for p in prompts if p["shotId"] == shot["id"] and p["viewId"] == view["viewId"]]
            t = matches[0]["t"] if matches else (shot["start"]+shot["end"])/2
            frame = min(frames, key=lambda p: abs(int(p.stem)/float(fps) - t))
            full = cv2.imread(str(frame))
            crop = crop_half(full, view)
            masks = list((directory / "masks").glob("*.png"))
            if overlay and masks:
                mask_path = min(masks, key=lambda p: abs(int(p.stem)-int(frame.stem)))
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                colored = crop.copy()
                colored[mask > 0] = [70,220,80]
                crop = cv2.addWeighted(crop, 0.6, colored, 0.4, 0)
            image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            image.thumbnail((sub_w, tile_h-50))
            sheet.paste(image, (sx+v*sub_w, sy+30))
            draw.text((sx+v*sub_w+3,sy+tile_h-16), view["viewId"], fill="white")
    path = root / ("source-review.png" if overlay else "prompt-review.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path
