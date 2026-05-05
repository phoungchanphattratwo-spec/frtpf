"""
Convert logo/logo.png (the cat logo) to a proper multi-size transparent ICO.
"""
from PIL import Image
import struct, io, os

src = r'C:\Users\KLS COMPUTER\Desktop\FRT\logo\logo.png'
OUT = r'C:\Users\KLS COMPUTER\Desktop\frt_tool_icon.ico'

img = Image.open(src).convert('RGBA')

sizes = [16, 24, 32, 48, 64, 128, 256]
images_data = []
for s in sizes:
    resized = img.resize((s, s), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format='PNG')
    images_data.append(buf.getvalue())

n = len(images_data)
ico = struct.pack('<HHH', 0, 1, n)
offset = 6 + n * 16
entries = b''
for s, data in zip(sizes, images_data):
    w = 0 if s == 256 else s
    h = 0 if s == 256 else s
    entries += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(data), offset)
    offset += len(data)

with open(OUT, 'wb') as f:
    f.write(ico + entries + b''.join(images_data))

print(f'Saved: {OUT}  ({os.path.getsize(OUT):,} bytes)  sizes: {sizes}')
