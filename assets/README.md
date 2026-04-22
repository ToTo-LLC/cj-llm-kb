# brain — launcher icon assets

Committed binaries consumed by the install scripts:

| File | Purpose | Consumed by |
|------|---------|-------------|
| `brain.png` | 1024×1024 master raster (source of truth for all derived formats). | Fallback + future Linux `.desktop` file. |
| `brain.icns` | Multi-resolution macOS icon bundle (16…1024 + @2x). | `scripts/install_lib/make_app_bundle.sh` copies into `~/Applications/brain.app/Contents/Resources/`. |
| `brain.ico` | Multi-resolution Windows icon (16, 32, 48, 256 — PNG-encoded). | `scripts/install_lib/make_start_menu.ps1` references in the Start Menu `.lnk`'s `IconLocation`. |
| `brain-glyph.svg` | Vector source. Edit this, then regenerate the rasters below. | Build-time only; not shipped to users. |

## Source + license

Placeholder glyph designed for Plan 08: a rounded-square tile with the
TomorrowToday orange gradient (`#FDEB9E → #FF6321`, from
`/tmp/brain-design-v3/assets/tt-tokens.css`) and a white lowercase "b"
wordmark. Authored for the `brain` project and licensed under the
repository's root `LICENSE`. Plan 09 will likely replace this with a
brand-designed glyph — if so, drop the new `brain-glyph.svg` in place
and rerun the commands below.

## Regeneration (macOS — the committed bins were made this way)

```bash
cd assets/

# 1. SVG -> 1024×1024 PNG master.
#    qlmanage is built into macOS; rsvg-convert is a fine alternative.
mkdir -p /tmp/brain-glyph-render
qlmanage -t -s 1024 -o /tmp/brain-glyph-render brain-glyph.svg
cp /tmp/brain-glyph-render/brain-glyph.svg.png brain.png

# 2. PNG -> .icns via iconutil (macOS-native, no external deps).
rm -rf brain.iconset && mkdir brain.iconset
sips -z 16   16   brain.png --out brain.iconset/icon_16x16.png     > /dev/null
sips -z 32   32   brain.png --out brain.iconset/icon_16x16@2x.png  > /dev/null
sips -z 32   32   brain.png --out brain.iconset/icon_32x32.png     > /dev/null
sips -z 64   64   brain.png --out brain.iconset/icon_32x32@2x.png  > /dev/null
sips -z 128  128  brain.png --out brain.iconset/icon_128x128.png   > /dev/null
sips -z 256  256  brain.png --out brain.iconset/icon_128x128@2x.png > /dev/null
sips -z 256  256  brain.png --out brain.iconset/icon_256x256.png   > /dev/null
sips -z 512  512  brain.png --out brain.iconset/icon_256x256@2x.png > /dev/null
sips -z 512  512  brain.png --out brain.iconset/icon_512x512.png   > /dev/null
sips -z 1024 1024 brain.png --out brain.iconset/icon_512x512@2x.png > /dev/null
iconutil -c icns brain.iconset -o brain.icns
rm -rf brain.iconset    # transient — don't commit

# 3. PNG -> multi-resolution .ico.
#    No ImageMagick / Pillow available here, so a stdlib Python packer is
#    kept alongside this README. ICO embeds each size as its own PNG blob
#    (Vista+ supports this — simpler + lossless vs. legacy BMP entries).
python3 pack_ico.py brain.ico 16 32 48 256
```

## Regeneration on Linux (alternative)

```bash
# Prereq: librsvg2-bin (rsvg-convert) + ImageMagick ('magick' or 'convert').
rsvg-convert -w 1024 -h 1024 brain-glyph.svg -o brain.png

# .ico (multi-resolution):
magick convert brain.png -define icon:auto-resize=16,32,48,256 brain.ico
# or:
convert brain.png -define icon:auto-resize=16,32,48,256 brain.ico

# .icns (without iconutil):
# png2icns (libicns) works: png2icns brain.icns 1024.png 512.png 256.png ...
# or use ImageMagick: magick brain.png brain.icns
```

## Why these formats

- **`.icns` (Mac):** Finder / Launchpad / Dock all read this. Multi-
  resolution variants (normal + @2x) avoid blurry upscales.
- **`.ico` (Windows):** Start Menu `.lnk` files, Explorer, Taskbar all
  honor the `IconLocation` field. Multi-resolution keeps the 16-px tray
  view crisp AND the 256-px settings panel tidy.
- **`.png`:** generic fallback — used for Linux `.desktop` files + any
  future cross-platform surface (e.g. a setup wizard favicon).

## Install script integration

The install scripts assume these three binaries live at
`<install_dir>/assets/`. They skip the icon step silently if the file is
missing (Task 7/8 codepath), which means a partial ship or a broken
raster just gives the user the default OS icon — never an install
failure. Keep it that way.

- macOS: `scripts/install_lib/make_app_bundle.sh` copies `brain.icns`
  into the `.app` bundle's Resources folder. The bundle's `Info.plist`
  references `CFBundleIconFile = brain` (no extension — macOS
  convention).
- Windows: `scripts/install_lib/make_start_menu.ps1` sets the shortcut's
  `IconLocation` to `<install_dir>\assets\brain.ico`.
