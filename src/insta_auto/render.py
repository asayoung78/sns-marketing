"""카드뉴스 템플릿에 문구를 넣어 1080x1350 JPEG 이미지를 만든다.

페이지 종류
- cover   : {"label", "title", "subtitle", "meta": [줄...]}
- text    : {"heading", "body", "number"(선택)}
- list    : {"heading", "items": [줄...]}
- info    : {"heading", "rows": [(항목, 내용), ...]}
- closing : {"title", "lines": [줄...]}
모든 페이지에 "source"(출처 한 줄)와 "image"(로컬 사진 경로)를 선택적으로 넣을 수 있다.
사진이 있으면 표지는 사진 배경, 나머지 페이지는 위쪽에 사진 띠가 들어간다.
"""

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1350
MARGIN = 96
# Ubuntu `fonts-noto-cjk` 패키지. .ttc 안의 1번이 한국어(KR) 글꼴
FONT_DIR = Path("/usr/share/fonts/opentype/noto")
KR_INDEX = 1
PHOTO_H = 540  # 본문 페이지 위쪽 사진 띠 높이
# 카드 글꼴에 없는 이모지·기호(네모로 깨짐)를 지운다
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")


def _clean(text: str) -> str:
    return re.sub(r" {2,}", " ", EMOJI.sub("", text or "")).strip()


