"""릴스 영상(1080x1920, 30fps)을 만든다.

- 영상 모드: 직접 찍은 영상을 세로로 맞춰 자르고 길이를 제한
- 사진 슬라이드 모드: 사진마다 천천히 확대되는 효과(켄 번즈)로 이어 붙임
두 모드 모두 위에 같은 글자층(PNG)을 얹는다: 상단 'ON NOW · 분류' 배지, 첫 3초 큰 제목, 이후 자막 차례로.
소리: 직접 찍은 영상의 현장음 + 드라이브 '음악' 폴더의 배경음악
"""

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps

from . import render
from .render import _black, _clean, _category_color, _font, _wrap

W, H, FPS = 1080, 1920, 30
HEAD_SECONDS = 3.0
# 인스타 릴스 화면에서 위쪽 제목줄·아래쪽 계정/본문·오른쪽 버튼에 가리지 않는 영역
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 200, 1500, 70, 940


def _run(cmd: list[str]):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"ffmpeg 실패: {' '.join(cmd[:3])}…\n{proc.stderr[-1500:]}")
    return proc.stdout


def probe(path: Path) -> dict:
    info = json.loads(_run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]))
    return {"duration": float(info["format"].get("duration", 0)),
            "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


# ---------------- 글자층 ----------------
def _layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _shade(img: Image.Image, top: int, bottom: int, start: float, end: float):
    """top~bottom 구간을 반투명 검정으로 점점 덮는다(글자 잘 보이게)."""
    h = bottom - top
    grad = Image.linear_gradient("L").resize((W, h)).point(lambda v: int(255 * (start + (end - start) * v / 255)))
    black = Image.new("RGBA", (W, h), (0, 0, 0, 255))
    black.putalpha(grad)
    img.alpha_composite(black, (0, top))


def _top_layer(label: str, design: dict) -> Image.Image:
    img, d = _layer()
    _shade(img, 0, 420, 0.55, 0.0)
    color = _category_color(design, label)
    tag_font = _black(40)
    tag = f"{design.get('cover_tag', 'ON NOW')} · "
    d.text((SAFE_LEFT, SAFE_TOP), tag, font=tag_font, fill="#FFFFFF")
    d.text((SAFE_LEFT + d.textlength(tag, font=tag_font), SAFE_TOP), _clean(label), font=tag_font, fill=color)
    badge = design.get("cover_badge", "")
    if badge:
        bf = _font(26, True)
        bw = d.textlength(badge, font=bf)
        x1 = SAFE_RIGHT
        d.rounded_rectangle([x1 - bw - 40, SAFE_TOP + 2, x1, SAFE_TOP + 54], radius=26, fill=design.get("badge_color", "#0B2A5B"))
        d.text((x1 - bw - 20, SAFE_TOP + 10), badge, font=bf, fill="#FFFFFF")
    return img


def _head_layer(line1: str, line2: str, info: str, label: str, design: dict) -> Image.Image:
    img, d = _layer()
    _shade(img, int(H * 0.45), H, 0.0, 0.85)
    lines = [l for l in (_clean(line1), _clean(line2)) if l]
    if not lines:
        return img
    size = 140
    while size > 80 and max(d.textlength(l, font=_black(size)) for l in lines) > SAFE_RIGHT - SAFE_LEFT:
        size -= 4
    hf, step = _black(size), int(size * 1.12)
    y = SAFE_BOTTOM - step * len(lines)
    if info:
        d.text((SAFE_LEFT + 4, y - 64), _clean(info), font=_font(38, True), fill="#FFFFFF", stroke_width=2, stroke_fill="#000000")
    color = _category_color(design, label)
    for i, line in enumerate(lines):
        fill = color if i == len(lines) - 1 and len(lines) > 1 else "#FFFFFF"
        d.text((SAFE_LEFT, y), line, font=hf, fill=fill, stroke_width=5, stroke_fill="#111111")
        y += step
    return img


def _sub_layer(text: str) -> Image.Image:
    img, d = _layer()
    _shade(img, 1050, H, 0.0, 0.6)
    font = _black(66)
    lines = _wrap(d, _clean(text), font, SAFE_RIGHT - SAFE_LEFT)[:2]
    y = 1330 - (len(lines) - 1) * 84
    for line in lines:
        x = (SAFE_LEFT + SAFE_RIGHT - d.textlength(line, font=font)) / 2
        d.text((x, y), line, font=font, fill="#FFFFFF", stroke_width=6, stroke_fill="#000000")
        y += 84
    return img


# ---------------- 바탕 영상 ----------------
def _base_from_video(src: Path, out: Path, seconds: float):
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", f"{seconds:.2f}", "-an",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)])


def _fit_tall(path: Path) -> Image.Image:
    """사진을 세로 화면보다 10% 크게, 잘리지 않게 넣고 빈 곳은 흐린 같은 사진으로 채운다."""
    w, h = int(W * 1.1), int(H * 1.1)
    src = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    bg = ImageEnhance.Brightness(ImageOps.fit(src, (w, h)).filter(ImageFilter.GaussianBlur(40))).enhance(0.5)
    fg = ImageOps.contain(src, (w, h))
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def _base_from_images(images: list[Path], out: Path, seconds: float):
    per = seconds / len(images)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    total = int(seconds * FPS)
    for i, path in enumerate(images):
        big = _fit_tall(path)
        frames = int(per * FPS) if i < len(images) - 1 else total - int(per * FPS) * (len(images) - 1)
        zoom_in = i % 2 == 0  # 사진마다 확대·축소를 번갈아
        for f in range(frames):
            t = f / max(frames - 1, 1)
            scale = 1.0 + 0.1 * (t if zoom_in else 1 - t)  # 1.0~1.1배
            cw, ch = big.width / scale, big.height / scale
            left, top = (big.width - cw) / 2, (big.height - ch) / 2
            frame = big.resize((W, H), Image.BILINEAR, box=(left, top, left + cw, top + ch))
            proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f"슬라이드 영상 만들기 실패: {proc.stderr.read().decode()[-800:]}")


