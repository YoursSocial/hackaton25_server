import plotly.express as px
import pandas as pd
import dash
from dash import dcc
import dash_bootstrap_components as dbc
import psycopg2 as ps
import app.dashboard.credentials as credentials


dash.register_page(__name__, path_template="/public_page")

# threshold under which percent traces are not shown in packetPie
threshold = 0.2


##
# Styles
##

line_color = "gray"
background_color = "#f5f5f5"
font_color = "black"
zeroline_color = "darkgray"

card_style = {
    "border-radius": "0.25rem",
    "width": "100%",
    "height": "31vh",
    "color": background_color,
    "boxShadow": "0 .5rem 1rem rgba(0,0,0,.15)",
    "box-sizing": "border-box"
}
fig_style = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    xaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False),
    yaxis=dict(showline=True, showgrid=False, linecolor=line_color, zeroline=False))
fig_pie_style = dict(
    plot_bgcolor=background_color,
    paper_bgcolor=background_color,
    font_color=font_color,
    legend=dict(
        x=1.3,
        y=1,
        xanchor="left",
        yanchor="top")
    )
graph_config = {"displayModeBar": "hover"}


def layout(**kwargs):
    db_user, db_password, user, password = credentials.get()
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()

    cur.execute("""SELECT s.timestamp, s.signal_level, s.background_noise, s.snr, s.count 
                FROM signal as s, sensor_job as j 
                WHERE s.id = j.id 
                AND j.job_name = %s""", ("public_page", ))

    df_signal = pd.DataFrame(cur.fetchall(),
                             columns=['timestamp', 'signal_level', 'background_noise', 'snr',
                                      'count'])
    df_signal["timestamp"] = pd.to_datetime(df_signal["timestamp"], unit='s')

    df_signal_sum = df_signal.sort_values(by='timestamp').copy()
    df_signal_sum['sum'] = df_signal_sum['count'].cumsum()

    cur.execute("""SELECT p.type, p.count 
                FROM packets as p, sensor_job as s
                WHERE p.id = s.id 
                AND s.job_name = %s""", ("public_page", ))
    df_packets = pd.DataFrame(cur.fetchall(), columns=['type', 'count'])

    cur.close()
    conn.close()

    # add percent and label cols to display only the traces with percentages bigger than threshold
    df_packets['percent'] = df_packets['count'] / df_packets['count'].sum() * 100
    df_packets['label'] = df_packets['percent'].apply(lambda x: f"{x:.1f}%" if x >= threshold else "")

    # define all charts
    packetLine = px.line(df_signal_sum,
                         x="timestamp",
                         y='sum',
                         title='Packets over Time',
                         labels={'sum': 'Sum', 'timestamp': 'Date'})
    packetPie = px.pie(df_packets,
                       names='type',
                       values='count',
                       title='Distribution of Packets')
    packetBar = px.bar(df_packets,
                       x='type',
                       y='count',
                       title='Count of Packets',
                       labels={'count': 'Count', 'type': 'Type'})

    # chart styles
    packetLine.update_layout(fig_style)
    packetPie.update_layout(fig_pie_style)
    packetBar.update_layout(fig_style)

    packetPie.update_traces(
        hovertemplate="Type: %{label}<br>"
                      "Count: %{value}<br>"
                      "Percentage: %{percent}<extra></extra>",
        texttemplate=[
            f"{p:.1f}%" if p >= threshold else "" for p in df_packets['percent']
        ]
    )
    packetLine.update_traces(
        hovertemplate="Date: %{x}<br>"
                      "Sum: %{y:,}<extra></extra>"
    )
    packetBar.update_traces(
        hovertemplate="Type: %{x}<br>"
                      "Count: %{y:,}<extra></extra>"
    )

    # layout of site
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dcc.Graph(
                        id="packetLine",
                        figure=packetLine,
                        config=graph_config
                    )],
                    style=card_style)])],
            style={"margin-top": "1vh"}),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dcc.Graph(
                        id="packetPie",
                        figure=packetPie,
                        config=graph_config
                    )],
                    style=card_style)
                ])],
            style={"margin-top": "2vh"}),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dcc.Graph(
                        id="packetBar",
                        figure=packetBar,
                        config=graph_config
                    )],
                    style=card_style)
                ])],
            style={"margin-top": "2vh", "margin-bottom": "1vh"}),],
        fluid=True,
        )
