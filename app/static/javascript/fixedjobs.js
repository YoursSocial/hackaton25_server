/*jshint esversion: 6*/
var fixedJobs = [];
var host = window.location.protocol + "//" + window.location.host;

document.getElementById('logoutButton').onclick = logout

window.onload = startCall();

function startCall() {
  $.ajax({
    dataTypr: 'json',
    method: 'GET',
    url: host + "/fixedjobs/",

    success: function(response) {
      fixedJobs = response.data;
      buildTable(fixedJobs);
      //buildContent(fixedJobs);
	  startDashboard();
    },
    error: function(response){
      var status = response.status;
      if (status == 401) {
        console.log("401: Unauthorized")
        perform_JWT_refresh().done(startCall);
      } else if (status == 403) {
        //redirect to login page
        alert("Insufficient rights.");
        console.log("403: Insufficient rights.")
      } else {
        console.log("jobs-autoload error: ", status, response.responseText);
      }
    },
  });
}

function startDashboard(){
	var url = '/dash/job_tracker';
	var iframe = "<iframe src=" + url + " style='border:none; width:100%; height:100%'></iframe>";
	document.getElementById('dashboard').innerHTML = iframe;
}

function shortenString(inputString, maxLengths){
  if (inputString.length > maxLengths){
    return inputString.substring(0,maxLengths) + "...";
  }
  else{
    return inputString;
  }
}

function buildTable(fixedJobs) {
  var table = document.getElementById('table_content');

  //sorting the jobs according to status
  var status_sortorder = ["finished","running","pending","failed"];
  //fixedJobs=fixedJobs.sort((a, b) => sortorder.indexOf(a.status) - sortorder.indexOf(b.status));
  //fixedJobs=fixedJobs.sort((a, b) => b.start_time-a.start_time); /*default: sort for start_time*/
  fixedJobs=fixedJobs.sort((a, b) => a.start_time-b.start_time); /*default: sort for start_time*/


  for (var i = fixedJobs.length-1; i >= 0; i--) {
      var entry = fixedJobs[i]; // one entry for each job
      var name = entry.name;
      // style options have to be in javascript to apply when rows are added dynamically
      var href_line = `<a class="clickables" href="fixedjob_details.html?job_id=${entry.id}">${entry.name}</a>`;
      var row = `
    <tr id="${entry.id}">
      <td class="columns_with_ellipsis_overflow" style="padding:0 5px 0 5px">${href_line}</td>
      <td id="status-${entry.id}" style="padding:0 5px 0 5px;font-weight: bold">${entry.status}</td>
      <td class="joblist columns_with_ellipsis_overflow" style="padding:0 5px 0 5px">${entry.sensors}</td>
      <td class="joblist columns_with_ellipsis_overflow" style="padding:0 5px 0 5px">${entry.start_time}</td>
      <td class="joblist columns_with_ellipsis_overflow" style="padding:0 5px 0 5px">${entry.end_time}</td>
      <td class="joblist columns_with_ellipsis_overflow" style="padding:0 5px 0 5px;">${entry.command}</td>
      <td class="buttonColumn" align="center" style="padding:0 5px 0 5px;">
            <button class="remove_btn small_buttons" type="button" data-name=${entry.name} data-id=${entry.id} id="delete-${entry.id}">Delete</button>
        </td>
    </tr> `;

      $('#table_content').append(row);
      $(`#delete-${entry.id}`).on('click', deleteFixedJob);

      // dynamically adjust status color
    switch(entry.status) {
      case "pending":
        document.getElementById("status-"+entry.id).style.color = "#b87d00"
        break;
      case "running":
        document.getElementById("status-"+entry.id).style.color = "#056b20"
        break;
      case "finished":
        document.getElementById("status-"+entry.id).style.color = "black"
        break;
      case "failed":
        document.getElementById("status-"+entry.id).style.color = "#a80049"
        break;
  }
  }
  
}

