import matplotlib.pyplot as plt
import zipfile
import math
import pandas as pd
import streamlit as st
import geopandas as gpd
import pyproj
from shapely.geometry import Polygon, Point, box
from io import BytesIO
import os
import shutil
from datetime import datetime

# Hardcoded constant value
data = {
    'SN': range(1, 26),
    'scientific_name': ['Abies spp', 'Acacia catechu', 'Adina cardifolia', 'Albizia spp', 'Alnus nepalensis',
                       'Anogeissus latifolia', 'Bombax ceiba', 'Cedrela toona', 'Dalbergia sissoo',
                       'Eugenia Jambolana', 'Hymenodictyon excelsum', 'Lagerstroemia parviflora',
                       'Michelia champaca', 'Pinus roxburghii', 'Pinus wallichiana', 'Quercus spp',
                       'Schima wallichii', 'Shorea robusta', 'Terminalia alata', 'Trewia nudiflora',
                       'Tsuga spp', 'Terai spp', 'Hill spp', 'Coniferious', 'Broadleaved'],
    'a': [-2.4453, -2.3256, -2.5626, -2.4284, -2.7761, -2.272, -2.3856, -2.1832, -2.1959, -2.5693,
          -2.585, -2.3411, -2.0152, -2.977, -2.8195, -2.36, -2.7385, -2.4554, -2.4616, -2.4585,
          -2.5293, -2.3993, -2.3204, None, None],
    'b': [1.722, 1.6476, 1.8598, 1.7609, 1.9006, 1.7499, 1.7414, 1.8679, 1.6567, 1.8816,
          1.9437, 1.7246, 1.8555, 1.9235, 1.725, 1.968, 1.8155, 1.9026, 1.8497, 1.8043,
          1.7815, 1.7836, 1.8507, None, None],
    'c': [1.0757, 1.0552, 0.8783, 0.9662, 0.9428, 0.9174, 1.0063, 0.7569, 0.9899, 0.8498,
          0.7902, 0.9702, 0.763, 1.0019, 1.1623, 0.7496, 1.0072, 0.8352, 0.88, 0.922,
          1.0369, 0.9546, 0.8223, None, None],
    'a1': [5.4433, 5.4401, 5.4681, 4.4031, 6.019, 4.9502, 4.5554, 4.9705, 4.358, 5.1749,
           5.5572, 5.3349, 3.3499, 6.2696, 5.7216, 4.8511, 7.4617, 5.2026, 4.5968, 5.3475,
           5.2774, 4.8991, 5.5323, None, None],
    'b1': [-2.6902, -2.491, -2.491, -2.2094, -2.7271, -2.3353, -2.3009, -2.3436, -2.1559, -2.3636,
           -2.496, -2.4428, -2.0161, -2.8252, -2.6788, -2.4494, -3.0676, -2.4788, -2.2305, -2.4774,
           -2.6483, -2.3406, -2.4815, None, None],
    's': [0.436, 0.443, 0.443, 0.443, 0.803, 0.443, 0.443, 0.443, 0.684, 0.443,
          0.443, 0.443, 0.443, 0.189, 0.683, 0.747, 0.52, 0.055, 0.443, 0.443,
          0.443, 0.443, 0.443, 0.436, 0.443],
    'm': [0.372, 0.511, 0.511, 0.511, 1.226, 0.511, 0.511, 0.511, 0.684, 0.511,
          0.511, 0.511, 0.511, 0.256, 0.488, 0.96, 0.186, 0.341, 0.511, 0.511,
          0.511, 0.511, 0.511, 0.372, 0.511],
    'bg': [0.355, 0.71, 0.71, 0.71, 1.51, 0.71, 0.71, 0.71, 0.684, 0.71,
           0.71, 0.71, 0.71, 0.3, 0.41, 1.06, 0.168, 0.357, 0.71, 0.71,
           0.71, 0.71, 0.71, 0.355, 0.71],
    'Local_Name': ['Thingre Salla', 'Khayar', 'Karma', 'Siris', 'Uttis', 'Banjhi', 'Simal', 'Tooni',
                   'Sissoo', 'Jamun', 'Bhudkul', 'Botdhayero', 'Chanp', 'Khote Salla', 'Gobre Salla',
                   'Kharsu', 'Chilaune', 'Sal', 'Saj', 'Gamhari', 'Dhupi Salla', 'Terai Spp',
                   'Hill spp', None, None]
}

# Wrap constant data in a variable
sppVal = pd.DataFrame(data)
sppVal = sppVal.fillna('')

