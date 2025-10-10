from io import StringIO
import plotly.express as px
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, callback, ALL, ctx
import dash_bootstrap_components as dbc
import psycopg2 as ps
import app.dashboard.credentials as credentials


dash.register_page(__name__, path_template="/job_details/<name>")

##
# Styles
##

line_color = "gray"
background_color = "#f5f5f5"
font_color = "black"
zeroline_color = "darkgray"

fig_style = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    xaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    yaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False))
fig_frame_style = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    xaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    yaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1, xanchor="right", x=1.2))
fig_pie_style = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    legend=dict(
        x=1.1,
        y=1,
        xanchor="left",
        yanchor="top"))
card_class = "text-white shadow p-0 rounded w-100"
list_style = {
    "width": "17%",
    "border-top-left-radius": "0",
    "border-top-right-radius": "0",
    "border-bottom-left-radius": "0",
    "border-bottom-right-radius": "0"}
packet_line_labels = {'sum': 'Sum', 'timestamp': 'Date'}
packet_labels = {'type': 'Type', 'count': 'Count'}
signal_labels = {'value': 'Value', 'timestamp': 'Date'}
graph_config = {"displayModeBar": "hover"}

legend_title=dict(text="Metric")


##
# Functions
##

def set_title(is_open):
    if is_open:
        return "Show Filter"
    return "Hide Filter"


# returns button group belonging to input sensor
def create_sensor_buttongroup(sensor):
    return dbc.ListGroup(
        [
            dbc.ListGroupItem(sensor,
                              style={"width": "49%"}),
            dbc.ListGroupItem("Data",
                              id={"type": "data", "sensor": sensor},
                              n_clicks=0,
                              action=True,
                              style=list_style),
            dbc.ListGroupItem("Stderr",
                              id={"type": "stderr", "sensor": sensor},
                              n_clicks=0,
                              action=True,
                              style=list_style,
                              ),
            dbc.ListGroupItem("Config",
                              id={"type": "config", "sensor": sensor},
                              n_clicks=0,
                              action=True,
                              style=list_style,
                              )
        ],
        horizontal=True,
        class_name="w-100")


# returns list of buttongroups belonging to sensors and button to show all sensors
def draw_sensor_buttons(sensors):
    buttonList = []
    for s in sensors:
        buttonList.append(create_sensor_buttongroup(s))

    buttonList.append(
        dbc.ListGroup(
            dbc.ListGroupItem("Show data from all sensors",
                              id="allData",
                              n_clicks=0,
                              action=True,
                              color="dark",
                              style={"border-top-left-radius": "0", "border-top-right-radius": "0"},
                              class_name="text-center w-100 dark")))
    return buttonList


