function deviceData(device, action){
    $.ajax({
        type : 'POST',
        url  : 'status',
        data : {'device': device, 'action': action},
        success :  function(data){
          try {
            data = data.replace(/'/g, "\"").replace("False", "0").replace("True", "1");
            data_json = JSON.parse(data);
            display = parseInt(data_json['dps']['20'])/10 + " V - " + data_json['dps']['18'] + " mA - " + data_json['dps']['19'] + " W"
            $(".display_"+device).html(display);
            if(data_json['dps']['1'] == 1)
                $(".status_"+device).css(
                  {'color': 'green'});
            else
                $(".status_"+device).css(
                  {'color': 'red'});
          }
          catch(err) {
              $(".message").html("Error: " + err.message)
              $('.alert').alert()
          }
        }
    });
}
