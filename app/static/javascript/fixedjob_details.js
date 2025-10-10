/*jshint esversion: 6*/
var sensors = []; // list of documents with sensor_id(int) and job strings(array)
var host = window.location.protocol + "//" + window.location.host;


// assigning functions to the left menu items
document.getElementById('add_sensor_btn').onclick = notYetImplemented;
document.getElementById('rm_senor_btn').onclick = notYetImplemented;


// call the website with href redirection: Redirect the user: location.replace("http://example.com/Page_Two.html?" + data); location.replace("sensor_details.html?sensor_id=foo");

//Get the current link & remove all content before ?
link = window.location.href;
if (link.includes("fixedjob_details.html?job_id=")) {
  var job_id = link.split('fixedjob_details.html?job_id=').pop();
  document.getElementById("job_id_field").innerHTML = "Job ID: " + job_id;
  startCall();
} else {
  console.log("unknown job_id");
  // redirect to the fixedjobs.html
  window.location = "fixedjobs.html";
}


function startCall() {
  var job_id = link.split('fixedjob_details.html?job_id=').pop();
  console.log("startCall, job: " + job_name)
  $.ajax({
    dataTypr: 'json',
    method: 'GET',
    url: host + "/fixedjobs/job_id/" + job_id,

    success: function(response) {
      job_data = response.data;
      console.log(job_data);
      buildContent(job_data)
	  startDashboard(job_data);
    },
    error: function(response){
      var status = response.status;
      if (status == 401) {
        console.log("401: Unauthorized")
        perform_JWT_refresh().done(startCall);
      } else if (status == 403) {
        alert("Insufficient rights.");
        console.log("403: Insufficient rights.")
        window.location = "user_list.html";
      } else {
        console.log("user-details-autoload error: ", status, response.responseText);
      }
    },
  });
}

function startDashboard(job_data){
	var name = job_data.name;
	var url = '/dash/job_details/' + name;
	var iframe = "<iframe src=" + url + " style='border:none; width:100%; height:100%'></iframe>";
	document.getElementById('dashboard').innerHTML = iframe;
}

function buildContent(job_data) {
  var id = job_data.id;
  document.getElementById("job_id_field").innerHTML = id;
  var name = job_data.name;
  document.getElementById("job_name").innerHTML = "job name: " + name;
  var start_time = job_data.start_time;
  document.getElementById("job_start_time").innerHTML = "start time: " + timestamp_2_timestring(start_time);
  var end_time = job_data.end_time;
  document.getElementById("job_end_time").innerHTML = "end time: " + timestamp_2_timestring(end_time);
  var command = job_data.command;
  document.getElementById("job_command").innerHTML = "command: " + command;
  var arguments = job_data.arguments;
  var arguments_string = "";
  var argument_keys = Object.keys(arguments);
  for (var i = 0; i < argument_keys.length; i++) {
    var argument_name = argument_keys[i];
    var argument_value = arguments[argument_name];
    arguments_string = arguments_string + argument_name + ": " + argument_value;
    if (i < argument_keys.length -1) {
      arguments_string = arguments_string + "; ";
    }
  }
  document.getElementById("job_arguments").innerHTML = "arguments: " + arguments_string;
  var sensors = job_data.sensors;
  document.getElementById("job_sensors").innerHTML = "sensors: " + sensors;
  var status = job_data.status;
  document.getElementById("job_status").innerHTML = "status: " + status;
  var states = job_data.states;
  var states_list = document.getElementById('job_sensor_states_list');
  var state_keys = Object.keys(states);
  for (var i = 0; i < state_keys.length; i++) {
    var temp_sensor_name = state_keys[i];
    var temp_sensor_state = states[temp_sensor_name]
    // create a list entry for every sensor-state
    var item = document.createElement("li");
    item.innerHTML = temp_sensor_name + ": " + temp_sensor_state;
    // add item to flexbox
    states_list.appendChild(item);
  }
}


function timestamp_2_timestring(utc_timestamp) {
  var date_obj = new Date(utc_timestamp * 1000);  // requires ms
  var hours = '0' + date_obj.getUTCHours();
  var minutes = '0' + date_obj.getUTCMinutes();
  var seconds= '0' + date_obj.getUTCSeconds();
  var my_time = Math.floor(Date.now() / 1000);
  var time_string = date_obj.getUTCDate() + '-' + (date_obj.getUTCMonth()+1) + '-' + date_obj.getUTCFullYear() + ', ' + hours.substr(-2) + ':' + minutes.substr(-2) + ':' + seconds.substr(-2) + ' (UTC)';
 return time_string
}


function notYetImplemented(){
  console.log("button not yet implemented");
  alert('Button not yet implemented!');
}