# Set the title of the Streamlit app
st.title("Stem Mapping File (CSV File Uploader)")

# File uploader for TreeLoc.csv
stemmapping = st.file_uploader("Upload TreeLoc.csv", type="csv")
df = None  # Initialize df to None

if stemmapping is not None:
    try:
        df = pd.read_csv(stemmapping)
        st.write("Uploaded Data Preview:")
        st.write(df.head())
        # Validate required columns and data types
        required_columns = ['species', 'dia_cm', 'height_m', 'class', 'LONGITUDE', 'LATITUDE']
        if not all(col in df.columns for col in required_columns):
            st.error(f"Missing required columns. Expected: {required_columns}")
            st.stop()
        if not all(df['dia_cm'].apply(lambda x: isinstance(x, (int, float)))):
            st.error("Column 'dia_cm' contains non-numeric values.")
            st.stop()
        if not all(df['height_m'].apply(lambda x: isinstance(x, (int, float)))):
            st.error("Column 'height_m' contains non-numeric values.")
            st.stop()
        if df['dia_cm'].le(0).any() or df['height_m'].le(0).any():
            st.error("Columns 'dia_cm' and 'height_m' must contain positive values.")
            st.stop()
    except Exception as e:
        st.error(f"An error occurred while reading the file: {e}")
        st.stop()
else:
    st.info("Please upload the TreeLoc.csv file.")

