"""LocalOps AI — Architecture Pipeline GIF Generator.

Generates a high-impact, professional animated GIF from the static
architecture pipeline image (02_architecture_pipeline.jpg).

Features:
- Sequential stage illumination and glowing card borders with authentic theme colors
- Streaming data packets flowing across the inter-stage data buses
- Grounding Sanitizer filtering effect (clean signals forward, rejected signals down)
- Severity Policy Engine and JSON output pulsation
- Synchronized full-system convergence loop
"""

from __future__ import annotations

import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_IMAGE_PATH = PROJECT_ROOT / "assets" / "linkedin_pack" / "02_architecture_pipeline.jpg"
OUTPUT_GIF_PATH = PROJECT_ROOT / "assets" / "linkedin_pack" / "02_architecture_pipeline.gif"


# Stage bounding boxes: (x1, y1, x2, y2)
STAGES = [
    {
        "id": 1,
        "name": "Telemetry",
        "box": (22, 138, 332, 675),
        "color": (16, 215, 140),   # Emerald / Mint Green
        "bus_y": 500,
        "next_x": 348,
    },
    {
        "id": 2,
        "name": "SLM",
        "box": (348, 138, 592, 675),
        "color": (6, 214, 255),    # Vibrant Neon Cyan
        "bus_y": 500,
        "next_x": 608,
    },
    {
        "id": 3,
        "name": "Sanitizer",
        "box": (608, 138, 826, 675),
        "color": (56, 145, 255),   # Electric Sky Blue
        "bus_y": 500,
        "next_x": 840,
    },
    {
        "id": 4,
        "name": "Policy",
        "box": (840, 138, 1052, 675),
        "color": (180, 95, 255),   # Vivid Purple / Violet
        "bus_y": 500,
        "next_x": 1068,
    },
    {
        "id": 5,
        "name": "JSON_RCA",
        "box": (1068, 138, 1354, 675),
        "color": (245, 75, 170),   # Neon Fuchsia / Pink
        "bus_y": 500,
        "next_x": 1360,
    },
]


