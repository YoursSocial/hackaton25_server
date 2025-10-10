import plotly.express as px
import pandas as pd
import dash
from dash import dcc
import dash_bootstrap_components as dbc
import psycopg2 as ps
import app.dashboard.credentials as credentials


dash.register_page(__name__, path_template="/sensor_details/<name>")

# threshold under which percent traces are not shown in fig_sensor & fig_command
threshold = 0.2

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
fig_style_line = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    xaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False, title="Time"),
    yaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False, title="Sum"))
fig_style_pie = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    xaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    yaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    legend=dict(
        x=1.1,
        y=1,
        xanchor="left",
        yanchor="top")
)
card_style = {'height': '96vh'}
card_class = "text-white shadow p-0 rounded w-100"
graph_config = {"displayModeBar": "hover"}


def layout(name=None, **kwargs):
    db_user, db_password, user, password = credentials.get()
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()

    # get signal data
    cur.execute("""SELECT s.timestamp, s.count, j.job_name 
                FROM signal as s, sensor_job as j 
                WHERE j.id = s.id 
                AND j.sensor_name = %s 
                ORDER BY s.timestamp""", (name,))
    df_signal = pd.DataFrame(cur.fetchall(), columns=['timestamp', 'count', 'job_name'])
    df_signal["timestamp"] = pd.to_datetime(df_signal["timestamp"], unit='s')

    df_signal['sum'] = df_signal['count'].cumsum()

    # get packet data
    cur.execute("""SELECT p.type, p.count 
                    FROM packets as p, sensor_job as j 
                    WHERE j.id = p.id 
                    AND j.sensor_name = %s""", (name,))
    df_packets = pd.DataFrame(cur.fetchall(), columns=['type', 'count'])
    df_packets = df_packets.groupby('type')['count'].sum().reset_index()

    # add percent and label cols to display only the traces with percentages bigger than threshold
    df_packets['percent'] = df_packets['count'] / df_packets['count'].sum() * 100
    df_packets['label'] = df_packets['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")

    cur.close()
    conn.close()

    # define all charts
    packetPie = px.pie(df_packets,
                       names='type',
                       values='count',
                       title='Distribution of Packets')
    packetBar = px.bar(df_packets,
                       x='type',
                       y='count',
                       title='Count of Packets',
                       labels={'count': 'Count', 'type': 'Type'})
    packetLine = px.line(df_signal,
                         x='timestamp',
                         y='sum',
                         title='Packets over Time', )

    # chart styles
    packetPie.update_layout(fig_style_pie)
    packetBar.update_layout(fig_style)
    packetLine.update_layout(fig_style_line)

    packetPie.update_traces(
        hovertemplate="Type: %{label}<br>"
                      "Count: %{value}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_packets['percent']
        ]
    )
    packetBar.update_traces(
        hovertemplate="Type: %{x}<br>"
                      "Count: %{y}<extra></extra>"
    )
    packetLine.update_traces(
        hovertemplate="Timestamp: %{x}<br>"
                      "Sum: %{y}<extra></extra>"
    )

    # layout of site
    return dbc.Container([
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetLine",
                            figure=packetLine,
                            config=graph_config
                        )],
                        className=card_class,
                        style=card_style),
                    width=4),
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetPie",
                            figure=packetPie,
                            config=graph_config
                        )],
                        className=card_class,
                        style=card_style)
                    , width=4),
                dbc.Col(
                    dbc.Card([
                        dcc.Graph(
                            id="packetBar",
                            figure=packetBar,
                            config=graph_config
                        )],
                        className=card_class,
                        style=card_style)
                    , width=4)
            ],
            className="pb-3")
        ], fluid=True)
