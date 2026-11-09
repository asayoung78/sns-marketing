"""카드뉴스 템플릿에 문구를 넣어 1080x1350 JPEG 이미지를 만든다."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
MARGIN = 96
# Ubuntu `fonts-noto-cjk` 패키지. .ttc 안의 1번이 한국어(KR) 글꼴
FONT_DIR = Path("/usr/share/fonts/opentype/noto")
KR_INDEX = 1


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


def _text_block(draw, xy, text, font, fill, max_width, line_gap=1.45) -> int:
    x, y = xy
    step = int(font.size * line_gap)
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _base(design: dict) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), design["background"])
    return img, ImageDraw.Draw(img)


def _footer(draw, design, handle, page, total):
    small = _font(30, False)
    draw.text((MARGIN, H - MARGIN - 20), handle, font=small, fill=design["primary"])
    label = f"{page} / {total}"
    draw.text((W - MARGIN - draw.textlength(label, font=small), H - MARGIN - 20), label, font=small, fill=design["text"])


def render_cards(post: dict, settings: dict, out_dir: Path) -> list[Path]:
    design, handle = settings["design"], settings["account"]["handle"]
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(post["slides"]) + 2
    width = W - MARGIN * 2
    pages = []

    # 1. 표지
    img, d = _base(design)
    d.rectangle([0, 0, W, 24], fill=design["primary"])
    label_font = _font(36, True)
    lw = d.textlength(post["cover_label"], font=label_font)
    d.rounded_rectangle([MARGIN, 260, MARGIN + lw + 56, 336], radius=38, fill=design["accent"])
    d.text((MARGIN + 28, 270), post["cover_label"], font=label_font, fill="#FFFFFF")
    y = _text_block(d, (MARGIN, 400), post["cover_title"], _font(92, True), design["primary"], width, 1.3)
    d.rectangle([MARGIN, y + 30, MARGIN + 120, y + 40], fill=design["accent"])
    _text_block(d, (MARGIN, y + 80), post["cover_subtitle"], _font(44, False), design["text"], width)
    _footer(d, design, handle, 1, total)
    pages.append(img)

    # 2. 본문 카드
    for i, slide in enumerate(post["slides"], start=1):
        img, d = _base(design)
        d.ellipse([MARGIN, 200, MARGIN + 110, 310], fill=design["accent"])
        num = f"{i:02d}"
        nf = _font(48, True)
        d.text((MARGIN + 55 - d.textlength(num, font=nf) / 2, 222), num, font=nf, fill="#FFFFFF")
        y = _text_block(d, (MARGIN, 380), slide["heading"], _font(68, True), design["primary"], width, 1.3)
        d.line([MARGIN, y + 30, W - MARGIN, y + 30], fill=design["primary"], width=3)
        _text_block(d, (MARGIN, y + 80), slide["body"], _font(44, False), design["text"], width, 1.6)
        _footer(d, design, handle, i + 1, total)
        pages.append(img)

    # 3. 마무리 카드
    img = Image.new("RGB", (W, H), design["primary"])
    d = ImageDraw.Draw(img)
    y = _text_block(d, (MARGIN, 470), post["closing"], _font(72, True), "#FFFFFF", width, 1.35)
    _text_block(d, (MARGIN, y + 60), "저장해 두고 필요할 때 꺼내 보세요\n도움이 됐다면 팔로우 부탁드려요", _font(40, False), design["background"], width, 1.6)
    small = _font(34, True)
    d.text((MARGIN, H - MARGIN - 30), handle, font=small, fill=design["accent"])
    pages.append(img)

    paths = []
    for n, page in enumerate(pages, start=1):
        path = out_dir / f"{n:02d}.jpg"  # Instagram API는 JPEG만 받음
        page.save(path, "JPEG", quality=92)
        paths.append(path)
    return paths
