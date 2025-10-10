from io import StringIO
import plotly.express as px
import pandas as pd
import dash
from dash import dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
from flask import request, jsonify
import requests
import plotly.colors as pc


dash.register_page(__name__, path="/job_tracker")

##
# Constants
##

# show pending jobs in fig_status
showPending = False
# threshold under which percent traces are not shown in fig_sensor & fig_command
threshold = 0.2
# list of all allowed command types
commands = ["get_full_status", "iridium_sniffing", "get_logs", "reboot", "get_status", "get_sys_config",
            "set_sys_config", "reset"]

##
# Styles
##

line_color = "gray"
background_color = "#f5f5f5"
font_color = "black"
zeroline_color = "darkgray"

fig_style = dict(
    showlegend=False,
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
)
card_class = "text-white shadow p-0 rounded w-100"
card_style = {"height": "100vh", "overflowY": "auto", "overflowX": "hidden", "background-color": background_color}
checklist_style = dict(color=font_color)
graph_config = {"displayModeBar": "hover"}


##
# Functions
##

# returns dataframe where every row contains at least one of the provided sensors as well as rows with no sensors
def filterSensors(df, sensors):
    # keep jobs without sensors
    sensors.append('nan')
    df = df.explode('sensors').astype(str)
    df = df[df.sensors.isin(sensors)]
    return df


# return dataframe [[attribute -> count], [attribute -> count] ...]
def count_attribute(df, attribute, rename):
    df = df.explode(attribute)
    df = df.groupby(attribute).count()
    df = df.reset_index().rename(columns={rename: 'count'})
    df = df.sort_values("count", ascending=False)
    return df


def layout(**kwargs):
    # get data for all jobs
    # TODO this is a workaround, get fixedjobs directly from postgresDB in the future
    url = "http://127.0.0.1:8000/fixedjobs/"
    cookies = request.cookies
    response = requests.get(url, cookies=cookies)
    if response.status_code != 200:
        return jsonify({"status": "Unauthorized"}), response.status_code
    data = response.json()
    df_jobs = pd.json_normalize(data.get("data", []), max_level=0)
    df_jobs = df_jobs.drop(columns=["arguments", "states", "start_time", "end_time", "id"])

    ###
    # Data handling
    ###

    if not showPending:
        df_jobs = df_jobs[df_jobs.status.isin(['finished', 'failed', 'running'])]

    # show all commands not in the allowed list with * symbol
    df_jobs["command"] = df_jobs["command"].where(df_jobs["command"].isin(commands), "*")

    # count sensors attribute (explode sensors because sensors is a list)
    df_sensor_count = count_attribute(df_jobs, "sensors", "name")
    # add percent and label cols to display only the traces with percentages bigger than threshold
    df_sensor_count['percent'] = df_sensor_count['count'] / df_sensor_count['count'].sum() * 100
    df_sensor_count['label'] = df_sensor_count['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")

    df_command_count = count_attribute(df_jobs, "command", "name")
    # add percent and label cols to display only the traces with percentages bigger than threshold
    df_command_count['percent'] = df_command_count['count'] / df_command_count['count'].sum() * 100
    df_command_count['label'] = df_command_count['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")

    # give each sensor a discrete color
    values = df_sensor_count.sensors
    palette = pc.qualitative.Plotly
    color_map = {val: palette[i % len(palette)] for i, val in enumerate(values)}

    ###
    # Dash
    ###

    # define all charts
    fig_status = px.pie(df_jobs,
                        names='status',
                        color='status',
                        color_discrete_map={
                            "failed": "#a80049",
                            "running": "#056b20",
                            "finished": "black",
                            "pending": "#b87d00"},
                        title='By Status',
                        )
    fig_sensor = px.pie(df_sensor_count,
                        names='sensors',
                        values='count',
                        title='By Sensor',
                        color_discrete_map=color_map,
                        color="sensors")
    fig_command = px.pie(df_command_count,
                         names='command',
                         values='count',
                         title='By Command')

    # chart styles
    fig_status.update_layout(fig_style)
    fig_sensor.update_layout(fig_style)
    fig_command.update_layout(fig_style)

    fig_status.update_traces(
        hovertemplate="Status: %{label}<br>"
                      "Count: %{value:,}<extra></extra>",
    )
    fig_sensor.update_traces(
        hovertemplate="Sensor: %{label}<br>"
                      "Count: %{value:,}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_sensor_count['percent']
        ]
    )
    fig_command.update_traces(
        hovertemplate="Command: %{label}<br>"
                      "Count: %{value:,}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_command_count['percent']
        ]
    )

    # layout of site
    return dbc.Container([
        dcc.Store(id="jobs", data=df_jobs.to_json(orient='split')),
        dcc.Store(id="color_map", data=color_map),
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.Row([
                        dbc.Col([
                            # Pie chart of Status
                            dcc.Graph(
                            id='statusPie',
                            figure=fig_status,
                            config=graph_config
                            )
                        ])
                    ], style={"height": "80vh"}
                    ),
                    dbc.Row([
                        dbc.Col([
                            # Checklist of Status
                            dbc.Checklist(
                                id='statusCheck',
                                options=df_jobs['status'].unique(),
                                value=df_jobs['status'].unique(),
                                inline=True,
                                style=checklist_style
                            )])],
                        justify="center",
                    ),

                    ], className=card_class
                    , style=card_style), width=3),
            dbc.Col(
                dbc.Card([
                    dbc.Row([
                        dbc.Col([
                            # Pie chart of Sensors
                            dcc.Graph(
                                id='sensorPie',
                                figure=fig_sensor,
                                config=graph_config
                            )
                        ], width=7),
                        dbc.Col([
                            # Checkbox of Sensors
                            dbc.Checklist(
                                id='sensorCheck',
                                options=df_sensor_count['sensors'].unique(),
                                value=df_sensor_count['sensors'].unique(),
                                style=checklist_style
                            )
                        ])
                    ], align="center")
                    ], className=card_class
                    , style=card_style)
                ),
            dbc.Col(
                dbc.Card([
                    dbc.Row([
                        dbc.Col([
                            # Pie chart of Command
                            dcc.Graph(
                                id='commandPie',
                                figure=fig_command,
                                config=graph_config
                            )
                        ], width=8),
                        dbc.Col([
                            # Checkbox of Command
                            dbc.Checklist(
                                id='commandCheck',
                                options=df_jobs['command'].unique(),
                                value=df_jobs['command'].unique(),
                                style=checklist_style
                            )
                        ])
                    ], align="center")
                    ], className=card_class
                    , style=card_style
                ), width=4
                )
            ], className="mb-0 w-100"
        )
    ], fluid=True, style={"height": "100vh", "overflow": "hidden"})