//TODO: old function: delete if not needed anymore
function buildContent(fixedJobs) {
    var contentBox = document.getElementById('content');

    for (var i = 0; i < fixedJobs.length; i++) {
        var fixedJob = fixedJobs[i];

        // create a div representing a fixed job
        var item = document.createElement("div");
        item.className = "fixed_jobs";
        item.id = fixedJob.name;

        // dynamic border colors
        switch(fixedJob.status) {
          case "pending":
            item.style.borderColor = "#005F8C91"
            break;
          case "running":
            item.style.borderColor = "orange"
            break;
          case "finished":
            item.style.borderColor = "lime"
            break;
          case "failed":
            item.style.borderColor = "red"
            break;
        }

        // create an ul element representing the attributes of the fixed job
        var fixedJobAttributes = document.createElement("ul");
        fixedJobAttributes.className = "attributes";

        // create an li element for each attribute
        var name = document.createElement("li");
        var href_line = `<a class="clickables" href="fixedjob_details.html?job_id=${fixedJob.id}">${fixedJob.name}</a>`;
        name.innerHTML = "<b>Name:</b> " + href_line;

        var startTime = document.createElement("li");
        startTime.innerHTML = "<b>Start Time:</b> " + fixedJob.start_time;

        var endTime = document.createElement("li");
        endTime.innerHTML = "<b>End Time:</b> " + fixedJob.end_time;

        //show command but only first 20 characters
        var command = document.createElement("li");
        command.innerHTML = "<b>Command:</b> " + fixedJob.command.substring(0,20) + (fixedJob.command.length > 20 ? "...":"");

        var cmd_args = document.createElement("li");
        cmd_args.innerHTML = "<b>Arguments:</b> " + dictToNiceString(fixedJob.arguments);

        var sensors = document.createElement("li");
        sensors.innerHTML = "<b>Sensors:</b> " + arrayToString(fixedJob.sensors);

        var status = document.createElement("li");
        status.innerHTML = "<b>Status:</b> " + fixedJob.status;

        // add li elements to ul
        fixedJobAttributes.appendChild(name);
        fixedJobAttributes.appendChild(startTime);
        fixedJobAttributes.appendChild(endTime);
        fixedJobAttributes.appendChild(command);
        fixedJobAttributes.appendChild(cmd_args);
        fixedJobAttributes.appendChild(sensors);
        fixedJobAttributes.appendChild(status);

        // add ul to item
        item.appendChild(fixedJobAttributes);

        // add delete button
        var delete_btn = document.createElement("button");
        delete_btn.type = "button";
        delete_btn.innerHTML = "Delete";
        delete_btn.data = fixedJob.name;
        delete_btn.className = "remove_btn small_buttons";
        delete_btn.onclick = function() { deleteFixedJob(this.data); }
        item.appendChild(delete_btn);

        // add item to flexbox
        contentBox.appendChild(item);
    }
}


// ["sensor1", "sensor2"] -> "sensor1,sensor2"
function arrayToString(array) {
    var output = ""
    for (var i = 0; i < array.length; i++) {
       // append commata until last element
        if (i < array.length - 1) {
            output += array[i] + ","
        } else {
            output += array[i];
        }
    }
    return output;
}

// {"key1": "value1"; "key2":"value2"} -> "key1:value1; key2:value2"
function dictToNiceString(dict) {
    var output = "";
    var keys = Object.keys(dict)
    for (var i = 0; i < keys.length; i++) {
       temp_key = keys[i];
       temp_value = dict[temp_key];
       // append commata until last element
        if (i < keys.length - 1) {
            output += temp_key + ":" + temp_value + ", ";
        } else {
            output += temp_key + ":" + temp_value;
        }
    }
    return output;
}

// "key1:value1; key2:value2" -> '"key1": "value1", "key2": "value2"'
function processString(in_string) {
    in_string = in_string.replace('"','')
    in_string = in_string.replace('{','')
    in_string = in_string.replace('}','')
    in_string = in_string.replace(',',';')
    in_string = in_string.replace(' ','')
    var output = '';
    var pairs = in_string.split(";")
    for (var i = 0; i < pairs.length; i++) {
       var entries = pairs[i].split(":")
       if (entries.length == 2) {
         output += '"' + entries[0] + '": "' + entries[1] + '"';
         // append commata until last element
         if (i < pairs.length - 1) {
            output += ', ';
         }
       }
    }
    return output;
}

function deleteFixedJob() {
  let name = $(this).data('name');
  let id = $(this).data('id');

  let text = "Delete " + name +"?";
  if (confirm(text) == true) {
    $.ajax({
      dataTypr: 'json',
      method: 'DELETE',
      url: host + "/fixedjobs/?name=" + name,

      success: function(response){
        console.log("Deleted " + name);
        $("#" + id).remove(); //delete row by referring to the row-id
      },
      error: function(response){
        var status = response.status;
        if (status == 401) {
          console.log("401: Unauthorized")
          perform_JWT_refresh().done(function() {deleteFixedJob(name)});
        } else if (status == 403) {
          //redirect to login page
          alert("Insufficient rights.");
          console.log("403: Insufficient rights.")
        } else {
          console.log("deleteFixedJob error: ", status, response.responseText);
        }
      },
    });

  }
}


