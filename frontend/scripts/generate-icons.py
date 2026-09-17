from PIL import Image
import os

src = Image.open(r"D:\Vs Code\VS code\Vault\Group 53.png").convert("RGBA")
out = r"D:\Vs Code\VS code\Vault\frontend\public"
os.makedirs(out, exist_ok=True)

# Generate all sizes
ico_sizes = [(16, 16), (32, 32), (48, 48)]
ico_images = [src.resize(s, Image.LANCZOS) for s in ico_sizes]
ico_images[0].save(os.path.join(out, "favicon.ico"), format="ICO", sizes=ico_sizes, append_images=ico_images[1:])
print("favicon.ico")

png_sizes = [72, 96, 128, 144, 150, 152, 180, 192, 310, 384, 512]
for s in png_sizes:
    resized = src.resize((s, s), Image.LANCZOS)
    name = f"icon-{s}.png" if s not in [180] else "apple-touch-icon.png"
    if s == 180:
        name = "apple-touch-icon.png"
    elif s == 150:
        resized.save(os.path.join(out, "mstile-150x150.png"), "PNG")
        name = f"icon-{s}.png"
    elif s == 310:
        resized.save(os.path.join(out, "mstile-310x310.png"), "PNG")
        name = f"icon-{s}.png"
    resized.save(os.path.join(out, name), "PNG")
    print(name)

# OG image (1200x630) - centered on dark bg
og = Image.new("RGBA", (1200, 630), (1, 1, 2, 255))
icon_512 = src.resize((400, 400), Image.LANCZOS)
og.paste(icon_512, ((1200 - 400) // 2, (630 - 400) // 2), icon_512)
og.save(os.path.join(out, "og-image.png"), "PNG")
print("og-image.png")

print("All icons generated")
