import os
from PIL import Image, ImageDraw

os.makedirs("extension/icons", exist_ok=True)

def create_icon(size):
    # Create image with dark slate blue background and vibrant gradient cyan accent
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = max(1, size // 10)
    bg_box = [margin, margin, size - margin, size - margin]
    radius = max(2, size // 4)

    # Draw rounded rectangle background
    draw.rounded_rectangle(bg_box, radius=radius, fill=(15, 23, 42, 255), outline=(99, 102, 241, 255), width=max(1, size // 24))

    # Draw document / magnifying glass motif
    center = size / 2
    pad = size / 4

    # Document shape
    doc_left = pad + 1
    doc_top = pad - 1
    doc_right = size - pad - 1
    doc_bottom = size - pad + 3
    draw.rectangle([doc_left, doc_top, doc_right, doc_bottom], fill=(30, 41, 59, 255), outline=(56, 189, 248, 255), width=max(1, size // 20))

    # Lines on document
    line_y1 = doc_top + (doc_bottom - doc_top) * 0.3
    line_y2 = doc_top + (doc_bottom - doc_top) * 0.5
    line_y3 = doc_top + (doc_bottom - doc_top) * 0.7
    
    draw.line([doc_left + 2, line_y1, doc_right - 2, line_y1], fill=(56, 189, 248, 255), width=max(1, size // 20))
    draw.line([doc_left + 2, line_y2, doc_right - 2, line_y2], fill=(99, 102, 241, 255), width=max(1, size // 20))
    draw.line([doc_left + 2, line_y3, doc_right - 4, line_y3], fill=(168, 85, 247, 255), width=max(1, size // 20))

    img.save(f"extension/icons/icon-{size}.png")
    print(f"Generated extension/icons/icon-{size}.png")

for size in [16, 48, 128]:
    create_icon(size)