# ---------------- 합치기 ----------------
def render_reel(out_dir: Path, *, label: str, headline1: str, headline2: str, info: str, subtitles: list[str],
                settings: dict, video: Path | None = None, images: list[Path] = (), music: Path | None = None) -> tuple[Path, Path]:
    """릴스 mp4와 표지(첫 화면) jpg 경로를 돌려준다."""
    cfg, design = settings["reels"], settings["design"]
    render.HEADLINE_FONT = design.get("headline_font", "")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / "base.mp4"
    has_audio = False
    if video:
        meta = probe(video)
        seconds = max(5.0, min(meta["duration"], cfg["max_video_seconds"]))
        has_audio = meta["has_audio"]
        _base_from_video(video, base, seconds)
    else:
        if not images:
            raise RuntimeError("릴스를 만들 영상이나 사진이 없습니다.")
        seconds = float(cfg["slide_seconds"])
        _base_from_images(list(images)[:8], base, seconds)

    # 글자층: 상단(전체), 큰 제목(처음 3초), 자막(나머지 시간을 나눠서)
    layers = [(_top_layer(label, design), 0, seconds), (_head_layer(headline1, headline2, info, label, design), 0, HEAD_SECONDS)]
    subs = [s for s in (_clean(s) for s in subtitles) if s]
    if subs:
        span = (seconds - HEAD_SECONDS - 0.2) / len(subs)
        layers += [(_sub_layer(s), HEAD_SECONDS + i * span, HEAD_SECONDS + (i + 1) * span) for i, s in enumerate(subs)]
    pngs = []
    for i, (img, start, end) in enumerate(layers):
        p = out_dir / f"layer{i}.png"
        img.save(p)
        pngs.append((p, start, end))

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(base)]
    for p, _, _ in pngs:
        cmd += ["-loop", "1", "-t", f"{seconds:.2f}", "-i", str(p)]
    audio_inputs = []
    if video and has_audio:
        cmd += ["-i", str(video)]
        audio_inputs.append(("orig", len(pngs) + 1))
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        audio_inputs.append(("music", len(pngs) + 1 + len([a for a in audio_inputs if a[0] == "orig"])))

    chain, last = [], "[0:v]"
    for i, (_, start, end) in enumerate(pngs, start=1):
        tag = f"[v{i}]"
        chain.append(f"{last}[{i}:v]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'{tag}")
        last = tag
    fade = max(seconds - 1.5, 0)
    mixes = []
    for kind, idx in audio_inputs:
        vol = (0.35 if any(k == "orig" for k, _ in audio_inputs) else 0.8) if kind == "music" else 0.9
        chain.append(f"[{idx}:a]atrim=0:{seconds:.2f},asetpts=PTS-STARTPTS,volume={vol},"
                     f"afade=t=in:d=0.5,afade=t=out:st={fade:.2f}:d=1.5,aresample=44100[a_{kind}]")
        mixes.append(f"[a_{kind}]")
    if len(mixes) == 2:
        chain.append(f"{''.join(mixes)}amix=inputs=2:duration=first:normalize=0[aout]")
        audio_map = "[aout]"
    elif mixes:
        audio_map = mixes[0]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        audio_map = f"{len(pngs) + 1}:a"
    final = out_dir / "reel.mp4"
    cmd += ["-filter_complex", ";".join(chain), "-map", last, "-map", audio_map, "-t", f"{seconds:.2f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(final)]
    _run(cmd)
    cover = out_dir / "cover.jpg"
    _run(["ffmpeg", "-y", "-v", "error", "-ss", "1.2", "-i", str(final), "-frames:v", "1", "-q:v", "3", str(cover)])
    return final, cover
