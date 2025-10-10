import dash
from dash import Dash, html, dcc
from flask import request, jsonify, abort
import requests
#from flask_cors import CORS

##
# Constants
##

# define dash internal routes, no authentication required
internal_routes = ["/_dash", "/_favicon", "/_reload", "/public_page", "/heatmap", "/assets"]
# define dashboard routes, authentication required
dashboard_routes = ["/sensor_details", "/job_details", "/job_tracker"]


##
# Dash app
##

# initialise Dash app
app = Dash(
    __name__,
    requests_pathname_prefix="/dash/",
    use_pages=True,
    suppress_callback_exceptions=True
)

# get the underlying flask server
server = app.server

# activate if dash server runs on different machine than host server
# all url's in data_deamon, job_tracker and this app have to be adjusted
#CORS(server, supports_credentials=True)

# multipage dash app needs page_container in main layout
app.layout = html.Div([
    dash.page_container,
    dcc.Location(id="url")
])

# validate every pages layout so dash knows all ids when it's run
app.validation_layout = html.Div([
    app.layout,
    *(dash.page_registry[page]["layout"] for page in dash.page_registry)
])


# only let valid routes pass
@server.before_request
def auth():
    path = request.path
    # let dash internal requests pass
    if any(path.startswith(route) for route in internal_routes):
        return None
    # perform authentication on dashboard requests
    if any(path.startswith(route) for route in dashboard_routes):
        url = "http://127.0.0.1:8000/login/auth"
        cookies = request.cookies
        response = requests.get(url, cookies=cookies)
        if response.status_code == 200:
            return None
        else:
            return jsonify({"status": "Unauthorized"}), response.status_code
    # every other request shows 404
    abort(404)


if __name__ == '__main__':
    app.run(debug=False,
            port=8050)

