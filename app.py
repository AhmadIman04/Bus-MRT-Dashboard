import streamlit as st
import streamlit as st
import pandas as pd
from requests import get
import requests
import textwrap
import zipfile
import io
import pyproj
from shapely.geometry import Point, LineString
from shapely.ops import transform
import warnings
import matplotlib
import matplotlib.colors as mcolors
import datetime
import os
from pyvis.network import Network
import streamlit.components.v1 as components
import numpy as np

import matplotlib.pyplot as plt

Page1 = st.Page(
    "pages/page1.py",
    title="Route Overview",
    icon="🚌",  # Compass emoji
    default=True,
)

Page2 = st.Page(
    "pages/page2.py",
    title="Station-to-Station Analysis",
    icon="🚏",  # Target emoji
)


# --- NAVIGATION SETUP ---
pg = st.navigation(pages=[Page1, Page2])

# Disable the SettingWithCopyWarning from pandas
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)

STATIC_FOLDER = 'rapid-bus-mrtfeeder'

# --- Ensure download + extraction + loading only happens once ---
if "gtfs_data_loaded" not in st.session_state:
        # Load all into session state
        st.session_state.agency_df = pd.read_csv(f'{STATIC_FOLDER}/agency.txt')
        st.session_state.trips_df = pd.read_csv(f'{STATIC_FOLDER}/trips.txt')
        st.session_state.stops_df = pd.read_csv(f'{STATIC_FOLDER}/stops.txt')
        st.session_state.stop_times_df = pd.read_csv(f'{STATIC_FOLDER}/stop_times.txt')
        st.session_state.routes_df = pd.read_csv(f'{STATIC_FOLDER}/routes.txt')
        st.session_state.shapes_df = pd.read_csv(f'{STATIC_FOLDER}/shapes.txt')

        # Flag to prevent re-downloading/reloading
        st.session_state.gtfs_data_loaded = True


# --- Now you can use the DataFrames like normal ---
routes_df = st.session_state.routes_df


unique_routes = routes_df["route_long_name"].unique()
# Move "T815" to the front if it's in the array
if "T815" in unique_routes:
    unique_routes = np.insert(np.delete(unique_routes, np.where(unique_routes == "T815")), 0, "T815")

unique_days = [None,"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


st.session_state.bus_data = pd.concat(
    [pd.read_csv(f"bus_data_folder/{file}") for file in os.listdir("bus_data_folder") if file.endswith('.csv')],
    ignore_index=True
)


pg.run()