var host = window.location.protocol + "//" + window.location.host;
var online_sensors = [];
var offline_sensors = [];
window.onload = startCall();

function startCall() {
    $.ajax({
        dataTypr: 'json',
        method: 'GET',
        url: host + "/sensors/get_locations",

        success: function(response) {
            online_sensors = response.data[0];
            offline_sensors = response.data[1];
            console.log(online_sensors);
            console.log(offline_sensors);
            startDashboard();
            if (online_sensors.length || offline_sensors.length){//need at least 1 sensor to calculate the map bounds below
                generatingMap();
            }else{
                document.getElementById("map").innerHTML += "<p>Error: No locations loaded</p>"
                console.log("no locations loaded");
            }
            
        },
        error: function(response){
            console.log("sensors-autoload error: ", response.status, response.responseText);
        },
    });
}

function startDashboard(){
	var url = '/dash/public_page/';
	var iframe = "<iframe src=" + url + " style='border:none; width:100%; height:100%;'></iframe>";
	document.getElementById('dashboard').innerHTML = iframe;

	var url_map = '/dash/heatmap/all'
	var iframe_map = "<iframe src=" + url_map + " style='border:none; width:67%; height:100%;'></iframe>";
	document.getElementById('heatmap').innerHTML = iframe_map;
}

function generatingMap(){
    var map = L.map('map');
    L.tileLayer('https://{s}.tile.osm.org/{z}/{x}/{y}.png', 
        {attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors',
            maxNativeZoom:9, //limit max zoom
            maxZoom:9,
        }).addTo(map);

    


    var redIcon = L.icon({
        iconUrl: '/images/marker-red.png',
        shadowUrl: '/images/marker-red.png',

        iconSize:     [25,35], // size of the icon
        shadowSize:   [0,0], // size of the shadow
        iconAnchor:   [12,35], // point of the icon which will correspond to marker's location
        shadowAnchor: [0,0],  // the same for the shadow
        popupAnchor:  [0,0] // point from which the popup should open relative to the iconAnchor
    });
    var grayIcon = L.icon({
        iconUrl: '/images/marker-gray.png',
        shadowUrl: '/images/marker-gray.png',

        iconSize:     [25,35], // size of the icon
        shadowSize:   [0,0], // size of the shadow
        iconAnchor:   [12,35], // point of the icon which will correspond to marker's location
        shadowAnchor: [0,0],  // the same for the shadow
        popupAnchor:  [0,0] // point from which the popup should open relative to the iconAnchor
    });

    //for testing
    /* var Kl = [49.44,7.74]; 
    var Fr = [50.11,8.68];
    var Mz = [49.99,8.24]; 
    const online_sensors = [Kl,Fr];
    const offline_sensors = [Mz];*/
    //var offline_sensors = online_sensors;
    //L.marker(online_sensors[1],{icon: grayIcon}).addTo(map)

    online_sensors.forEach((p) => L.marker(p,{icon: redIcon}).addTo(map))
    offline_sensors.forEach((p) => L.marker(p,{icon: grayIcon}).addTo(map))


    var bounds = new L.LatLngBounds(online_sensors.concat(offline_sensors)); //fit all sensors into initial view
    map.fitBounds(bounds);
}