def layout(name=None, **kwargs):
    db_user, db_password, user, password = credentials.get()
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()

    ###
    # Layouts depending on command type
    ###

    cur.execute("""SELECT command 
                FROM jobs 
                WHERE name = %s""", (name,))
    command = cur.fetchone()

    if command is None:
        cur.close()
        conn.close()
        return html.Div(
            dbc.ListGroup(
                [dbc.ListGroupItem("No command found for this job. "
                                   "You may need to wait up to 24h if job was recently created.", color="dark")],
                class_name="w-25 text-center"))

    command = command[0]

    if any(i in command for i in ["log", "config", "restart", "reset", "reboot", "status"]):
        return html.Div(
            dbc.ListGroup(
                [dbc.ListGroupItem(f"No data to visualize for command {command}", color="dark")],
                class_name="w-25 text-center"))

    elif "globestar" in command:
        cur.close()
        conn.close()
        return html.Div(
            dbc.ListGroup(
                [dbc.ListGroupItem("Globestar visualization not yet implemented", color="dark")],
                class_name="w-25 text-center"))

    elif "starlink" in command:
        cur.close()
        conn.close()
        return html.Div(
            dbc.ListGroup(
                [dbc.ListGroupItem("Starlink visualization not yet implemented", color="dark")],
                class_name="w-25 text-center"))

    elif "iridium" in command:
        cur.execute("""SELECT sensor_name 
                    FROM sensor_job 
                    WHERE job_name = %s""", (name,))
        sensors = [i[0] for i in cur.fetchall()]

        if len(sensors) == 0:
            cur.close()
            conn.close()
            return html.Div(
                dbc.ListGroup(
                    [dbc.ListGroupItem("No sensor data for this job. "
                                       "You may need to wait up to 24h if data was recently uploaded.", color="dark")],
                    class_name="w-25 text-center"))

        # get configration of all sensors
        cur.execute("""SELECT sensor_name, sample_rate, center_freq, bandwidth, gain, if_gain, bb_gain, decimation 
                        FROM sensor_job 
                        WHERE job_name = %s""", (name,))
        df_conf = pd.DataFrame(cur.fetchall(), columns=['sensor_name', 'sample_rate', 'center_freq', 'bandwidth',
                                                        'gain', 'if_gain', 'bb_gain', 'decimation'])

        # get stderr data of all sensors
        cur.execute("""SELECT s.timestamp, s.i, s.o, s.ok_s, s.ok, j.sensor_name 
                    FROM stderr as s, sensor_job as j 
                    WHERE s.id = j.id 
                    AND j.job_name = %s
                    ORDER BY timestamp, ok""", (name,))
        df_stderr = pd.DataFrame(cur.fetchall(), columns=['timestamp', 'i', 'o', 'ok_s', 'ok', 'sensor_name'])
        df_stderr["timestamp"] = pd.to_datetime(df_stderr["timestamp"], unit='s')

        # get signal data of all sensors
        cur.execute("""SELECT j.sensor_name, s.timestamp, s.signal_level, s.background_noise, s.snr, s.count 
                    FROM signal as s, sensor_job as j 
                    WHERE s.id = j.id 
                    AND j.job_name = %s 
                    ORDER BY s.timestamp ASC""", (name,))
        df_signal = pd.DataFrame(cur.fetchall(),
                                 columns=['sensor_name', 'timestamp', 'signal_level', 'background_noise', 'snr',
                                          'count'])
        df_signal["timestamp"] = pd.to_datetime(df_signal["timestamp"], unit='s')

        # calculate cumulative sum without sensor names to show data for all sensors
        df_signal_sum = df_signal.drop(columns=['sensor_name'])
        df_signal_sum['sum'] = df_signal_sum['count'].cumsum()

        # get packet data of all sensors
        cur.execute("""SELECT s.sensor_name, p.type, p.count 
                    FROM packets as p, sensor_job as s 
                    WHERE s.id = p.id
                    AND s.job_name = %s""", (name,))
        df_packets = pd.DataFrame(cur.fetchall(), columns=['sensor_name', 'type', 'count'])

        # calculate sum of packet types for all sensors
        df_packets_sum = df_packets.drop(columns=['sensor_name']).groupby('type')
        df_packets_sum = df_packets_sum['count'].sum().reset_index()

        cur.close()
        conn.close()

        ###
        # Dash
        ###

        # define all charts
        packetLine = px.line(df_signal_sum,
                             x="timestamp",
                             y='sum',
                             title='Packets over Time',
                             labels=packet_line_labels)
        packetPie = px.pie(df_packets_sum,
                           names='type',
                           values='count',
                           title='Distribution of Packets',
                           labels=packet_labels)
        packetBar = px.bar(df_packets_sum,
                           x='type',
                           y='count',
                           title='Count of Packets',
                           labels=packet_labels)
        signalLine = None

        # chart styles
        packetLine.update_layout(fig_style)
        packetPie.update_layout(fig_pie_style)
        packetBar.update_layout(fig_style)

        packetLine.update_traces(
            hovertemplate="Date: %{x}<br>"
                          "Sum: %{y:,}<extra></extra>"
        )
        packetBar.update_traces(
            hovertemplate="Type: %{x}<br>"
                          "Count: %{y:,}<extra></extra>"
        )
        packetPie.update_traces(
            hovertemplate="Type: %{label}<br>"
                          "Count: %{value:,}<extra></extra>"
        )

        # layout of site
        return dbc.Container([
            dcc.Location(id="url"),
            dcc.Store(id="stderr", data=df_stderr.to_json(orient='split')),
            dcc.Store(id="signal", data=df_signal.to_json(orient='split')),
            dcc.Store(id="signal_sum", data=df_signal_sum.to_json(orient='split')),
            dcc.Store(id="packets", data=df_packets.to_json(orient='split')),
            dcc.Store(id="packets_sum", data=df_packets_sum.to_json(orient='split')),
            dcc.Store(id="conf", data=df_conf.to_json(orient='split')),
            dbc.Row([
                # buttons
                dbc.Col(
                    dbc.Card([
                        dbc.Button("Show Filter",
                                   id="collapse-button",
                                   className="m-0 w-100",
                                   color="primary",
                                   n_clicks=0
                                   ),
                        dbc.Collapse(id="collapse",
                                     is_open=False,
                                     children=draw_sensor_buttons(sensors))
                    ], className=card_class + "h-100"),
                    width=4),
                # data info div
                dbc.Col(
                    html.Div(style={"position": "sticky",
                                    "top": 0,
                                    "background-color": background_color,
                                    "border-radius": "0.25rem"},
                             children=[
                                 dbc.Card([
                                     html.Div(
                                         html.H2(id="info",
                                             children=["Data for all sensors"],
                                             style={"color": font_color, "textAlign": "center"}),
                                        style={"height": "100%",
                                               "background-color": background_color,
                                               "padding": "12px",
                                               "paddingLeft": "7rem"})
                                 ], className=card_class)]),
                    width=8,
                    className="text-white"
                ),
            ], className="mb-3", justify="end"),
            # graphs
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetLine",
                            figure=packetLine,
                            config=graph_config
                        )],
                        id="line_card",
                        className=card_class),
                        style={"display": "block"},
                        width=4),
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetPie",
                            figure=packetPie,
                            config=graph_config
                        )],
                        id="pie_card",
                        className=card_class),
                        style={"display": "block"},
                        width=4),
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetBar",
                            figure=packetBar,
                            config=graph_config
                        )],
                        id="bar_card",
                        className=card_class),
                        style={"display": "block"},
                        width=4)
            ], className="mb-0"),
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="signalLine",
                            figure=signalLine,
                            className="margin-0",
                            config=graph_config)],
                        className=card_class,
                        id="signal_card",
                        style={"display": "none"}),
                    width=8,
                    align="center",
                    className="mx-auto")
            ], className="mt-3 mb-3")
        ],
        fluid=True
        )

    # command unknown
    else:
        cur.close()
        conn.close()
        return html.Div(
            dbc.ListGroup(
                [dbc.ListGroupItem(f"Command {command} unknown", color="warning")],
                class_name="w-25 text-center"))


