import streamlit as st
import os
from pyvis.network import Network
import datetime
import streamlit.components.v1 as components
import scipy.stats as stats
import statsmodels.stats.multicomp as mc
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

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

routes_df = st.session_state.routes_df
trips_df = st.session_state.trips_df
stop_times_df = st.session_state.stop_times_df

def build_network_graph(df, route, hour=10, day=None):
    df = df[df["trip_id_short"].str.contains(route)]
    df = add_connection_hour_column(df)
    initial_df = df.copy()
    if day != None:
        df = df[df["day"].isin(day)]
    df = df[df["hour"] == hour]
    df = remove_invalid_connections(route, df)
    df = visualise_each_hour(df, hour)
    
    average_arr = []
    for i in range(len(df)):
        df_temp, avg_time = visualise_each_connections(initial_df, df.iloc[i]["connection"])
        average_arr.append(avg_time)
    df["ideal_time"] = average_arr
    
    diff = []
    for i in range(len(df)):
        difference = df.iloc[i]["avg_duration_minutes"] - df.iloc[i]["ideal_time"]
        if difference <= 0:
            difference = 0
        diff.append(difference)
    df["delay (minutes)"] = diff

    routeid = routes_df[routes_df['route_long_name'] == route]['route_id'].values[0]
    tripid = trips_df[trips_df['route_id'] == routeid]['trip_id'].values[0]
    stoptimes = stop_times_df[stop_times_df['trip_id'] == tripid].sort_values('stop_sequence')
    stoptimes = stoptimes[:-1]
    stoptimes.reset_index(inplace=True)
    
    if (route == "T815"):
        stoptimes.drop([7, 8, 16], inplace=True)
    stoptimes.reset_index(inplace=True)
    stations = stoptimes['stop_headsign']
    stations = stations.str.strip().unique()
    nodes = stations
    edges = df["connection"].unique()

    net = Network(notebook=True, cdn_resources="in_line", directed=True, bgcolor="#FFFFFF")

    all_nodes = ['start'] + list(nodes)
    source_set = set()
    target_set = set()
    
    for edge in edges:
        parts = edge.split("->")
        if len(parts) == 2:
            source_set.add(parts[0].strip())
            target_set.add(parts[1].strip())

    start_nodes = {node for node in all_nodes if node not in target_set}
    end_nodes = {node for node in all_nodes if node not in source_set}

    for node in all_nodes:
        if node in start_nodes or node in end_nodes:
            net.add_node(node, label=node, color="#000000")
        else:
            net.add_node(node, label=node, color="#8BA5C0")

    # Simplified edge coloring - single color for all edges
    for i in range(len(df)):
        parts = df.iloc[i]["connection"].split("->")
        if len(parts) == 2:
            source = parts[0].strip()
            target = parts[1].strip()
            # Set all edges to the same color
            net.add_edge(source, target, color="#90a4c4", width=4)

    net.toggle_physics(True)

    current_dir = os.getcwd()
    file_path = os.path.join(current_dir, "mygraph1.html")
    html_content = net.generate_html(notebook=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return df

def distribution_analysis_each_connection(connection,df):
    df = df[df["connection"]==connection]
    # --- One-Way ANOVA ---
    # Assume df is your DataFrame with 'hour' and 'duration_minutes' columns
    groups = [group['duration_minutes'].values for name, group in df.groupby('hour')]
    anova_result = stats.f_oneway(*groups)

    print("ANOVA F-statistic:", anova_result.statistic)
    print("ANOVA p-value:", anova_result.pvalue)

    if anova_result.pvalue < 0.05:
        print("The travel duration across these two stations are affected by time")

    else:
        print("The travel duration across these two stations are not affected by time")



    temp_df, avg_time = visualise_each_connections(df,connection)

    plt.figure(figsize=(10,6))
    sns.barplot(x='hour', y='avg_duration_minutes', data=temp_df, palette='viridis')
    plt.xlabel('Hour')
    plt.ylabel('Average Bus Travel Time')
    plt.title('Bus Travel Time by Hour (Average in Minutes)')
    plt.show()

    palette = sns.color_palette("husl", n_colors=df['hour'].nunique())
    overall_avg = df['duration_minutes'].mean()

    fig = plt.figure(figsize=(10,6))
    # plot things...
    fig1, ax1 = plt.subplots(figsize=(12,6))
    sns.barplot(x='hour', y='avg_duration_minutes', data=temp_df, palette='viridis', ax=ax1)
    ax1.set_xlabel('Hour (24H Format)')
    ax1.set_ylabel('Average Bus Travel Times (Minutes)')
    ax1.set_title('Bus Travel Time by Hour (Average in Minutes)')
    bar_chart = fig1

    # --- Violin Plot with Box Plot inside ---
    fig2, ax2 = plt.subplots(figsize=(12,6))
    sns.violinplot(x='hour', y='duration_minutes', data=df, inner="box", palette=palette, ax=ax2)
    ax2.axhline(overall_avg, color='black', linestyle='--', linewidth=1.5, label=f'Overall Average: {overall_avg:.2f}')
    ax2.set_xlabel("Hour (24H format)")
    ax2.set_ylabel("Duration (minutes)")
    ax2.set_title("Travel Duration Spread Across Hours")
    violin_plot = fig2


    plt.figure(figsize=(12, 6))
    sns.boxplot(x='hour', y='duration_minutes', data=df, palette="Set3")
    plt.axhline(overall_avg, color='black', linestyle='--', linewidth=1.5, label=f'Overall Average: {overall_avg:.2f}')
    plt.title("Box Plot of Duration Minutes by Hour")
    plt.xlabel("Hour")
    plt.ylabel("Duration (minutes)")
    plt.show()

    return anova_result.statistic,anova_result.pvalue,bar_chart,violin_plot

col3,col4 = st.columns([1,3])
with col3 :
   st.image("rapidkl.png")
with col4 :
   st.write(" ")
st.markdown("---")
st.subheader("Station To Station Analysis")
unique_routes = routes_df["route_long_name"].unique()
if "T815" in unique_routes:
    unique_routes = np.insert(np.delete(unique_routes, np.where(unique_routes == "T815")), 0, "T815")
unique_days = ["Weekdays","Weekend"]
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

df = add_connection_hour_column(df)


build_network_graph(df,st.session_state.route)

with open("mygraph1.html", "r", encoding="utf-8") as f:
    html_data = f.read()

#Display the PyVis graph in Streamlit
components.html(html_data, height=500, scrolling=True)


col1, col2 = st.columns(2)

with col1:
    
    unique_connections = df["connection"].unique()
    st.session_state.connection = st.selectbox("Select A route between two stations",unique_connections)
with col2:
    st.markdown("<h6 style='margin-bottom:10px;'>Anova Statistics</h6>",unsafe_allow_html=True)
    f_stat, p_value, bar_chart, violin_plot = distribution_analysis_each_connection(st.session_state.connection,df)
    st.write("F-Statistics :",f_stat)
    st.write("P-Value :",p_value)
    if p_value < 0.05:
        st.write("The travel duration across these two stations are affected by time")
    else:
        st.write("The travel duration across these two stations are not affected by time")

st.divider()
st.subheader("Visual Analysis")
st.pyplot(bar_chart)
st.pyplot(violin_plot)
    

    









