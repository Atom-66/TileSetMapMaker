import os
from PIL import Image, ImageDraw

def create_sample_assets(base_dir: str = "sample_assets"):
    os.makedirs(f"{base_dir}/Terrain/Grass", exist_ok=True)
    os.makedirs(f"{base_dir}/Terrain/Water", exist_ok=True)
    os.makedirs(f"{base_dir}/Objects/Trees", exist_ok=True)
    os.makedirs(f"{base_dir}/Buildings/Houses", exist_ok=True)

    # 1. Single grass tile (32x32)
    img = Image.new("RGBA", (32, 32), (34, 139, 34, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, 27, 27], fill=(46, 170, 46, 255))
    draw.rectangle([8, 8, 23, 23], fill=(60, 200, 60, 255))
    img.save(f"{base_dir}/Terrain/Grass/grass_01.png")

    img2 = Image.new("RGBA", (32, 32), (34, 139, 34, 255))
    draw2 = ImageDraw.Draw(img2)
    draw2.ellipse([6, 6, 25, 25], fill=(70, 210, 70, 255))
    img2.save(f"{base_dir}/Terrain/Grass/grass_02.png")

    # 2. Water tile
    img_w = Image.new("RGBA", (32, 32), (30, 144, 255, 255))
    draw_w = ImageDraw.Draw(img_w)
    draw_w.line([0, 8, 31, 8], fill=(65, 105, 225, 255), width=2)
    draw_w.line([0, 20, 31, 20], fill=(65, 105, 225, 255), width=2)
    img_w.save(f"{base_dir}/Terrain/Water/water.png")

    # 3. Tileset: 64x64 containing 4 tiles (32x32 each)
    tileset = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(tileset)
    # Tile 0,0: Stone
    d.rectangle([0, 0, 31, 31], fill=(128, 128, 128, 255))
    d.rectangle([4, 4, 27, 27], fill=(160, 160, 160, 255))
    # Tile 1,0: Cobble
    d.rectangle([32, 0, 63, 31], fill=(105, 105, 105, 255))
    d.ellipse([36, 4, 59, 27], fill=(140, 140, 140, 255))
    # Tile 0,1: Dirt
    d.rectangle([0, 32, 31, 63], fill=(139, 69, 19, 255))
    d.rectangle([6, 38, 25, 57], fill=(160, 82, 45, 255))
    # Tile 1,1: Sand
    d.rectangle([32, 32, 63, 63], fill=(238, 214, 175, 255))
    d.rectangle([36, 36, 59, 59], fill=(244, 164, 96, 255))
    tileset.save(f"{base_dir}/Terrain/terrain_tileset.png")

    # 4. Large single PNG graphic (Tree 64x96 px)
    tree = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
    td = ImageDraw.Draw(tree)
    # Trunk
    td.rectangle([24, 60, 39, 95], fill=(101, 67, 33, 255))
    # Foliage
    td.ellipse([4, 4, 59, 68], fill=(34, 139, 34, 255))
    td.ellipse([10, 10, 53, 60], fill=(46, 170, 46, 255))
    tree.save(f"{base_dir}/Objects/Trees/large_tree.png")

    # 5. Building (House 96x96 px)
    house = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    hd = ImageDraw.Draw(house)
    # Roof
    hd.polygon([(48, 4), (8, 44), (88, 44)], fill=(178, 34, 34, 255))
    # Walls
    hd.rectangle([14, 44, 82, 92], fill=(210, 180, 140, 255))
    # Door
    hd.rectangle([38, 64, 58, 92], fill=(101, 67, 33, 255))
    house.save(f"{base_dir}/Buildings/Houses/cottage.png")
    print(f"Sample assets created in {base_dir}")

if __name__ == "__main__":
    create_sample_assets()