##
# Iridium callbacks
##

@callback(
    [
        Output("collapse", "is_open"),
        Output("collapse-button", "children")
    ],
    [Input("collapse-button", "n_clicks")],
    [State("collapse", "is_open")],
    prevent_initial_callback=True
)
def toggle_collapse(n, is_open):
    if n:
        return not is_open, set_title(is_open)
    return is_open, "Show Filter"


@callback(
    [
        Output('packetLine', 'figure', allow_duplicate=True),
        Output('packetPie', 'figure', allow_duplicate=True),
        Output('packetBar', 'figure', allow_duplicate=True),
        Output('info', 'children', allow_duplicate=True),
        Output('line_card', 'style', allow_duplicate=True),
        Output('pie_card', 'style', allow_duplicate=True),
        Output('bar_card', 'style', allow_duplicate=True),
        Output('signal_card', 'style', allow_duplicate=True)
    ],
    [
        Input('allData', 'n_clicks'),
        State("signal_sum", "data"),
        State("packets_sum", "data"),
    ],
    prevent_initial_call=True
)
def show_all_data(x, signal_sum, packets_sum):
    df_signal_sum = pd.read_json(StringIO(signal_sum), orient='split')
    df_packets_sum = pd.read_json(StringIO(packets_sum), orient='split')

    info = "Data for all sensors"
    display = {"display": "block"}

    packetLine = px.line(df_signal_sum,
                         x='timestamp',
                         y='sum',
                         title='Packets over Time',
                         labels=packet_line_labels)
    packetPie = px.pie(df_packets_sum,
                       names='type',
                       values='count',
                       title='Distribution of Packets',
                       labels=packet_labels)
    packetBar = px.bar(df_packets_sum,
                       x='type',
                       y='count',
                       title='Count of Packets',
                       labels=packet_labels)

    packetLine.update_layout(fig_style)
    packetPie.update_layout(fig_pie_style)
    packetBar.update_layout(fig_style)

    packetLine.update_traces(
        hovertemplate="Date: %{x}<br>"
                      "Sum: %{y:,}<extra></extra>"
    )
    packetBar.update_traces(
        hovertemplate="Type: %{x}<br>"
                      "Count: %{y:,}<extra></extra>"
    )
    packetPie.update_traces(
        hovertemplate="Type: %{label}<br>"
                      "Count: %{value:,}<extra></extra>"
    )

    return packetLine, packetPie, packetBar, info, display, display, display, {"display": "none"}