def draw_glow_rect(draw: ImageDraw.ImageDraw, box: tuple, color: tuple, width: int = 3, alpha: int = 255):
    """Draws a rounded glowing rectangle border."""
    x1, y1, x2, y2 = box
    r, g, b = color
    # Multi-layer border for soft neon glow
    for offset, a_mult in [(3, 0.25), (2, 0.45), (1, 0.75), (0, 1.0)]:
        eff_color = (r, g, b, int(alpha * a_mult))
        draw.rounded_rectangle(
            [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
            radius=12,
            outline=eff_color,
            width=width,
        )


def draw_data_packet(overlay: Image.Image, x: float, y: float, color: tuple, size: int = 6, tail_len: int = 14):
    """Draws a glowing data packet with a motion trail."""
    draw = ImageDraw.Draw(overlay, "RGBA")
    r, g, b = color

    # Motion trail
    for i in range(tail_len):
        fade = 1.0 - (i / tail_len)
        tx = x - (i * 2.0)
        t_radius = size * (0.8 - (i * 0.04))
        if t_radius > 1:
            draw.ellipse(
                [tx - t_radius, y - t_radius, tx + t_radius, y + t_radius],
                fill=(r, g, b, int(160 * fade * fade)),
            )

    # Core packet halo
    draw.ellipse([x - size * 1.8, y - size * 1.8, x + size * 1.8, y + size * 1.8], fill=(r, g, b, 70))
    draw.ellipse([x - size * 1.2, y - size * 1.2, x + size * 1.2, y + size * 1.2], fill=(r, g, b, 160))
    # Bright center
    draw.ellipse([x - size * 0.6, y - size * 0.6, x + size * 0.6, y + size * 0.6], fill=(255, 255, 255, 240))


def generate_frames() -> list[Image.Image]:
    base_img = Image.open(INPUT_IMAGE_PATH).convert("RGBA")
    w, h = base_img.size

    num_frames = 36
    frames = []

    for f in range(num_frames):
        # Progress parameter 0.0 -> 1.0
        t = f / num_frames

        # Create overlay layer for additive graphics
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")

        # Cycle active stages across the frames
        # Stages 1 to 5 map to progress chunks
        # f in [0..6]   -> Stage 1 active
        # f in [7..13]  -> Stage 2 active
        # f in [14..20] -> Stage 3 active
        # f in [21..27] -> Stage 4 active
        # f in [28..31] -> Stage 5 active
        # f in [32..35] -> All stages pulse together (Convergence)

        is_convergence = (f >= 32)
        if not is_convergence:
            active_idx = min(int(f / 6.4), 4)
        else:
            active_idx = -1  # all active

        # 1. Draw glowing borders & highlights for stages
        for idx, stage in enumerate(STAGES):
            box = stage["box"]
            color = stage["color"]

            if is_convergence:
                # Pulsing all together
                pulse_phase = math.sin((f - 32) / 4.0 * math.pi)
                alpha = int(180 + 75 * pulse_phase)
                draw_glow_rect(draw, box, color, width=3, alpha=alpha)

                # Header glow
                hx1, hy1, hx2, hy2 = box[0], box[1], box[2], box[1] + 55
                draw.rounded_rectangle([hx1, hy1, hx2, hy2], radius=10, fill=(color[0], color[1], color[2], 28))

            elif idx == active_idx:
                # Primary active stage
                stage_frame = f - (idx * 6.4)
                pulse = math.sin(stage_frame * 0.5)
                alpha = int(210 + 45 * pulse)
                draw_glow_rect(draw, box, color, width=4, alpha=alpha)

                # Subtle translucent internal illumination
                draw.rounded_rectangle(box, radius=12, fill=(color[0], color[1], color[2], 22))

                # Header energetic pulse
                hx1, hy1, hx2, hy2 = box[0], box[1], box[2], box[1] + 55
                draw.rounded_rectangle([hx1, hy1, hx2, hy2], radius=10, fill=(color[0], color[1], color[2], 42))

                # Glowing status indicator pill at top right of card
                pill_x = box[2] - 22
                pill_y = box[1] + 28
                draw.ellipse([pill_x - 5, pill_y - 5, pill_x + 5, pill_y + 5], fill=(255, 255, 255, 250))
                draw.ellipse([pill_x - 9, pill_y - 9, pill_x + 9, pill_y + 9], fill=(color[0], color[1], color[2], 140))

            elif idx < active_idx:
                # Upstream stages stay subtly illuminated
                draw_glow_rect(draw, box, color, width=2, alpha=110)

        # 2. Draw animated data packets streaming along the buses
        # Main inter-stage pipeline packets:
        # Map progress to continuous coordinates along horizontal axis
        bus_y = 500
        top_arrow_y = 196

        # Continuous beam progress from x=60 to x=1320
        beam_x = 60 + ((f % num_frames) / num_frames) * 1260

        # Draw a cluster of 3 data packets traveling forward
        for offset_x, p_size, p_color in [
            (0, 5, (255, 255, 255)),
            (-35, 4, (6, 214, 255)),
            (-70, 3, (180, 95, 255)),
        ]:
            px = (beam_x + offset_x)
            if 60 <= px <= 1320:
                # Packet along middle data bus
                draw_data_packet(overlay, px, bus_y, p_color, size=p_size, tail_len=16)
                # Second packet along top header bus
                draw_data_packet(overlay, px, top_arrow_y, p_color, size=p_size * 0.8, tail_len=12)

        # 3. Grounding Sanitizer Filter Animation (at Stage 3: x between 608 and 826)
        # When packets pass through Stage 3, filter drops rejected particles downward
        if 13 <= f <= 24:
            s3_frame = f - 13
            # Filter drop animation toward the red trash/rejected icon at bottom of Stage 3
            # Red rejection bin is around (716, 670)
            for drop_i in range(3):
                drop_y = 520 + ((s3_frame * 14 + drop_i * 25) % 130)
                drop_x = 690 + math.sin(drop_y * 0.1) * 12
                # Crimson glowing reject particle
                draw.ellipse([drop_x - 3, drop_y - 3, drop_x + 3, drop_y + 3], fill=(239, 68, 68, 220))
                draw.ellipse([drop_x - 6, drop_y - 6, drop_x + 6, drop_y + 6], fill=(239, 68, 68, 90))

        # 4. JSON RCA Output Emission (at Stage 5: x between 1068 and 1354)
        # Emits pulse outward to FastAPI and SRE dashboard arrows
        if 26 <= f <= 35:
            s5_frame = f - 26
            emission_r = (s5_frame * 8) % 60
            json_center = (1210, 500)
            draw.ellipse(
                [json_center[0] - emission_r, json_center[1] - emission_r, json_center[0] + emission_r, json_center[1] + emission_r],
                outline=(245, 75, 170, max(0, 200 - emission_r * 3)),
                width=2,
            )

        # 5. Composite Base Image with Additive Overlay
        frame = Image.alpha_composite(base_img, overlay)

        # Resize for optimal LinkedIn bandwidth and crisp display (1024px width)
        target_w = 1024
        target_h = int(h * (target_w / w))
        frame_resized = frame.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Convert to RGB with slight contrast boost for LinkedIn dark mode pop
        enhancer = ImageEnhance.Contrast(frame_resized.convert("RGB"))
        enhanced_frame = enhancer.enhance(1.05)

        # Convert to P mode with adaptive palette for crisp, artifact-free GIF rendering
        p_frame = enhanced_frame.convert("P", palette=Image.ADAPTIVE, colors=216)
        frames.append(p_frame)

    return frames


def main():
    print(f"Loading input: {INPUT_IMAGE_PATH}...")
    frames = generate_frames()
    print(f"Generated {len(frames)} animated frames.")

    print(f"Saving optimized GIF to {OUTPUT_GIF_PATH}...")
    frames[0].save(
        OUTPUT_GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        optimize=True,
        duration=80,    # 80ms per frame = 12.5 fps (smooth ~2.9s loop)
        loop=0,         # Infinite loop
    )

    gif_size_mb = OUTPUT_GIF_PATH.stat().st_size / (1024 * 1024)
    print(f"[OK] Animated GIF successfully created!")
    print(f"  Path: {OUTPUT_GIF_PATH}")
    print(f"  Size: {gif_size_mb:.2f} MB")


if __name__ == "__main__":
    main()