# Conditional execution
if df is not None:
    # Merge with species data
    joined_df = df.merge(sppVal, left_on='species', right_on='scientific_name', how='left')
    if joined_df.empty:
        st.error("No matching species found in the merge. Check 'species' column in TreeLoc.csv.")
        st.stop()
    result_df = joined_df.copy()

    def add_calculated_columns(df):
        df['dia_cm'] = pd.to_numeric(df['dia_cm'], errors='coerce')
        df['height_m'] = pd.to_numeric(df['height_m'], errors='coerce')
        if df['dia_cm'].isna().any() or df['height_m'].isna().any():
            st.error("Invalid or missing values in 'dia_cm' or 'height_m'.")
            st.stop()
        df['stem_volume'] = (df['a'] + df['b'] * df['dia_cm'].apply(lambda x: math.log(x)) + df['c'] * df['height_m'].apply(lambda x: math.log(x))).apply(math.exp) / 1000
        df['branch_ratio'] = df['dia_cm'].apply(lambda x: 0.1 if x < 10 else 0.2)
        df['branch_volume'] = df['stem_volume'] * df['branch_ratio']
        df['tree_volume'] = df['stem_volume'] + df['branch_volume']
        df['cm10diaratio'] = (df['a1'] + df['b1'] * df['dia_cm'].apply(lambda x: math.log(x))).apply(math.exp)
        df['cm10topvolume'] = df['stem_volume'] * df['cm10diaratio']
        df['gross_volume'] = df['stem_volume'] - df['cm10topvolume']
        df['net_volume'] = df.apply(lambda row: row['gross_volume'] * 0.9 if row['class'] == 'A' else row['gross_volume'] * 0.8, axis=1)
        df['net_volum_cft'] = df['net_volume'] * 35.3147
        df['firewood_m3'] = df['tree_volume'] - df['net_volume']
        df['firewood_chatta'] = df['firewood_m3'] * 0.105944
        return df

    result_df = add_calculated_columns(df=result_df)

    # Drop unnecessary columns
    columns_to_drop = ['SN', 'scientific_name', 'a', 'b', 'c', 'a1', 'b1', 's', 'm', 'bg']
    result_df = result_df.drop(columns=[col for col in columns_to_drop if col in result_df.columns])

    # Download result_df as CSV
    csv_data = result_df.to_csv(index=False)
    st.download_button(
        label="Download result_df as CSV",
        data=csv_data,
        file_name='result_df.csv',
        mime='text/csv'
    )

    # Convert to GeoDataFrame
    result_df['geometry'] = result_df.apply(lambda row: Point(row['LONGITUDE'], row['LATITUDE']), axis=1)
    result_gdf = gpd.GeoDataFrame(result_df, geometry='geometry', crs='epsg:4326')

    # Create bounding box
    xmin, ymin, xmax, ymax = result_gdf.total_bounds
    bounding_polygon = box(xmin, ymin, xmax, ymax)
    bounding_gdf = gpd.GeoDataFrame(geometry=[bounding_polygon], crs=result_gdf.crs)

    # User input for grid spacing
    st.title("Grid Spacing in Meters for Mother Tree")
    grid_spacing = st.number_input("Enter Grid Spacing (meters)", value=20.0, step=0.1, format="%.2f")
    st.write(f"Grid Spacing: {grid_spacing}")

    # Create grid
    spacing_meters = grid_spacing
    center_lat = (ymin + ymax) / 2
    if math.cos(math.radians(center_lat)) == 0:
        st.error("Invalid center latitude for grid spacing calculation.")
        st.stop()
    spacing_degrees = spacing_meters / (111320 * math.cos(math.radians(center_lat)))
    st.write(f"spacing_degrees: {spacing_degrees}")
    num_x = int((xmax - xmin) / spacing_degrees) + 1
    num_y = int((ymax - ymin) / spacing_degrees) + 1
    x_coords = [xmin + i * spacing_degrees for i in range(num_x)]
    y_coords = [ymin + i * spacing_degrees for i in range(num_y)]
    st.write(f"x_coords: {x_coords}")
    st.write(f"y_coords: {y_coords}")
    polygons = [Polygon([(x, y), (x + spacing_degrees, y), (x + spacing_degrees, y + spacing_degrees), (x, y + spacing_degrees)]) 
                for x in x_coords for y in y_coords]
    grid_gdf = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')
    grid_gdf = gpd.clip(grid_gdf, bounding_gdf)

    # Spatial join to find intersecting grid cells
    intersected_grid_indices = gpd.sjoin(grid_gdf, result_gdf, how='inner', predicate='intersects').index.unique()
    selected_polygons_gdf = grid_gdf[grid_gdf.index.isin(intersected_grid_indices)].reset_index(drop=True)

    # Display grid plot
    st.write("Grid Plot:")
    fig, ax = plt.subplots()
    selected_polygons_gdf.plot(ax=ax)
    st.pyplot(fig)

    # User input for EPSG code
    st.title("Projection Settings")
    epsg_code = st.text_input("Enter EPSG code for projection:", "32633")
    try:
        projected_gdf = selected_polygons_gdf.to_crs(f"EPSG:{int(epsg_code)}")
        centroid_gdf = projected_gdf.copy()
        centroid_gdf['geometry'] = centroid_gdf['geometry'].centroid
        centroid_gdf = centroid_gdf.to_crs(selected_polygons_gdf.crs)

        # Perform spatial join in projected CRS
        projected_crs = st.text_input("Enter EPSG Code for Nearest Neighbor Analysis:", value="EPSG:4326")
        if projected_crs:
            try:
                centroid_gdf_proj = centroid_gdf.to_crs(projected_crs)
                result_gdf_proj = result_gdf.to_crs(projected_crs)
                joined_gdf = gpd.sjoin_nearest(centroid_gdf_proj, result_gdf_proj, how='left', distance_col='distance')
                nearest_tree_indices = joined_gdf.groupby(joined_gdf.index)['distance'].idxmin()
                result_gdf = result_gdf.copy()  # Avoid SettingWithCopyWarning
                result_gdf['remark'] = 'Felling Tree'
                result_gdf.loc[nearest_tree_indices, 'remark'] = 'Mother Tree'

                # Display results
                st.write("Updated Result GeoDataFrame:")
                st.write(result_gdf)

                # Download result_gdf as CSV
                def download_csv(gdf, filename):
                    csv = gdf.to_csv(index=False)
                    st.download_button(
                        label=f"Download {filename}.csv",
                        data=csv,
                        file_name=f"{filename}.csv",
                        mime="text/csv"
                    )
                download_csv(result_gdf, "result_gdf")

                # Download result_gdf as zipped shapefile
                def download_gdf_zip(gdf, filename):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_dir = f"shapefile_{timestamp}"
                    os.makedirs(temp_dir, exist_ok=True)
                    shapefile_path = os.path.join(temp_dir, filename)
                    try:
                        gdf.to_file(shapefile_path, driver="ESRI Shapefile")
                        zip_buffer = BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                                file_path = f"{shapefile_path}{ext}"
                                if os.path.exists(file_path):
                                    zipf.write(file_path, f"{filename}{ext}")
                        zip_buffer.seek(0)
                        st.download_button(
                            label=f"Download {filename}.zip",
                            data=zip_buffer,
                            file_name=f"{filename}.zip",
                            mime="application/zip"
                        )
                    finally:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)

                if st.button('Download Shapefile'):
                    download_gdf_zip(result_gdf, "result_gdf")

            except pyproj.exceptions.CRSError as e:
                st.error(f"Error: Invalid CRS provided. Please enter a valid EPSG code.\nDetails: {e}")
    except ValueError:
        st.error("Please enter a valid EPSG code.")
