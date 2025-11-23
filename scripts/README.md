# Banner Bridge Generator - Pixel-Perfect Edition

This script generates a pixel-perfect bridge image that seamlessly transitions between the banner images used in the header, preserving vertical color variation.

## How It Works

1. **Extracts Edge Columns**: Extracts the entire rightmost column of pixels from `banner_left_DungeonDelver.png` and the entire leftmost column from `banner_right_DungeonDelver.png`

2. **Handles Transparency**: Composites any transparent pixels onto the dark background color (#080B10) to get the true visible colors

3. **Generates Bridge Image**: Creates a 100px wide PNG image that smoothly interpolates horizontally between the two edge columns, preserving vertical color variation row-by-row for pixel-perfect transitions

## Usage

Run the script from the project root:

```bash
python scripts/generate_banner_gradient.py
```

The script will output:
- The exact edge colors it detected
- CSS gradient code to copy
- CSS variable values to update in `static/css/style.css`

## When to Re-run

Re-run this script whenever you:
- Change the banner images
- Update the banner artwork
- Want to verify the gradient matches the images

## Manual Steps After Running

1. Run the script - it will generate `static/images/ui/banner_bridge.png`
2. Update the CSS variables in `static/css/style.css` (if values changed):
   ```css
   :root {
       --header-left: #[value from script];
       --header-right: #[value from script];
   }
   ```
3. Update the header background in `static/css/style.css`:
   ```css
   .header {
       background: url('/static/images/ui/banner_bridge.png');
       background-size: 100% 100%;
       background-position: center;
       background-repeat: no-repeat;
       /* ... other properties ... */
   }
   ```
4. Update the cache-busting parameter in `static/html/game.html`:
   ```html
   <link rel="stylesheet" href="/static/css/style.css?v=[new-version]">
   ```
5. Restart the server and hard refresh your browser

## Technical Details

- **Bridge Width**: 100px wide, stretched to fill header width in CSS
- **Height**: Matches the taller of the two banner images (1024px)
- **Interpolation**: Linear interpolation between edge colors for each pixel row
- **Transparency**: Uses alpha blending with background color #080B10
- **Display**: Single instance stretched with `background-size: 100% 100%`
- **Output**: PNG image that provides seamless pixel-perfect transition
- **Dependencies**: Requires Pillow (PIL) - install with `pip install Pillow`
