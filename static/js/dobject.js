var ajaxurl="/demovibes/ajax/";
var ajaxeventid=0; // updated later
var debug;
var ajaxmonitorrequest=false;

function apf(url, form) {
    $.post(url, $(form).serialize());
    return false;
}

function ajaxmonitorspawn() {
    // resceive monitor events for objects on the page
    var url=ajaxurl+'ping/'+ajaxeventid+'/';
    debug=url;
    // alert('Monitor for '+url);
    // old version: http://code.google.com/p/demovibes/issues/detail?id=47
    // ajaxmonitorrequest=$.get(url,ajaxmonitorupdate);
    ajaxmonitorrequest=$.ajax({
        type: 'GET',
        dataType: 'text',
        url: url,
        timeout: 300000,
        success: function(data, textStatus ){
            ajaxmonitorupdate(data);
        },
        error: function(xhr, textStatus, errorThrown){
            //newMessage("[Updater] Problem with server connection. Retrying in 15 seconds", 15);
            setTimeout('ajaxmonitorspawn()',15000); // wait a bit on fail
        }
     });
}

function ajaxmonitorabort() {
    if (ajaxmonitorrequest)
        ajaxmonitorrequest.abort();
}

function ajaxmonitor(eventid) {
    ajaxeventid=eventid;
    setTimeout('ajaxmonitorspawn()',1);
    setInterval('counter()',1000);
}

function ajaxmonitorupdate(req) {
        // must return event in lines
        var event=req.split('\n');
        var i;
        var id;
        for (i=0;i<event.length;i++) {
            id=event[i];
            if (id != "bye" && id != "") {
                if (id.substr(0,4)=='msg:') {
                    newMessage(id.substr(4,id.length));
                }
                else if (id.substr(0,5)=='vote:') {
                    updateVotes(id.substr(5,id.length));
                }
                else if (id.substr(0,5)=='eval:') {
                    eval(id.substr(5,id.length)); // evaluate the expression
                } else if (id.substr(0,1)=='!') {
                    ajaxeventid=parseInt(id.substr(1,id.length));
                } else {
                    $("[data-name='"+id+"']").load(ajaxurl+id+'/?event='+ajaxeventid, function() {applyHooks();})
                }
            }
        }
        ajaxmonitorrequest=false;
        applyHooks()
        var randInt = Math.floor((Math.random()*1000));
        setTimeout('ajaxmonitorspawn()',100 + randInt); // we get a nice return ask again right away
}

function updateVotes(data) {
    var votedata = data.split("|");
    $("#songrating").text(votedata[0]);
    $("#songrating_votes").text(votedata[1]);
}

function add_smileys(div, input) {
    div.empty();
    div.html("<div class='smileys_loading'>Loading..</div>");
    $.get("/demovibes/ajax/smileys/",function (data) {
        div.empty();
        $(data).each(function (i, elem) {
            var sign = elem[0];
            var icon = elem[1];
            var boxdiv = $("<div/>").addClass("smileybox-smiley");
            var boximg = $("<img/>").attr("src", STATIC_URL + icon);
            boxdiv.append(boximg);
            boxdiv.attr("title", sign);
            boxdiv.click(function () {
                var inpval = input.val() + " " + sign + " ";
                input.val(inpval);
                div.remove();
                input.focus();
            });
            div.append(boxdiv);
        });
    });
}

$(window).load( function () {
    var mydiv = $("<div/>").addClass("smileys-clicker").text("Smileys list");
    var inputbox = $("#blah");
    mydiv.click(function () {
        inputbox.focus();
        var smileys_holder = $("<div/>").addClass("smileybox-holder");
        var smileys_div = $("<div/>").addClass("smileybox");
        smileys_holder.append(smileys_div);
        $("body").prepend(smileys_holder);
        add_smileys(smileys_div, inputbox);
        smileys_holder.click(function () {
            smileys_holder.remove();
        });
    });
    $("#makeitso").after(mydiv);
});
