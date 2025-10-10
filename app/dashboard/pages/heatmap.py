import datetime
import pandas as pd
import dash
from dash import dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import psycopg2 as ps
import app.dashboard.credentials as credentials


dash.register_page(__name__, path_template="/heatmap/<name>")

##
# Styles
##

background_color = "#f5f5f5"
font_color = "black"
card_style = {
    "border-radius": "0.25rem",
    "width": "100%",
    "height": "100%",
    "color": "white",
    "boxShadow": "0 .5rem 1rem rgba(0,0,0,.15)",
    "box-sizing": "border-box",
    "padding": "0"
}
card_class = "text-white shadow p-0 rounded w-100"
graph_config = {"displayModeBar": "hover"}


# create dataframe [year, month, count] for every year-month combination between now and years many years ago where
# count is number of jobs in this year-month
def create_sensor_df(cur, sensor, years=2):
    # get the timestamp of input years many years ago, if timestamp is in middle of year, take the first day of the year
    # as lower bound for jobs to be included and today as upper bound
    base = datetime.datetime.utcnow() - datetime.timedelta(weeks=years * 52)
    start_of_year = datetime.datetime(base.year, 1, 1, tzinfo=datetime.timezone.utc)
    year_lower = start_of_year.year
    month_lower = start_of_year.month
    start_of_year = start_of_year.timestamp()
    year_month_upper = datetime.datetime.today().strftime("%Y %m")
    year_upper = int(year_month_upper.split()[0])
    month_upper = int(year_month_upper.split()[1])

    if sensor == "all":
        # get all jobs
        sql = """SELECT name, start_time, end_time FROM jobs WHERE name != 'public_page' AND end_time >= %s"""
        cur.execute(sql, (start_of_year, ))
        data = cur.fetchall()
        df_jobs = pd.DataFrame(data=data, columns=["name", "start_time", "end_time"])
    else:
        # get all jobs for this sensor
        sql = """SELECT j.name, j.start_time, j.end_time 
                FROM jobs as j, sensor_job as s 
                WHERE j.name = s.job_name 
                AND s.sensor_name = %s 
                AND end_time >= %s"""
        cur.execute(sql, (sensor, start_of_year))
        data = cur.fetchall()
        df_jobs = pd.DataFrame(data=data, columns=["name", "start_time", "end_time"])

    # create dataframe for plotting year, month and count, prefill with all years and months to plot with count of zero
    df_heatmap = pd.DataFrame(columns=['year', 'month', 'count'])
    df_heatmap.loc[len(df_heatmap)] = year_lower, month_lower, 0
    while not (year_lower == year_upper and month_lower == month_upper):
        if month_lower < 12:
            month_lower += 1
        else:
            month_lower = 1
            year_lower += 1
        df_heatmap.loc[len(df_heatmap)] = year_lower, month_lower, 0

    # iterate over every job, add up count for year month combinations where job was active
    for index, row in df_jobs.iterrows():
        start = max(start_of_year, row['start_time'])
        start = datetime.datetime.utcfromtimestamp(start).strftime("%Y %m")
        end = datetime.datetime.utcfromtimestamp(row['end_time']).strftime("%Y %m")

        if start_of_year < int(row['end_time']):
            s_year = int(start.split()[0])
            s_month = int(start.split()[1])
            e_year = int(end.split()[0])
            e_month = int(end.split()[1])

            # increment count for every year-month combination where job was active
            df_heatmap.loc[(df_heatmap["year"] == s_year) & (df_heatmap["month"] == s_month), "count"] += 1
            while not (s_year == e_year and s_month == e_month):
                if s_month < 12:
                    s_month += 1
                else:
                    s_month = 1
                    s_year += 1
                df_heatmap.loc[(df_heatmap["year"] == s_year) & (df_heatmap["month"] == s_month), "count"] += 1

    return df_heatmap


def layout(name=None, **kwargs):
    db_user, db_password, user, password = credentials.get()
    # Connect to postgres database
    conn = ps.connect(database="postgres",
                      user=db_user,
                      host="localhost",
                      password=db_password,
                      port=5432)
    cur = conn.cursor()

    # create dataframe, define labels and heatmap graph
    df = create_sensor_df(cur, name, 2)
    x_labels = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jul', 7: 'Jun', 8: 'Aug', 9: 'Sep', 10: 'Oct',
                11: 'Nov', 12: 'Dec'}
    y_labels = {i: str(i) for i in df.year.unique()}
    fig = go.Figure(data=
        go.Heatmap(
            z=df['count'],
            x=df['month'],
            y=df['year'],
            xgap=2, ygap=2,
            hovertemplate=
            "Month: %{x}<br>"
            "Year: %{y}<br>"
            "Count: %{z}<extra></extra>",
            colorscale="Tealgrn"
        ))

    # style
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            tickmode='array',
            tickvals=list(x_labels.keys()),
            ticktext=list(x_labels.values())
        ),
        yaxis=dict(
            showgrid=False,
            tickmode='array',
            tickvals=list(y_labels.keys()),
            ticktext=list(y_labels.values())
        ),
        height=266,
        title="Number of previous Jobs",
        showlegend=False,
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font_color=font_color,
    )

    cur.close()
    conn.close()

    # layout of site
    return dbc.Container(
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dcc.Graph(figure=fig,
                              config=graph_config
                            ),
                    style=card_style,
                    className=card_class)))
        , fluid=True)
