import streamlit as st
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict
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




agency_df = st.session_state.agency_df
trips_df = st.session_state.trips_df
stops_df = st.session_state.stops_df
stop_times_df = st.session_state.stop_times_df
routes_df = st.session_state.routes_df
shapes_df = st.session_state.shapes_df



if "route" not in st.session_state or st.session_state.route is None:
    st.session_state.route = "T815"

unique_routes = routes_df["route_long_name"].unique()
if "T815" in unique_routes:
    unique_routes = np.insert(np.delete(unique_routes, np.where(unique_routes == "T815")), 0, "T815")
unique_days = ["Weekdays","Weekend"]

#with st.sidebar :
 #       selected_route = st.selectbox("Select a route", unique_routes)
  #      selected_day = st.selectbox("Select A day",unique_days)

# This can safely be outside the sidebar block
#st.session_state.route = selected_route
#st.session_state.day = selected_day




def add_connection_hour_column(df):
    hour_arr = []
    connection_arr=[]
    for i in range (len(df)):
      str_time = df.iloc[i]["median_time"]
      dt = datetime.datetime.strptime(str_time, "%H:%M:%S")
      hour = dt.hour
      hour_arr.append(hour)
      connection = f"{df.iloc[i]['station_before']} -> {df.iloc[i]['next_station']}"
      connection_arr.append(connection)

    df["hour"]=hour_arr
    df["connection"]=connection_arr
    return df

def remove_invalid_connections (route,df):
    routeid = routes_df[routes_df['route_long_name'] == route]['route_id'].values[0]
    tripid = trips_df[trips_df['route_id'] == routeid]['trip_id'].values[0]
    stoptimes = stop_times_df[stop_times_df['trip_id'] == tripid].sort_values('stop_sequence')
    stoptimes=stoptimes[:-1]
    stoptimes.reset_index(inplace=True)
    if (route == "T815"):
        stoptimes.drop([7,8,16],inplace=True)

    stoptimes.reset_index(inplace=True)
    stations = stoptimes['stop_headsign']
    connections = ['start -> ' + stations[0]] + [f"{stations[i]} -> {stations[i+1]}" for i in range(len(stations) - 1)]
    df = df[df["connection"].isin(connections)]

    return df

def visualise_each_connections(df,connection):
    df =df[df["connection"]==connection]
    avg_time = df['duration_minutes'].quantile(0.25)
    grouped_by_df = df.groupby('hour').agg(
        duration_minutes = ('duration_minutes','mean'),
        count_occ = ('hour','count')
    )
    grouped_by_df = grouped_by_df.rename(columns={'hour': 'hour', 'duration_minutes': 'avg_duration_minutes'})
    return grouped_by_df,avg_time


def visualise_each_hour(df,hour):
  df = df[df["hour"]==hour]
  grouped_by_df = df.groupby('connection').agg(
      duration_minutes = ('duration_minutes','mean'),
      count_occ = ('connection','count')
  ).reset_index()
  grouped_by_df =grouped_by_df[['connection','duration_minutes','count_occ']]
  grouped_by_df = grouped_by_df.rename(columns={'connection': 'connection', 'duration_minutes': 'avg_duration_minutes'})
  return grouped_by_df

def coloured_graph_vis(df,route,hour,day=None):
    df = df[df["trip_id_short"].str.contains(route)]
    df= add_connection_hour_column(df)
    initial_df = df.copy()
    if day != None:
      df = df[df["day"].isin(day)]
    df=df[df["hour"]==hour]
    df = remove_invalid_connections(route,df)
    df = visualise_each_hour(df,hour)
    average_arr = []
    for i in range(len(df)):
      df_temp,avg_time = visualise_each_connections(initial_df,df.iloc[i]["connection"])
      average_arr.append(avg_time)
    df["ideal_time"]=average_arr
    diff = []
    for i in range(len(df)):
      difference = df.iloc[i]["avg_duration_minutes"]-df.iloc[i]["ideal_time"]
      if difference <= 0 :
        difference = 0

      diff.append(difference)
    df["delay (minutes)"] = diff


    routeid = routes_df[routes_df['route_long_name'] == route]['route_id'].values[0]
    tripid = trips_df[trips_df['route_id'] == routeid]['trip_id'].values[0]
    stoptimes = stop_times_df[stop_times_df['trip_id'] == tripid].sort_values('stop_sequence')
    stoptimes=stoptimes[:-1]
    stoptimes.reset_index(inplace=True)
    if (route == "T815"):
        stoptimes.drop([7,8,16],inplace=True)

    stoptimes.reset_index(inplace=True)
    stations = stoptimes['stop_headsign']
    stations = stations.str.strip().unique()
    #print(stations)
    #stations = initial_df["next_station"].unique()
    nodes = stations
    edges = df["connection"].unique()

    net = Network(notebook=True, cdn_resources="in_line", directed=True, bgcolor="#C2C5C8B")

    # Add 'start' node explicitly along with other unique nodes
    all_nodes = ['start'] + list(nodes)

    # Determine nodes that are sources and targets
    source_set = set()
    target_set = set()
    for edge in edges:
        parts = edge.split("->")
        if len(parts) == 2:
            source_set.add(parts[0].strip())
            target_set.add(parts[1].strip())

    # Start nodes: those that never appear as a target (no incoming edge)
    start_nodes = {node for node in all_nodes if node not in target_set}
    # End nodes: those that never appear as a source (no outgoing edge)
    end_nodes = {node for node in all_nodes if node not in source_set}

    # Add nodes individually so we can assign a color if they are start or end nodes
    for node in all_nodes:
        # If node is a start or end node, set its color to black; otherwise, use default
        if node in start_nodes or node in end_nodes:
            net.add_node(node, label=node, color="#000000")
        else:
            net.add_node(node, label=node, color="#8BA5C0")

    min_delay = 0
    max_delay = 10


    for i in range(len(df)):
        parts = df.iloc[i]["connection"].split("->")
        if len(parts) == 2:
            source = parts[0].strip()
            target = parts[1].strip()
            delay = df.iloc[i]["delay (minutes)"]

            if delay < 2:
              colour = "#14E097"
            elif delay < 4 :
              colour = "#FED03F"
            else :
              colour = "#F24E42"

            net.add_edge(source, target, color=colour, width = 4 )

        net.toggle_physics(True)

    # Save mygraph.html explicitly in the current working directory
    current_dir = os.getcwd()
    file_path = os.path.join(current_dir, "mygraph.html")
    # Generate HTML manually
    html_content = net.generate_html(notebook=True)

    # Write to file using UTF-8 encoding
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return df


