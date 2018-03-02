const notifier = require('node-notifier');
const http = require('http');
const open = require('opn');

const jobEndpoint = process.argv[2];
var requestOptions = {
  host: 'ds-build1.in.wellcentive.com',
  port: 8080,
  path: jobEndpoint + '/lastBuild/api/json'
}

function openConsole(notifierObject, options) {
  link = 'http://' + requestOptions['host'] + ':' + requestOptions['port'] + jobEndpoint + '/lastBuild/console';
  open(link);
  process.exit();
}

checkDone = function (body) {
  json_data = JSON.parse(body);

  if (json_data['building']) {
    return false;
  } else {
    var jobEndpointPieces = jobEndpoint.split('/');
    notifier.notify({
      'title': 'Jenkins ' + jobEndpointPieces[jobEndpointPieces.length - 1],
      'message': 'Build ' + json_data['result'],
      'wait': true
    })
    notifier.on('click', openConsole)
    return true;
  }
}

callJenkins = function() {
  http.get(requestOptions, function(response) {
    var body = '';

    response.on('data', function(chunk) {
      body += chunk;
    });
    response.on('end', function() {
      if (checkDone(body)) {
      }
    });
  });
}

console.log('Checking...');
callJenkins();
setInterval(callJenkins, 15000);
