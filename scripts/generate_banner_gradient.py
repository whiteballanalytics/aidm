#!/usr/bin/env python3
"""
Banner Gradient Generator - Pixel-Perfect Edition

This script extracts edge pixel colors from banner images and generates
a seamless bridge image that transitions between them with perfect vertical fidelity.

Usage:
    python scripts/generate_banner_gradient.py

Output:
    - Creates static/images/ui/banner_bridge.png (thin gradient image)
    - Prints CSS code to use the bridge image in the header
"""

from PIL import Image
import os

# Configuration
LEFT_BANNER_PATH = "static/images/ui/banner_left_DungeonDelver.png"
RIGHT_BANNER_PATH = "static/images/ui/banner_right_DungeonDelver.png"
OUTPUT_BRIDGE_PATH = "static/images/ui/banner_bridge.png"
BACKGROUND_COLOR = (8, 11, 16)  # #080B10 - dark background for transparency compositing
BRIDGE_WIDTH = 100  # Width of the transition bridge in pixels


def composite_on_background(rgba_tuple, bg_color):
    """Composite RGBA color on background color, handling transparency."""
    r, g, b, a = rgba_tuple
    alpha = a / 255.0
    
    # Alpha blend with background
    final_r = int(r * alpha + bg_color[0] * (1 - alpha))
    final_g = int(g * alpha + bg_color[1] * (1 - alpha))
    final_b = int(b * alpha + bg_color[2] * (1 - alpha))
    
    return (final_r, final_g, final_b)


def interpolate_color(color1, color2, ratio):
    """Linearly interpolate between two RGB colors."""
    r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
    g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
    b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
    return (r, g, b)


def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def extract_edge_column(image_path, edge='right', bg_color=(8, 11, 16)):
    """
    Extract a full column of pixels from the edge of an image.
    
    Args:
        image_path: Path to the image file
        edge: 'left' or 'right' - which edge to sample
        bg_color: Background color for compositing transparency
    
    Returns:
        List of RGB tuples, one per pixel height
    """
    img = Image.open(image_path).convert('RGBA')
    width, height = img.size
    
    # Determine which column to extract
    x = width - 1 if edge == 'right' else 0
    
    # Extract all pixels in that column
    colors = []
    for y in range(height):
        pixel = img.getpixel((x, y))
        rgb = composite_on_background(pixel, bg_color)
        colors.append(rgb)
    
    return colors, height


def generate_bridge_image(left_edge_colors, right_edge_colors, output_path, bridge_width=100):
    """
    Generate a bridge image that smoothly transitions between two edge color columns.
    
    Args:
        left_edge_colors: List of RGB colors from left banner's right edge
        right_edge_colors: List of RGB colors from right banner's left edge
        output_path: Where to save the bridge image
        bridge_width: Width of the bridge in pixels
    
    Returns:
        True if successful
    """
    # Both edges should have the same height
    height = len(left_edge_colors)
    
    # Create a new image for the bridge
    bridge = Image.new('RGB', (bridge_width, height))
    
    # For each row (y coordinate)
    for y in range(height):
        left_color = left_edge_colors[y]
        right_color = right_edge_colors[y]
        
        # For each column in the bridge (x coordinate)
        for x in range(bridge_width):
            # Calculate interpolation ratio (0.0 at left, 1.0 at right)
            ratio = x / (bridge_width - 1) if bridge_width > 1 else 0.5
            
            # Interpolate between left and right colors
            pixel_color = interpolate_color(left_color, right_color, ratio)
            
            # Set the pixel
            bridge.putpixel((x, y), pixel_color)
    
    # Save the bridge image
    bridge.save(output_path, 'PNG')
    return True


def average_colors(colors):
    """Average a list of RGB colors."""
    if not colors:
        return (0, 0, 0)
    avg_r = sum(c[0] for c in colors) // len(colors)
    avg_g = sum(c[1] for c in colors) // len(colors)
    avg_b = sum(c[2] for c in colors) // len(colors)
    return (avg_r, avg_g, avg_b)


def main():
    print("=" * 70)
    print("Banner Bridge Generator - Pixel-Perfect Edition")
    print("=" * 70)
    print()
    
    # Check if files exist
    if not os.path.exists(LEFT_BANNER_PATH):
        print(f"❌ Error: Left banner not found at {LEFT_BANNER_PATH}")
        return
    
    if not os.path.exists(RIGHT_BANNER_PATH):
        print(f"❌ Error: Right banner not found at {RIGHT_BANNER_PATH}")
        return
    
    print(f"📸 Extracting right edge from {LEFT_BANNER_PATH}...")
    left_edge_colors, left_height = extract_edge_column(
        LEFT_BANNER_PATH, 
        edge='right', 
        bg_color=BACKGROUND_COLOR
    )
    
    print(f"📸 Extracting left edge from {RIGHT_BANNER_PATH}...")
    right_edge_colors, right_height = extract_edge_column(
        RIGHT_BANNER_PATH, 
        edge='left', 
        bg_color=BACKGROUND_COLOR
    )
    
    # Use the taller of the two heights
    max_height = max(left_height, right_height)
    
    # Resize color lists if needed (stretch to match)
    if left_height < max_height:
        print(f"⚠️  Warning: Left banner is shorter ({left_height}px vs {max_height}px), stretching...")
        # Simple stretch - repeat colors proportionally
        left_edge_colors = [left_edge_colors[int(i * left_height / max_height)] for i in range(max_height)]
    
    if right_height < max_height:
        print(f"⚠️  Warning: Right banner is shorter ({right_height}px vs {max_height}px), stretching...")
        right_edge_colors = [right_edge_colors[int(i * right_height / max_height)] for i in range(max_height)]
    
    print()
    print(f"🎨 Generating {BRIDGE_WIDTH}px wide bridge with {max_height}px height...")
    
    success = generate_bridge_image(
        left_edge_colors,
        right_edge_colors,
        OUTPUT_BRIDGE_PATH,
        BRIDGE_WIDTH
    )
    
    if success:
        print(f"✅ Bridge image saved to: {OUTPUT_BRIDGE_PATH}")
        print()
        
        # Calculate average colors for CSS variables
        left_avg = average_colors(left_edge_colors)
        right_avg = average_colors(right_edge_colors)
        left_hex = rgb_to_hex(left_avg)
        right_hex = rgb_to_hex(right_avg)
        
        print("📋 CSS Updates:")
        print()
        print("1. Update CSS variables in style.css:")
        print(f"   --header-left: {left_hex};")
        print(f"   --header-right: {right_hex};")
        print()
        print("2. Update header background to use bridge image:")
        print(f"   background: url('/static/images/ui/banner_bridge.png');")
        print(f"   background-size: auto 100%;")
        print(f"   background-position: center;")
        print(f"   background-repeat: repeat-x;")
        print()
        print("=" * 70)
        print("✨ Pixel-perfect gradient bridge created!")
        print("=" * 70)
    else:
        print("❌ Failed to generate bridge image")


if __name__ == "__main__":
    main()
