import os
import sys
from io import BytesIO
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pyart
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from metpy.plots import colortables
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib as mpl
from PIL import Image

# -------------------
# Configuration
# -------------------
FOLDER = "nexrad"
GIF_FILENAME = "radar_loop.gif"
BASE_URL = "https://unidata-nexrad-level3.s3.amazonaws.com/"
STATION = "MOB_N0B"

# Accept date as argument, otherwise use today UTC
if len(sys.argv) > 1:
    utc_date = sys.argv[1]  # format: YYYY_MM_DD
else:
    utc_date = datetime.utcnow().strftime("%Y_%m_%d")

# Ensure output folder exists
os.makedirs(FOLDER, exist_ok=True)

# -------------------
# Fetch latest 5 files
# -------------------
print(f"Fetching latest MOB files for {utc_date}...")

index_url = f"{BASE_URL}?prefix={STATION}_{utc_date}"
r = requests.get(index_url)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")
keys = [k.text for k in soup.find_all("key") if k.text.startswith(f"{STATION}_{utc_date}")]
keys = sorted(keys)[-5:]  # latest 5 files, oldest → newest

print("Files to fetch:")
for k in keys:
    print(f" - {k}")

# -------------------
# Prepare colormap
# -------------------
cmap = ListedColormap(colortables['NWSReflectivity'])

# -------------------
# Process each radar file
# -------------------
png_files = []

for key in keys:
    file_url = f"{BASE_URL}{key}"
    print(f"Fetching {file_url}...")
    r = requests.get(file_url)
    r.raise_for_status()

    file_like = BytesIO(r.content)
    radar = pyart.io.read_nexrad_level3(file_like)

    # Create plot
    fig, ax = plt.subplots(figsize=(8,8), subplot_kw={'projection': ccrs.Mercator()})
    display = pyart.graph.RadarMapDisplay(radar)

    display.plot_ppi_map(
        'reflectivity',
        resolution='50m',
        min_lon=-90, max_lon=-85,
        min_lat=30, max_lat=33,
        cmap=cmap,
        vmin=-10, vmax=70,
        ax=ax,
        colorbar_flag=False
    )

    # Add geographic features
    ax.add_feature(cfeature.STATES.with_scale('50m'), edgecolor='black', linewidth=1)
    ax.add_feature(cfeature.BORDERS.with_scale('50m'), edgecolor='black', linewidth=1)

    # Manual colorbar
    norm = mpl.colors.Normalize(vmin=-10, vmax=70)
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label('dBZ')

    # Convert UTC to CDT
    utc_time_str = radar.time['units']
    utc_time_iso = utc_time_str.split("since")[1].strip().replace('Z','')
    utc_dt = datetime.fromisoformat(utc_time_iso)
    cdt_dt = utc_dt - timedelta(hours=5)
    cdt_label = cdt_dt.strftime('%Y-%m-%d %H:%M CDT')

    # Overlay timestamp
    ax.text(
        0.02, 0.95, cdt_label, transform=ax.transAxes,
        color='white', fontsize=12, fontweight='bold',
        bbox=dict(facecolor='black', alpha=0.5, pad=2)
    )

    # Save PNG
    out_png = os.path.join(FOLDER, key.split('/')[-1] + "_mercator.png")
    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close()
    png_files.append(out_png)
    print(f"Saved {out_png}")

# -------------------
# Create forward-playing GIF
# -------------------
print("Creating GIF...")
# Ensure oldest → newest
png_files = png_files[::-1]

images = []
base_size = None
for filename in png_files:
    img = Image.open(filename)
    if base_size is None:
        base_size = img.size
    else:
        img = img.resize(base_size, Image.BILINEAR)
    images.append(img)

images[0].save(
    GIF_FILENAME,
    save_all=True,
    append_images=images[1:],
    duration=800,
    loop=0
)

print(f"GIF saved as {GIF_FILENAME}")
print(f"All PNG files kept in {FOLDER}/")