@callback(
    [
        Output('packetLine', 'figure', allow_duplicate=True),
        Output('packetPie', 'figure', allow_duplicate=True),
        Output('packetBar', 'figure', allow_duplicate=True),
        Output('info', 'children', allow_duplicate=True),
        Output('line_card', 'style', allow_duplicate=True),
        Output('pie_card', 'style', allow_duplicate=True),
        Output('bar_card', 'style', allow_duplicate=True),
        Output('signal_card', 'style', allow_duplicate=True),
        Output('signal_card', 'children', allow_duplicate=True)
    ],
    [
        # use pattern matching callback with keyword ALL to trigger callback from all buttons that have type and sensor
        # in id
        Input({"type": "data", "sensor": ALL}, 'n_clicks'),
        State("signal", "data"),
        State("packets", "data"),
    ],
    prevent_initial_call=True
)
def data_button(x, signal, packets):
    # determine which sensor button was clicked by context
    sensor = ctx.triggered_id.sensor

    df_signal = pd.read_json(StringIO(signal), orient='split')
    df_packets = pd.read_json(StringIO(packets), orient='split')

    info = "Data for " + sensor
    display = {"display": "block"}

    # filter all dataframes by current sensor name
    df_packetCount = df_packets[df_packets.sensor_name == sensor]
    df_signal_sensor = df_signal[df_signal.sensor_name == sensor].sort_values(by='timestamp')
    df_signal_sensor['sum'] = df_signal_sensor['count'].cumsum()

    packetLine = px.line(df_signal_sensor,
                         x='timestamp',
                         y='sum',
                         title='Packets over Time',
                         labels=packet_line_labels)
    packetPie = px.pie(df_packetCount,
                       names='type',
                       values='count',
                       title='Distribution of Packets',
                       labels=packet_labels)
    packetBar = px.bar(df_packetCount,
                       x='type',
                       y='count',
                       title='Count of Packets',
                       labels=packet_labels)
    signalLine = px.line(df_signal_sensor,
                         x='timestamp',
                         y=['signal_level', 'background_noise', 'snr'],
                         title='Signal Data',
                         labels={"timestamp": "Date", "value": "dB", "variable": "Variables"})
    graph = dcc.Graph(
        id="signalLine",
        figure=signalLine,
        className="margin-0",
        config=graph_config
    )
    packetLine.update_layout(fig_style)
    packetPie.update_layout(fig_pie_style)
    packetBar.update_layout(fig_style)
    signalLine.update_layout(fig_style)

    for trace in signalLine.data:
        trace.name = trace.name.replace("_", " ").upper()

    packetLine.update_traces(
        hovertemplate="Date: %{x}<br>"
                      "Sum: %{y:,}<extra></extra>"
    )
    packetBar.update_traces(
        hovertemplate="Type: %{x}<br>"
                      "Count: %{y:,}<extra></extra>"
    )
    packetPie.update_traces(
        hovertemplate="Type: %{label}<br>"
                      "Count: %{value:,}<extra></extra>"
    )
    signalLine.update_traces(
        hovertemplate="Variable: %{fullData.name}<br>"
                      "Date: %{x}<br>"
                      "dB: %{y}<extra></extra>"
    )

    return packetLine, packetPie, packetBar, info, display, display, display, display, graph

