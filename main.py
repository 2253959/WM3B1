import dearpygui.dearpygui as dpg
import pandas as pd
import folium
import webbrowser
import os
import requests
import hashlib

dpg.create_context()

data = None
altitude_data = None
battery_data = None
time_data = None
distance_data = None
formatted_date = None
file_hashes = None
current_file_path = None

def calculate_file_hashes(file_path):
    """Calculate MD5 and SHA256 hashes of the file"""
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        # Read the file in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(4096), b''):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
    
    return {
        'md5': md5_hash.hexdigest(),
        'sha256': sha256_hash.hexdigest()
    }

def load_data(file_path):
    global data, altitude_data, battery_data, time_data, distance_data, formatted_date, file_hashes, current_file_path
    
    current_file_path = file_path
    file_hashes = calculate_file_hashes(file_path)
    data = pd.read_csv(file_path)

    # Extract data from csv
    altitude_data = data.iloc[:, 5].tolist()
    battery_data = data.iloc[:, 107].tolist()
    time_data = data.iloc[:, 81].tolist()
    distance_data = data.iloc[:, 55].tolist()

    date = data.iloc[:2, 80].tolist()
    raw_date = str(date[0])

    # Format the date from YYYYMMDD to DD-MM-YYYY
    if len(raw_date) == 8:
        formatted_date = f"{raw_date[6:8]}-{raw_date[4:6]}-{raw_date[0:4]}"
    else:
        formatted_date = "Invalid Date"

    create_main_window()

def callback_file_dialog(sender, app_data):
    file_path = app_data['file_path_name']
    load_data(file_path)
    dpg.delete_item("file_dialog_id")

def load_coordinates(csv_file_path):
    df = pd.read_csv(csv_file_path)
    df = df.iloc[:, [2, 3]].dropna()
    longitudes = df.iloc[:, 0].tolist()
    latitudes = df.iloc[:, 1].tolist()
    return longitudes, latitudes

# Populate folium with coordinates from csv
def create_map(longitudes, latitudes):
    if not longitudes or not latitudes:
        raise ValueError("No valid coordinates to plot.")

    avg_lat = sum(latitudes) / len(latitudes)
    avg_lon = sum(longitudes) / len(longitudes)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=18)

    for lon, lat in zip(longitudes, latitudes):
        folium.Marker(location=[lat, lon]).add_to(m)

    map_file = "map.html"
    m.save(map_file)
    return map_file, avg_lat, avg_lon

# Query OSM with coordinates to get location
def get_approximate_location(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    headers = {
        'User-Agent': 'DJIpyGUI/1.0'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        location_data = response.json()
        return location_data.get('display_name', 'Unknown location')
    else:
        return "Error retrieving location"

def update_plot(sender, app_data):
    selected_data = app_data
    dpg.delete_item("line_series")

    if selected_data == "Altitude":
        dpg.add_line_series(time_data, altitude_data, label="Altitude", tag="line_series", parent="y_axis")
        dpg.set_axis_limits("y_axis", min(altitude_data), max(altitude_data))
        dpg.set_item_label("y_axis", "Altitude (Metres)") 
    elif selected_data == "Battery":
        dpg.add_line_series(time_data, battery_data, label="Battery", tag="line_series", parent="y_axis")
        dpg.set_axis_limits("y_axis", min(battery_data), max(battery_data))
        dpg.set_item_label("y_axis", "Battery Capacity (Percentage)")
    elif selected_data == "Distance":
        dpg.add_line_series(time_data, distance_data, label="Distance", tag="line_series", parent="y_axis")
        dpg.set_axis_limits("y_axis", min(distance_data), max(distance_data))
        dpg.set_item_label("y_axis", "Distance Travelled (Metres)") 

def get_location():
    if data is None:
        return
        
    longitudes, latitudes = load_coordinates(current_file_path)
    if not longitudes or not latitudes:
        dpg.set_value("location_text", "No valid coordinates found in the CSV file.")
        return
    
    # Calculate average location for API call
    avg_lat = sum(latitudes) / len(latitudes)
    avg_lon = sum(longitudes) / len(longitudes)
    
    approx_location = get_approximate_location(avg_lat, avg_lon)
    dpg.set_value("location_text", f"{approx_location}")

def show_map():
    if data is None:
        return
        
    longitudes, latitudes = load_coordinates(current_file_path)
    if not longitudes or not latitudes:
        dpg.add_text("No valid coordinates found in the CSV file.")
        return
    
    map_file, avg_lat, avg_lon = create_map(longitudes, latitudes)
    # Open map.html in browser
    webbrowser.open(f"file://{os.path.abspath(map_file)}")

def create_main_window():
    with dpg.window(tag="Primary Window"):

        dpg.add_text("File hashes:", color=(255, 255, 0))
        dpg.add_text(f"MD5: {file_hashes['md5']}")
        dpg.add_text(f"SHA256: {file_hashes['sha256']}")

        dpg.add_separator()
        
        dpg.add_text(f"Date of the flight (DD-MM-YYYY): {formatted_date}")
        
        dpg.add_button(label="Show flight path (opens in your browser)", callback=show_map)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Get approximate location of drone (uses the internet)", callback=get_location)
            dpg.add_text("", tag="location_text")

        dpg.add_separator()

        dpg.add_combo(["Altitude", "Battery", "Distance"], label="Select Data Type", callback=update_plot)
        with dpg.plot(label="Data Plot", height=720, width=1280):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Time (HoursMinutesSeconds)")
            dpg.add_plot_axis(dpg.mvYAxis, label="Altitude (Metres)", tag="y_axis")

            dpg.add_line_series(time_data, altitude_data, label="Altitude", tag="line_series", parent="y_axis")
            dpg.set_axis_limits("y_axis", min(altitude_data), max(altitude_data))

    dpg.set_primary_window("Primary Window", True)

def _hyperlink(text, address):
    b = dpg.add_button(label=text, callback=lambda:webbrowser.open(address))
    dpg.bind_item_theme(b, "__demo_hyperlinkTheme")

def create_welcome_window():
    with dpg.window(label="Welcome to DJIpyGUI", tag="welcome_window", 
                   no_resize=True, no_move=True, no_close=True,
                   width=500, height=250):
        dpg.add_text("This application helps you to analyse drone flight data.")
        dpg.add_separator()
        dpg.add_text("Please use DatCon to export a CSV file of your flight.")
        with dpg.group(horizontal=True):
            dpg.add_text("Available for download")
            _hyperlink("here", "https://datfile.net/DatCon/downloads.html")
            dpg.add_text("(opens in your browser).")
        dpg.add_text("Then navigate to and the select that file you exported by clicking")
        dpg.add_text("the button below.")
        dpg.add_separator()
        dpg.add_button(label="Select File", callback=show_file_dialog)
        
        # Center the window
        dpg.set_item_pos("welcome_window", 
            [(dpg.get_viewport_width() - 400) // 2, 
             (dpg.get_viewport_height() - 150) // 2])

def show_file_dialog():
    dpg.delete_item("welcome_window")
    
    with dpg.file_dialog(
        directory_selector=False, 
        show=True,
        callback=callback_file_dialog,
        tag="file_dialog_id",
        width=700,
        height=400,
        modal=True,
        default_filename="",
        default_path=""):
        
        dpg.add_file_extension(".csv", color=(0, 255, 0, 255))

dpg.create_viewport(title='DJIpyGUI', width=1340, height=960)
dpg.setup_dearpygui()
dpg.show_viewport()

create_welcome_window()

dpg.start_dearpygui()
dpg.destroy_context()