def _font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    name = "NotoSansCJK-Bold.ttc" if bold else "NotoSansCJK-Regular.ttc"
    return ImageFont.truetype(str(FONT_DIR / name), size, index=KR_INDEX)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """띄어쓰기 단위로 줄바꿈하고, 한 단어가 너무 길면 글자 단위로 자른다."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ""
            for ch in word:
                if draw.textlength(line + ch, font=font) > max_width:
                    lines.append(line)
                    line = ""
                line += ch
        lines.append(line)
    return lines


def _text_block(draw, xy, text, font, fill, max_width, line_gap=1.45, max_lines=None) -> int:
    x, y = xy
    step = int(font.size * line_gap)
    lines = _wrap(draw, _clean(text), font, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()[:-1] + "…"
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _footer(draw, design, brand, page, total, source, dark=False):
    small = _font(30, True)
    color = design["accent"] if dark else design["primary"]
    draw.text((MARGIN, H - MARGIN - 20), brand, font=small, fill=color)
    label = f"{page} / {total}"
    num_font = _font(30, False)
    draw.text((W - MARGIN - draw.textlength(label, font=num_font), H - MARGIN - 20), label, font=num_font,
              fill="#FFFFFF" if dark else design["text"])
    if source:
        src_font = _font(24, False)
        text = source if source.startswith("사진:") else f"출처: {source}"
        draw.text((MARGIN, H - MARGIN - 70), text, font=src_font, fill="#C9D6E3" if dark else "#7B8794")


def _cover(d, page, design, width):
    d.rectangle([0, 0, W, 24], fill=design["primary"])
    label_font = _font(36, True)
    page["label"] = _clean(page["label"])
    lw = d.textlength(page["label"], font=label_font)
    d.rounded_rectangle([MARGIN, 220, MARGIN + lw + 56, 296], radius=38, fill=design["accent"])
    d.text((MARGIN + 28, 230), page["label"], font=label_font, fill="#FFFFFF")
    y = 340
    if page.get("subtitle"):
        y = _text_block(d, (MARGIN, y), page["subtitle"], _font(42, False), design["text"], width, max_lines=2) + 20
    y = _text_block(d, (MARGIN, y), page["title"], _font(84, True), design["primary"], width, 1.28, max_lines=4)
    d.rectangle([MARGIN, y + 30, MARGIN + 120, y + 40], fill=design["accent"])
    y += 90
    for line in page.get("meta", []):
        y = _text_block(d, (MARGIN, y), line, _font(38, False), design["text"], width, max_lines=2) + 8


def _fit(path: str, w: int, h: int) -> Image.Image:
    """사진을 w×h 안에 잘리지 않게 넣고, 빈 곳은 같은 사진을 흐리게 깔아 채운다(포스터용)."""
    src = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    bg = ImageOps.fit(src, (w, h)).filter(ImageFilter.GaussianBlur(30))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    fg = ImageOps.contain(src, (w, h))
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def _photo_band(img, page) -> int:
    """위쪽에 사진 띠를 넣고 본문 시작 y를 돌려준다. 사진이 없으면 기본 위치."""
    if not page.get("image"):
        return 230
    try:
        img.paste(_fit(page["image"], W, PHOTO_H), (0, 0))
        return PHOTO_H + 70
    except Exception as e:
        print(f"사진 넣기 실패({page['image']}): {e}")
        return 230


def _photo_cover(img, d, page, design, width):
    """사진 표지: 흐린 사진 배경 + 위쪽에 포스터 전체 + 아래 흰 글씨."""
    img.paste(_fit(page["image"], W, H).filter(ImageFilter.GaussianBlur(4)), (0, 0))
    shade = Image.new("RGB", (W, H), "#000000")
    img.paste(Image.blend(img.copy(), shade, 0.35))
    poster = ImageOps.contain(ImageOps.exif_transpose(Image.open(page["image"])).convert("RGB"), (W - 2 * MARGIN, 700))
    img.paste(poster, ((W - poster.width) // 2, 90))
    y = 90 + poster.height + 50
    label_font = _font(32, True)
    label = _clean(page["label"])
    lw = d.textlength(label, font=label_font)
    d.rounded_rectangle([MARGIN, y, MARGIN + lw + 48, y + 64], radius=32, fill=design["accent"])
    d.text((MARGIN + 24, y + 8), label, font=label_font, fill="#FFFFFF")
    y += 90
    if page.get("subtitle"):
        y = _text_block(d, (MARGIN, y), page["subtitle"], _font(36, False), "#E6EEF5", width, max_lines=1) + 6
    y = _text_block(d, (MARGIN, y), page["title"], _font(64, True), "#FFFFFF", width, 1.25, max_lines=2) + 12
    for line in page.get("meta", []):
        y = _text_block(d, (MARGIN, y), line, _font(32, False), "#E6EEF5", width, max_lines=1) + 4


def _heading(d, text, design, width, y=230):
    y = _text_block(d, (MARGIN, y), text, _font(64, True), design["primary"], width, 1.3, max_lines=2)
    d.line([MARGIN, y + 26, W - MARGIN, y + 26], fill=design["primary"], width=3)
    return y + 76


def _text(d, page, design, width, y=230):
    photo = y > 230
    if page.get("number") and not photo:
        d.ellipse([MARGIN, 180, MARGIN + 100, 280], fill=design["accent"])
        nf = _font(44, True)
        num = f"{page['number']:02d}"
        d.text((MARGIN + 50 - d.textlength(num, font=nf) / 2, 200), num, font=nf, fill="#FFFFFF")
        y = 330
    y = _heading(d, page["heading"], design, width, y)
    size = 40 if photo else 44
    _text_block(d, (MARGIN, y), page["body"], _font(size, False), design["text"], width, 1.55, max_lines=5 if photo else 10)


def _list(d, page, design, width, y=230):
    photo = y > 230
    y = _heading(d, page["heading"], design, width, y)
    body = _font(36 if photo else 42, False)
    for item in page["items"]:
        if y > H - 300:  # 아래 출처·쪽번호와 겹치지 않게
            break
        d.ellipse([MARGIN, y + 18, MARGIN + 18, y + 36], fill=design["accent"])
        y = _text_block(d, (MARGIN + 40, y), item, body, design["text"], width - 40, 1.45, max_lines=2 if photo else 3) + 24


def _info(d, page, design, width, y=230):
    photo = y > 230
    y = _heading(d, page["heading"], design, width, y)
    key_font, val_font = _font(34 if photo else 36, True), _font(34 if photo else 36, False)
    key_w = 190
    for key, value in page["rows"]:
        if not value:
            continue
        d.text((MARGIN, y), key, font=key_font, fill=design["primary"])
        y = _text_block(d, (MARGIN + key_w, y), value, val_font, design["text"], width - key_w, 1.45, max_lines=2 if photo else 4) + 18
        if y > H - 260:
            break


def _closing(d, page, design, width):
    y = _text_block(d, (MARGIN, 470), page["title"], _font(72, True), "#FFFFFF", width, 1.35, max_lines=3)
    _text_block(d, (MARGIN, y + 60), "\n".join(page.get("lines", [])), _font(40, False), design["background"], width, 1.6)


DRAW = {"cover": _cover, "text": _text, "list": _list, "info": _info, "closing": _closing}


def render_pages(pages: list[dict], settings: dict, out_dir: Path) -> list[Path]:
    design, brand = settings["design"], settings["account"]["brand"]
    out_dir.mkdir(parents=True, exist_ok=True)
    width = W - MARGIN * 2
    paths = []
    for n, page in enumerate(pages, start=1):
        photo_cover = page["type"] == "cover" and page.get("image")
        dark = page["type"] == "closing" or bool(photo_cover)
        img = Image.new("RGB", (W, H), design["primary"] if dark else design["background"])
        d = ImageDraw.Draw(img)
        if photo_cover:
            _photo_cover(img, d, page, design, width)
        elif page["type"] in ("text", "list", "info"):
            DRAW[page["type"]](d, page, design, width, _photo_band(img, page))
        else:
            DRAW[page["type"]](d, page, design, width)
        _footer(d, design, brand, n, len(pages), page.get("source", ""), dark)
        path = out_dir / f"{n:02d}.jpg"  # Instagram API는 JPEG만 받음
        img.save(path, "JPEG", quality=92)
        paths.append(path)
    return paths
