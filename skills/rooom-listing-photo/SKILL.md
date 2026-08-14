---
name: rooom-listing-photo
description: Select, deduplicate, enhance, and export property photos from a Google Drive folder for Airbnb, Booking.com, スペースマーケット, and インスタベース while preserving the originals.
---

# Rooom Listing Photo Skill

Use this skill when the user provides a Google Drive folder containing property, rental-space, hotel, or vacation-rental photos and wants a curated listing-ready photo set.

## Goal

Turn a source Google Drive photo folder into a separate listing-ready output folder without modifying, moving, renaming, or deleting any original photo.

## Required behavior

1. Accept a Google Drive folder URL or folder ID.
2. Enumerate JPEG, PNG, and WebP images directly inside the folder.
3. Analyze every photo before editing it.
4. Reject obvious junk and low-value images before enhancement:
   - near-duplicates and burst shots
   - severe blur
   - extreme underexposure or blown highlights
   - screenshots and mostly-text documents
   - QR-code or promotional/contact graphics
   - low-resolution images
5. Categorize usable images into living room, bedroom, kitchen, bathroom, toilet, entrance, exterior, workspace, amenities, view, and floor plan.
6. Select a balanced set. Do not simply take the highest numeric scores if that would leave important rooms or facilities undocumented.
7. Prefer landscape images for listing platforms.
8. Keep only the strongest image from a group of very similar compositions unless a second composition communicates genuinely different information.
9. Enhance only selected images. Do not spend processing time on rejected images.
10. Limit editing to truthful photographic correction:
    - EXIF orientation
    - white balance
    - exposure
    - local contrast
    - light sharpening
    - resizing and geometric cropping
11. Never add furniture, widen a room, replace windows/views, synthesize amenities, remove permanent defects, or otherwise make the property materially different from reality.
12. Create a new output folder under the source folder. Never overwrite originals.
13. Create platform subfolders:
    - 共通_マスター
    - Airbnb
    - Booking
    - スペースマーケット
    - インスタベース
14. For Airbnb, prioritize landscape photos and output at least 1024 x 683; the default preset is 2048 x 1365.
15. For Booking.com, ensure unique images and valid JPEG output; avoid uploading duplicates.
16. For インスタベース, use 1570 x 880 as the default output size and target at least 15 useful images when the source material supports it.
17. Do not export bedroom/bed images to インスタベース when they present the space as overnight lodging.
18. Save 選定レポート.csv and 選定レポート.json with the selection/rejection reason for every source image.

## Preferred execution

Run:

```bash
rooomphotos drive "<GOOGLE_DRIVE_FOLDER_URL>"
```

For review-only selection:

```bash
rooomphotos drive "<GOOGLE_DRIVE_FOLDER_URL>" --dry-run
```

If the user specifies a minimum or maximum photo count, pass `--min-selected` and `--max-selected`.

## Decision rules

A photo should be selected because it either:

- clearly explains an important space or amenity,
- is a strong hero/cover candidate,
- adds a meaningfully different viewpoint,
- prevents a material guest question about layout, access, sleeping, cooking, bathing, work, equipment, exterior, or surroundings.

A photo should not be selected merely because it is technically sharp if it adds no new information.

## Safety of originals

The source folder is read-only from the workflow's perspective. All generated assets go to the newly created output folder. If an output run fails partway through, leave all source files unchanged and report the incomplete output folder rather than attempting destructive rollback on the source.