def page1_preprocessing(df,route,hour,day=None):
    df = df[df["trip_id_short"].str.contains(route)]
    df= add_connection_hour_column(df)
    initial_df = df.copy()
    if day != None:
      df = df[df["day"].isin(day)]
    df=df[df["hour"]==hour]
    df = remove_invalid_connections(route,df)
    df = visualise_each_hour(df,hour)
    average_arr = []
    for i in range(len(df)):
      df_temp,avg_time = visualise_each_connections(initial_df,df.iloc[i]["connection"])
      average_arr.append(avg_time)
    df["ideal_time"]=average_arr
    diff = []
    for i in range(len(df)):
      difference = df.iloc[i]["avg_duration_minutes"]-df.iloc[i]["ideal_time"]
      if difference <= 0 :
        difference = 0

      diff.append(difference)
    df["delay (minutes)"] = diff
    return df

col3,col4 = st.columns([1,3])
with col3 :
   st.image("rapidkl.png")
with col4 :
   st.write(" ")
st.markdown("---")

st.subheader("Route Overview")
with st.sidebar :
        selected_route = st.selectbox("Select a route", unique_routes)
        selected_day = st.selectbox("Select A day",unique_days)

# This can safely be outside the sidebar block
st.session_state.route = selected_route

if(selected_day=="Weekdays"):
   st.session_state.day = ["monday","tuesday","wednesday","thursday","friday"]
else:
   st.session_state.day = ["saturday","sunday"]
   


bus_data=st.session_state.bus_data
st.session_state.df = bus_data[bus_data["trip_id_short"].str.contains(st.session_state.route)]

df = st.session_state.df
if st.session_state.day != None:
    df = df[df["day"].isin(st.session_state.day)]


initial_df = df.copy()



col1, col2  = st.columns([1,2])

with col1 :
    time_arr = [6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
    st.write("\n")
    st.session_state.hour = st.selectbox("Select a Time (24 Hour Format)", time_arr )
    st.markdown(
        """
        <h6 style='margin-bottom:10px;'>Traffic Condition Legend</h6>
        <div style='display: flex; align-items: center;'>
            <div style='width: 20px; height: 20px; background-color: #14E097; margin-right: 10px;'></div> Normal Traffic
        </div>
        <div style='display: flex; align-items: center; margin-top: 5px;'>
            <div style='width: 20px; height: 20px; background-color: #FED03F; margin-right: 10px;'></div> Moderate Traffic
        </div>
        <div style='display: flex; align-items: center; margin-top: 5px;'>
            <div style='width: 20px; height: 20px; background-color: #F24E42; margin-right: 10px;'></div> Heavy Traffic
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    df_vis=page1_preprocessing(df,st.session_state.route,st.session_state.hour)
    #st.write(df_vis)
    top5_df = df_vis.sort_values(by="delay (minutes)", ascending=False).head(5)
    # Wrap long labels using textwrap
    wrapped_labels = [textwrap.fill(label, width=12) for label in top5_df["connection"]]
    # Plot using Matplotlib
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(wrapped_labels, top5_df["delay (minutes)"], color="#F24E42")
    ax.set_xlabel("Connection")
    ax.set_ylabel("Delay (minutes)")
    ax.set_title("Top 5 Delays between stations")

    # Show in Streamlit
    st.pyplot(fig)
    

coloured_graph_vis(bus_data,st.session_state.route,st.session_state.hour,st.session_state.day)

with open("mygraph.html", "r", encoding="utf-8") as f:
    html_data = f.read()

# Display the PyVis graph in Streamlit
components.html(html_data, height=600, scrolling=True)