@callback(
    [
        Output('packetLine', 'figure', allow_duplicate=True),
        Output('packetPie', 'figure', allow_duplicate=True),
        Output('packetBar', 'figure', allow_duplicate=True),
        Output('info', 'children', allow_duplicate=True),
        Output('line_card', 'style', allow_duplicate=True),
        Output('pie_card', 'style', allow_duplicate=True),
        Output('bar_card', 'style', allow_duplicate=True),
        Output('signal_card', 'style', allow_duplicate=True)
    ],
    [
        # use pattern matching callback with keyword ALL to trigger callback from all buttons that have type and sensor
        # in id
        Input({"type": "stderr", "sensor": ALL}, 'n_clicks'),
        State("stderr", "data"),
    ],
    prevent_initial_call=True
)
def stderr_button(x, stderr):
    # determine which sensor button was clicked by context
    sensor = ctx.triggered_id.sensor

    df_stderr = pd.read_json(StringIO(stderr), orient='split')

    info = "Stderr for " + sensor
    display = {"display": "block"}

    # filter dataframe by current sensor name
    df_sensor = df_stderr[df_stderr.sensor_name == sensor]

    lineBurst = px.line(df_sensor,
                        x='timestamp',
                        y='i',
                        title='Bursts',
                        labels={"timestamp": "Date", "i": "Avg num of Bursts / s"})
    lineFrame = px.line(df_sensor,
                        x='timestamp',
                        y=['o', 'ok_s'],
                        title='Frames',
                        labels={"timestamp": "Date", "value": "Avg num / s", "variable": "Variables"})
    lineOk = px.line(df_sensor,
                     x='timestamp',
                     y='ok',
                     title='Sum of OK Frames',
                     labels={"timestamp": "Date", "variable": "Variables", "ok": "Sum"})
    name_map = {
        "o": "Number of frames",
        "ok_s": "Number of OK frames"
    }
    for trace in lineFrame.data:
        trace.name = name_map.get(trace.name, trace.name)

    lineBurst.update_layout(fig_style)
    lineFrame.update_layout(fig_frame_style)
    lineOk.update_layout(fig_style)

    lineBurst.update_traces(
        hovertemplate="Date: %{x}<br>"
                      "Avg num of Bursts: %{y:,}/s<extra></extra>"
    )
    lineOk.update_traces(
        hovertemplate="Date: %{x}<br>"
                      "Sum: %{y:,}<extra></extra>"
    )
    lineFrame.update_traces(
        hovertemplate="Variable: %{fullData.name}<br>"
                      "Date: %{x}<br>"
                      "Avg num: %{y:,}/s<extra></extra>"
    )

    return lineBurst, lineFrame, lineOk, info, display, display, display, {"display": "none"}

@callback(
    [
        Output('info', 'children', allow_duplicate=True),
        Output('line_card', 'style', allow_duplicate=True),
        Output('pie_card', 'style', allow_duplicate=True),
        Output('bar_card', 'style', allow_duplicate=True),
        Output('signal_card', 'style', allow_duplicate=True),
        Output('signal_card', 'children', allow_duplicate=True)
    ],
    [
        # use pattern matching callback with keyword ALL to trigger callback from all buttons that have type and sensor
        # in id
        Input({"type": "config", "sensor": ALL}, 'n_clicks'),
        State("conf", "data"),
    ],
    prevent_initial_call=True
)
def conf_button(x, conf):
    # determine which sensor button was clicked by context
    sensor = ctx.triggered_id.sensor

    df_conf = pd.read_json(StringIO(conf), orient='split')

    not_display = {"display": "none"}
    info = "Configuration for " + sensor
    style = {"display": "block", "width": "50%", "float": "right"}

    # filter dataframe by current sensor name
    df_conf_sensor = df_conf[df_conf.sensor_name == sensor]

    card = dbc.Card(
        dbc.ListGroup([
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("Sample Rate: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.sample_rate.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("Center Frequency: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.center_freq.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("Bandwidth: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.bandwidth.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("Gain: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.gain.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("IF Gain: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.if_gain.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("BB Gain: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.bb_gain.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"})),
            dbc.ListGroupItem(
                html.Div([
                    html.Strong("Decimation: ", style={"flex": "2"}),
                    html.Span(str(df_conf_sensor.decimation.item()), style={"flex": "1"})
                ],
                    style={"display": "flex"}))
        ],
            flush=True
        ),
        className=card_class
    )

    return info, not_display, not_display, not_display, style, card