# If any of the associated Checkboxes for the Pie Charts get updated, filter Dataframe and update all PieCharts
@callback(
    [
        Output('statusPie', 'figure'),
        Output('sensorPie', 'figure'),
        Output('commandPie', 'figure'),
    ],
    [
        State("jobs", "data"),
        State("color_map", "data"),
        Input('statusCheck', 'value'),
        Input('sensorCheck', 'value'),
        Input('commandCheck', 'value'),
    ]
)
def updateCharts(jobs, color_map, status, sensor, command):
    df_jobs = pd.read_json(StringIO(jobs), orient='split')

    # filter all dataframes by active values of checkboxes
    df_updated = df_jobs[df_jobs.status.isin(status)]
    df_updated = df_updated[df_updated.command.isin(command)]
    df_updated = filterSensors(df_updated, sensor)

    # to filter sensors the col is exploded because it's a list, so we only keep rows with unique job_name for StatusPie
    # and CommandPie
    df_updated_unique = df_updated.copy().drop_duplicates(subset=["name"], keep="first")

    # count sensors attribute (explode sensors because sensors is a list)
    df_updatedSensorCount = count_attribute(df_updated, "sensors", "name")
    # add percent and label cols to display only the traces with percentages bigger than threshold
    df_updatedSensorCount['percent'] = df_updatedSensorCount['count'] / df_updatedSensorCount['count'].sum() * 100
    df_updatedSensorCount['label'] = df_updatedSensorCount['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")
    df_updatedCommandCount = count_attribute(df_updated_unique, "command", "name")
    df_updatedCommandCount['percent'] = df_updatedCommandCount['count'] / df_updatedCommandCount['count'].sum() * 100
    df_updatedCommandCount['label'] = df_updatedCommandCount['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")

    updatedStatusPie = px.pie(df_updated_unique,
                              names='status',
                              color='status',
                              color_discrete_map={
                                  "failed": "#a80049",
                                  "running": "#056b20",
                                  "finished": "black",
                                  "pending": "#b87d00"},
                              title='By Status',
                              labels={'status': 'Status'})
    updatedSensorsPie = px.pie(df_updatedSensorCount,
                               names='sensors',
                               values='count',
                               title='By Sensors',
                               labels={'sensors': 'Sensor'},
                               color="sensors",
                               color_discrete_map=color_map)
    updatedCommandPie = px.pie(df_updatedCommandCount,
                               names='command',
                               values='count',
                               title='By Command',
                               labels={'command': 'Command'})

    updatedStatusPie.update_layout(fig_style)
    updatedSensorsPie.update_layout(fig_style)
    updatedCommandPie.update_layout(fig_style)

    updatedStatusPie.update_traces(
        hovertemplate="Status: %{label}<br>"
                      "Count: %{value:,}<extra></extra>",
    )
    updatedSensorsPie.update_traces(
        hovertemplate="Sensor: %{label}<br>"
                      "Count: %{value:,}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_updatedSensorCount['percent']
        ]
    )
    updatedCommandPie.update_traces(
        hovertemplate="Command: %{label}<br>"
                      "Count: %{value:,}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_updatedCommandCount['percent']
        ]
    )

    return updatedStatusPie, updatedSensorsPie, updatedCommandPie
