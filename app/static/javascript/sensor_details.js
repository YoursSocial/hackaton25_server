/*jshint esversion: 6*/
var sensors = []; // list of documents with sensor_id(int) and job strings(array)
var host = window.location.protocol + "//" + window.location.host;


// assigning functions to the left menu items
document.getElementById('logoutButton').onclick = logout;
document.getElementById('create_new_jwt').onclick = download_JWT;


// call the website with href redirection: Redirect the user: location.replace("http://example.com/Page_Two.html?" + data); location.replace("sensor_details.html?sensor_id=foo");

//Get the current link & remove all content before ?
link = window.location.href;
if (link.includes("sensor_details.html?sensor_id=")) {
  var sensor_id = link.split('sensor_details.html?sensor_id=').pop();
  console.log("set sensor_status_id=", sensor_id);
  document.getElementById("sensor_status_id").innerHTML = "ID: " + sensor_id;
  //document.getElementById("create_new_jwt").setAttribute("href", host + "/login/sensor_token/" + sensor_id);
  startCall();
} else {
  console.log("unknown sensor_id");
  // redirect to the sensor_list.html
  window.location = "sensor_list.html";
}


function startCall() {
  $.ajax({
    dataTypr: 'json',
    method: 'GET',
    url: host + "/sensors/" + sensor_id,

    success: function(response) {
      sensor = response.data;
      console.log(sensor);
      buildContent(sensor)
	  startDashboard(sensor);
    },
    error: function(response){
      var status = response.status;
      if (status == 401) {
        console.log("401: Unauthorized")
        perform_JWT_refresh().done(startCall);
      } else if (status == 403) {
        alert("Insufficient rights.");
        console.log("403: Insufficient rights.")
        window.location = "login.html";
      } else {
        console.log("sensors-autoload error: ", status, response.responseText);
      }
    },
  });
}

function startDashboard(sensor){
	var name = sensor.sensor_name;

	var url = '/dash/sensor_details/' + name;
	var iframe = "<iframe src=" + url + " style='border:none; width:100%; height:100%'></iframe>";
	document.getElementById('dashboard').innerHTML = iframe;

	var url_map = '/dash/heatmap/' + name;
	var iframe_map = "<iframe src=" + url_map + " style='border:none; width:100%; height:100%'></iframe>";
	document.getElementById('heatmap').innerHTML = iframe_map;
}

function buildContent(sensor) {
//    var table = document.getElementById('table_content');

  var id = sensor.id;
  document.getElementById("sensor_status_id").innerHTML = "ID: " + id;
  var name = sensor.sensor_name;
  document.getElementById("sensor_name_field").innerHTML = name;
  var jobstring = sensor.jobs;
  if (jobstring.length < 1) {
    jobstring = " ---"
  }
  document.getElementById("sensor_scheduled_jobs").innerHTML = "scheduled Jobs: " + jobstring;
  var sensor_time = sensor.status.status_time;
  var sensor_date = new Date(sensor_time * 1000);
  var sensor_hours = '0' + sensor_date.getUTCHours()
  var sensor_minutes = '0' + sensor_date.getUTCMinutes()
  var sensor_seconds= '0' + sensor_date.getUTCSeconds()
  var my_time = Math.floor(Date.now() / 1000)
  var diff_time = my_time - sensor_time;
  var diff_sec = '0' + (diff_time % 60)
  var diff_min = '0' + (Math.trunc(diff_time / 60) % 60)
  var diff_hour = '' + Math.trunc(diff_time / 3600)
  if (diff_hour.length < 2) {
    diff_hour = '0' + diff_hour;
  }
  var time_string = sensor_date.getUTCDate() + '-' + (sensor_date.getUTCMonth()+1) + '-' + sensor_date.getUTCFullYear() + ', ' + sensor_hours.substr(-2) + ':' + sensor_minutes.substr(-2) + ':' + sensor_seconds.substr(-2) + ' (UTC) (' + diff_hour + ':' + diff_min.substr(-2) + ':' + diff_sec.substr(-2) + ' ago)';
  document.getElementById("sensor_last_contact").innerHTML = "last contact: " + time_string;
     
  var properties_list = document.getElementById('sensor_properties_list');
  // location (lat/lon)   
  var location_lat = sensor.status.location_lat;
  var location_lon = sensor.status.location_lon;
  if ((location_lat == null) || (location_lon == null)) {
    location_lat = "x";
    location_lon = "x";
  }
  var list_item = document.createElement("li");
  list_item.appendChild(document.createTextNode("location [°lat, °lon]: " + location_lat + ", " + location_lon));
  properties_list.appendChild(list_item);
  add_property(properties_list, "os version: ", sensor.status.os_version);
  add_property(properties_list, "temperature [°C]: ", sensor.status.temperature_celsius);
  add_property(properties_list, "Ethernet: ", sensor.status.Ethernet);
  add_property(properties_list, "WiFi: ", sensor.status.WiFi);
  add_property(properties_list, "LTE: ", sensor.status.LTE);
}


function add_property(properties_list, text_before, parameter) {
  if (parameter == null){
    parameter = "x";
  }
  var list_item = document.createElement("li");
  list_item.appendChild(document.createTextNode(text_before + parameter));
  properties_list.appendChild(list_item);
}

function download_JWT() {
  if (confirm (`Create new JWT for this sensor? (Actual token will become invalid!)`)) {
    var sensor_id = link.split('sensor_details.html?sensor_id=').pop();
    $.ajax({
      method: 'GET',
      url: host + "/login/sensor_token/" + sensor_id,
      xhrFields: {
        responseType: 'blob'
      },
      success: function (data) {
        var a = document.createElement('a');
        var url = window.URL.createObjectURL(data);
        a.href = url;
        document.body.append(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      },
      error: function(response){
        var status = response.status;
        if (status == 401) {
            console.log("401: Unauthorized")
            perform_JWT_refresh().done(download_JWT);
        } else if (status == 403) {
          //redirect to login page
          alert("Insufficient rights.");
          console.log("403: Insufficient rights.")
        } else {
          console.log("logout error: ", status, response.responseText);
        }
      },
    });
  }
}