// add new fixed job dialog, from: https://jqueryui.com/dialog/#modal-form
$( function() {
  var dialog, form,

    // From http://www.whatwg.org/specs/web-apps/current-work/multipage/states-of-the-type-attribute.html#e-mail-state-%28type=email%29
    name = $( "#name" ),
    start_date = $( "#start_date" ),
    start_time = $( "#start_time" ),
    end_date = $( "#end_date" ),
    end_time = $( "#end_time" ),
    command = $( "#command" ),
    cmd_args = $( "#cmd_args" ),
    allFields = $( [] ).add( name ).add( start_time ).add( end_time ).add( command ).add( cmd_args ),
    tips = $( ".validateTips" );


  function datetimeToUnixtimestamp(date){
    return parseInt((Date.parse(date)/1000).toFixed(0))
  }

  function updateTips( t ) {
    tips
      .text( t )
      .addClass( "ui-state-highlight" );
    setTimeout(function() {
      tips.removeClass( "ui-state-highlight", 1500 );
    }, 500 );
  }

  function checkFilledIn(element){
    if (element.val()){
      return true; //element has a value and it's ok
    }else{
      element.addClass( "ui-state-error" );
      updateTips("please fill in the field");
      return false;
    }
  }

  function checkWhitespace(element){
    if (element.val().includes(' ')){
      element.addClass( "ui-state-error" );
      updateTips("No whitespace allowed in the name!");
      return false;
    }else{
      return true;
    }
  }

  function checkJobDuration(start,end){
    if (datetimeToUnixtimestamp(end) <= datetimeToUnixtimestamp(start)){
      end_date.addClass( "ui-state-error" );
      end_time.addClass( "ui-state-error" );
      updateTips("The job's end must be after its start time");
      return false;
    }else{
      return true;
    }
  }

  function specificCommandChecker(command, cmd_args){
    if (["iridium_sniffing","get_logs","set_network_conn","set_wifi_config","set_eth_config","get_sys_config","set_sys_config"].includes(command.val()) && cmd_args.val() === ""){
      cmd_args.addClass( "ui-state-error" );
      updateTips("The command requires arguments");
      return false;
    }else{
      return true;
    }
  }

  function createFixedJob() {
    //merge start/end date & time to get a complete datetime
    var start = new Date(Date.parse(start_date.val() + ' ' + start_time.val()));
    var end = new Date(Date.parse(end_date.val() + ' ' + end_time.val()));
    //console.log(datetimeToUnixtimestamp(start))
    

    var valid = true;
    allFields.removeClass( "ui-state-error" );

    // check that no major value is empty (cmd_args can be empty)
    //valid = valid && name.val() && start_time.val() && end_time.val() && command.val();
    valid &= checkFilledIn(name) && checkFilledIn(start_date) && checkFilledIn(start_time) && checkFilledIn(end_date) && checkFilledIn(end_time) && checkFilledIn(command);

    //disallow whitespace in name such that delete works properly:
    valid &= checkWhitespace(name);

    //check that end time is after start time
    valid &= checkJobDuration(start,end);

    valid &= specificCommandChecker(command, cmd_args);

    if ( valid ) {

      pre_data = '{"name": '+'"'+name.val()+'"'+
        ', "start_time": '+'"'+datetimeToUnixtimestamp(start)+'"'+
        ', "end_time":'+'"'+datetimeToUnixtimestamp(end)+'"'+
        ', "command":'+'"'+command.val()+'"'+
        ', "arguments":'+'{'+processString(cmd_args.val())+'}'+
        ', "sensors": []'+
        ', "states": {}}'

      $.ajax({
        method: 'POST',
        dataTypr: 'json',
        contentType: 'application/json',
        url: host + "/fixedjobs/",
        data: pre_data,

        success: function(response) {
          console.log("added fixed job");
          location.reload();
        },
        error: function(response){
          var status = response.status;
          if (status == 401) {
            console.log("401: Unauthorized")
            perform_JWT_refresh().done(createFixedJob);
          } else if (status == 403) {
            //redirect to login page
            alert("Insufficient rights.");
            console.log("403: Insufficient rights.")
          } else {
            if (/.* already exists./.test(response.responseText)){
              alert("Error: job with that name already exists.");
            }
            if (/.* start lies in the past./.test(response.responseText)){
              alert("Error: job starts in the past.");
            }
            console.log("createFixedJob error: ", status, response.responseText);
          }
        },
      });
      // dialog.dialog( "close" );
    }
    return valid;
  }

  dialog = $( "#dialog-form" ).dialog({
    autoOpen: false,
    height: 550,
    width: 400,
    modal: true,
    buttons: {
      "Create Fixed Job": createFixedJob,
      Cancel: function() {
        dialog.dialog( "close" );
      }
    },
    close: function() {
      form[ 0 ].reset();
      allFields.removeClass( "ui-state-error" );
    }
  });

  form = dialog.find( "form" ).on( "submit", function( event ) {
    event.preventDefault();
    createFixedJob();
  });

  $( "#create_fixed_job" ).button().on( "click", function() {
    dialog.dialog( "open" );
  });
} );