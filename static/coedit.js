//create a cookie to send the username to server
function setCookie(c_name,value,exdays){
    var exdate = new Date();
    exdate.setDate(exdate.getDate() + exdays);
    var c_value = encodeURI(value) + ((exdays==null) ? "" : "; expires=" + exdate.toUTCString());
    document.cookie = c_name + "=" + c_value;
}

//get the cookie from the browser
function getCookie(c_name){
    var c_value = document.cookie;
    var c_start = c_value.indexOf(" " + c_name + "=");
    if (c_start == -1){
        c_start = c_value.indexOf(c_name + "=");
    }
    if (c_start == -1){
        c_value = null;
    }else{
        c_start = c_value.indexOf("=", c_start) + 1;
        var c_end = c_value.indexOf(";", c_start);
        if (c_end == -1){
            c_end = c_value.length;
        }
        c_value = decodeURI((c_value.substring(c_start,c_end)));
    }
    return c_value;
}

//check the cookie if the user's name is already in the list
function checkCookie(){
    var username=getCookie("username");
    if (username!=null && username!=""){
    }
    else{
        username=prompt("Please enter your name:","");
        if (username!=null && username!=""){
            setCookie("username",username,1);
        }
    }
}

ace.require("ace/lib/fixoldbrowsers");
var editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");

$(function() {
    //the connection variable
    var conn = null;

    //the flag to forbid the info send back to server again
    // before the type in message change is made
    var fromMessage = false;

    //the flag to forbid the info send back to server again
    // before the text reset is made
    var applyChange=false;

    //the flag to forbid the info send back to server again
    // before the cursor move change is made
    var fromCursor = false;

    //the list to remember the random generated color for different user
    var colorStack=[];

    //define the range to be ace editor range instead of browser default value
    var r=ace.require('ace/range').Range;

    //a list to remember the cursor position of the user by assign the index
    // in the list to be the user's id
    var users=[];

    //a list of username tag which show up on the user's cursor
    var cursorTag=[];

    //dynamically distribute color to users
    // which randomly generates the user cursor color in the style
    var cssGenerator = function (){
        //set css to be the first thing of the style
        var css = $('#my_style')[0];

        //rule 1 is to create the color style for user's cursor
        var rule1='';

        //rules is the basic setup style for the ace editor
        var rules = ' #editor{height: 300px; display: block; position:relative;}\n';

        //rule 2 is to create the color style for user's selection
        var rule2='';

        //create 200 different color style
        for (var i=0; i < 200; i++){
            var a = 5*Math.floor(Math.random() * 4);
            var b = 5*Math.floor(Math.random() * 4);
            var c = 5*Math.floor(Math.random() * 4);

            //check if the color is black if is reassign it
            //check if the color is similar to the previous one
            while((i!=0 && ('#' + a.toString(16) + b.toString(16) + c.toString(16))==colorStack[i-1])
                ||(a==0 && b==0 && c==0)){

                a = 5*Math.floor(Math.random() * 4);
                b = 5*Math.floor(Math.random() * 4);
                c = 5*Math.floor(Math.random() * 4);
            }

            //record the color to the color stack for dynamically create div
            colorStack[i]='#' + a.toString(16) + b.toString(16) + c.toString(16);

            //the color style code for user's cursor
            rule1 += 'div.user_'
                + String(i) + '.ace_cursor { border-left-color: #'
                + a.toString(16) + b.toString(16) + c.toString(16) + ' }\n';

            //the color style code for user's selection
            rule2 += 'div.ace_marker-layer div.user_'
                + String(i) + '.ace_selection { background-color: #'
                + a.toString(16) + b.toString(16) + c.toString(16)+ ' }\n';
        }

        //combine all the style code
        rules=rules+rule1+rule2;

        //apply these to css style
        css.innerHTML = rules;
    };

    //run the on load check cookie and css generator
    checkCookie();
    cssGenerator();

    //helper function to build up range object
    function createRange(pos1,pos2,pos3,pos4){
        //build up the range object of the new cursor position
        var row1= pos1;
        var column1= pos2;
        var row2= pos3;
        var column2=pos4;
        return new r(pos1,pos2,pos3,pos4);
    }

    //helper function to set or reset text
    function setText(string_message,pos1,pos2){
        //forbid the info send to server before the change is applied
        fromCursor=true;
        applyChange=true;
        fromMessage=true;

        //set the text to be the client text and move the cursor back to position
        editor.setValue(string_message);
        editor.clearSelection();
        editor.getSelection().moveCursorToScreen(pos1, pos2,false);

        //allow the info send to server to apply the new changes
        fromMessage=false;
        fromCursor=false;
        applyChange=false;
    }

    //helper function to remove a div
    function divRemove(id_num){
        //remove the old username-cursor tag's div
        var oldelement=document.getElementById(id_num);
        if (oldelement) {
            oldelement.parentNode.removeChild(oldelement);
        }
    }

    //helper function to create a new cursor
    function createMarker(users,message,num){
        //build up the range object of the new cursor position
        var my_range
            =createRange(message.row,message.column,message.row,message.column+1);

        //add the cursor to the screen
        var mark_id
            =editor.session.addMarker(my_range,"user_"+num+" ace_cursor","text");

        editor.session
            .addDynamicMarker(editor.session.getMarkers()[mark_id],false);

        //record the cursor id in the users list by index to be user id
        users[message.user_id]=mark_id;
    }

    //check if username tag is there when repainted if not readded it
    function ensureNameTagIsPresent(users,cursor_tag){
        for(var i=0;i<users.length;i++){
            if(users[i]!=null&&users[i]!=-1&& $("#"+i).length==0){
                var num=i%200;
                document
                    .getElementsByClassName("user_"+num)[0].appendChild(cursor_tag[i]);
            }
        }
    }

    //function to create the username tag on cursor
    function cursor_username(num,name,user_id,label) {
        var color="gray";
        if(user_id!=-1){
            color=colorStack[num];
        }

        //create the div for the username on cursor tag
        var cursor_username = document.createElement("div");
        cursor_username.id = user_id;
        cursor_username.innerHTML = name;

        //setup the css styple for the div
        cursor_username.style.color ="black";
        cursor_username.style.padding="2px 3px";
        cursor_username.style.backgroundColor = color;
        cursor_username.style.position="absolute";
        cursor_username.style.top="13px";
        cursor_username.style.zIndex="6";
        cursor_username.style.display="none";

        //add the div to the page
        var wrapper=document.getElementsByClassName(label)[0];
        wrapper.appendChild(cursor_username);

        //record the div in the cursor tag
        cursorTag[user_id]=cursor_username;

    }

    //dynamically add new div fro the new user to
    // match the user with cursor color and user name
    function dynamicDiv(num,name,user_id) {
        var color="gray";
        if(user_id!=-1){
            color=colorStack[num];
        }

        //create the div for the user
        var dynDiv = document.createElement("div");
        dynDiv.id = "name"+user_id;
        dynDiv.innerHTML = name;

        //setup the css styple for the div
        dynDiv.style.color =color;
        dynDiv.style.height = "20px";
        dynDiv.style.width = "200px";
        dynDiv.style.backgroundColor = 'black';

        //add the div to the page
        document.body.appendChild(dynDiv);
    }

    //cycler function for screenchange
    function nameTagCycler(object) {
        $(object).data('is_waiting', true);

        // get time since the last click
        var time_since_change = new Date() - $(object).data('last_moved');

        if( time_since_change>= 2100 ){
            $(object).fadeOut(1);
            $(object).data('is_waiting', false);
        } else {
            setTimeout(function() { nameTagCycler(object) }, 200);
        }
    }

    //function to deal with screen change time record
    function nameTagHanlder(object) {
        // Record the time of the screenchanged
        $(object).data('last_moved', new Date());

        // Start Cycler
        if(!$(object).data('is_waiting')){
            nameTagCycler(object);
        }
    }

    //reapply the mouse over event hanlder
    function bindMouseOver(){
        $(".ace_start").unbind('mouseover');
        $(".ace_start").unbind('mouseout');

        $(".ace_start").on('mouseover',function() {
            $(this).children().fadeIn(50);
        });
        $(".ace_start").on('mouseout',function(){
            nameTagHanlder($(this).children());
        });
    }

    //helper function for tag move when mouse moves
    function tagMove(users,cursor_tag,message,num){
        //add the username tag on cursor and make it fade after 3 secs
        setTimeout(function() {
            cursor_username(num,message.name,message.user_id,"user_"+num);
            $("#"+num).fadeIn(100,nameTagHanlder($("#"+num)));
        },50);

        setTimeout(function() {
            ensureNameTagIsPresent(users,cursor_tag);
        },100);

        setTimeout(function(){
            bindMouseOver();
        },150);
    }

    //function to deal with message from the server
    function connect() {
        disconnect();

        //setup the connection host
        conn = new SockJS('http://' + window.location.host + '/chat', "websocket");

        //when user connected, create a div for the user self
        conn.onopen = function() {
            dynamicDiv(-1,"Myself",-1);
        };

        //deal with the message get from the server
        conn.onmessage = function(e) {
            var message = JSON.parse(e.data);

            //setup the client text for the new connected user
            if (message.act == "startup"){
                var string_message=JSON.parse(message.info);

                //set the text
                if (string_message!=(editor.getValue())){
                    setText(string_message,0,0);
                }
            }
            //doing the correction for the collison
            else if (message.act == "correction"){
                var string_message=JSON.parse(message.info);

                //check if the client text is the same with the user's text
                if (string_message!=(editor.getValue())){

                    //get the cursor's current position
                    var position=editor.getSelection().getCursor();

                    //reset the text
                    setText(string_message,position.row,position.column);
                }
            }
            //create the cursor for the new user
            else if (message.act == "create_cursor"){
                //get the css style num for the user
                var num=message.user_id % 200;

                //add the cursor to the screen
                createMarker(users,message,num);

                //create a div for the user name to match with the cursor color
                dynamicDiv(num,message.name,message.user_id);

                //add the username tag on cursor and make it fade after 3 secs
                tagMove(users,cursorTag,message,num);
            }
            //remove the cursor for the disconnected user
            else if(message.act == "remove_cursor"){
                //get the cursor id from the users list
                var mark_id=users[message.user_id];

                //remove the cursor id from the user list
                users[message.user_id]=-1;

                //remove the cursor from the screen
                editor.session.removeMarker(mark_id);

                //remove the div of the user
                divRemove("name"+message.user_id);
            }

            //move the user's cursor accordingly
            else if(message.act == 'move_cursor'){
                //get the css style num for the user cursor
                var num=message.user_id % 200;

                //remove the old username-cursor tag's div
                divRemove(message.user_id);

                //forbid the info send to server before the cursor change is made
                fromCursor=true;

                //check if the user's cursor is in the list if it is
                // remove the old one if not create a new user div
                // to match the cursor color and username for the user
                if(users[message.user_id]!=null && users[message.user_id]!=-1){
                    //get the cursor id from the users list
                    var mark_id=users[message.user_id];

                    //build up the range object of the new cursor position
                    var my_range
                        =createRange(message.row,message.column,message.row,message.column+1);

                    //update the marker
                    editor.session.getMarkers()[mark_id].range=my_range;

                    if(editor.session.getMarkers()[mark_id].clazz
                        !="user_"+num+" ace_cursor"){

                        editor.session.getMarkers()[mark_id].clazz
                            ="user_"+num+" ace_cursor";
                    }
                    editor.updateSelectionMarkers();
                }else{
                    //create a new user div
                    // to match the cursor color and username for the user
                    dynamicDiv(num,message.name,message.user_id);

                    //add the cursor to the screen
                    createMarker(users,message,num);
                }

                //add the username tag on cursor and make it fade after 3 secs
                tagMove(users,cursorTag,message,num);

                //enable the cursor info send to server
                fromCursor=false;
            }

            //make a selection accordingly
            else if(message.act == 'change_selection'){
                //get the css style num for the user selection
                var num=message.user_id % 200;

                //remove the old username-cursor tag's div
                divRemove(message.user_id);

                //update cursor to be a selection or make a new one selection
                if(users[message.user_id]!=null && users[message.user_id]!=-1){
                    //get the cursor id from the users list
                    var mark_id=users[message.user_id];

                    //build up the range object of the new selection
                    var my_range
                        =createRange(message.start_row,message.start_column,message.end_row,message.end_column);

                    //update the marker
                    editor.session.getMarkers()[mark_id].range=my_range;

                    if(editor.session.getMarkers()[mark_id].clazz
                        != "user_"+num+" ace_selection"){

                        editor.session.getMarkers()[mark_id].clazz
                            = "user_"+num+" ace_selection";
                    }
                    editor.updateSelectionMarkers();
                }else{
                    //create a new user div to match the cursor color
                    // and username for the user
                    dynamicDiv(num,message.name,message.user_id);

                    //build up the range object of the new selection
                    var my_range
                        =createRange(message.start_row,message.start_column,message.end_row,message.end_column);

                    //add the selection to the screen
                    var mark_id
                        =editor.session.addMarker(my_range,"user_"+num+" ace_selection","text");

                    editor.session
                        .addDynamicMarker(editor.session.getMarkers()[mark_id],false);

                    //record the cursor id in the users list by index
                    // to be user id
                    users[message.user_id]=mark_id;
                }

                //add the username tag on cursor and make it fade after 3 secs
                tagMove(users,cursorTag,message,num);
            }
            //deal with the message change
            else {
                //get the cursor position
                var cursor= editor.getCursorPosition();

                //forbid info send to server before the message change is made
                fromMessage = true;

                //to check if the message change is made before user self's
                // cursor. if is, then the applied change will affect the user
                // self's cursor position. if not then the change will not
                // affect the user self's cursor position
                if((message.range.start.row< cursor.row)
                    || (message.range.end.row< cursor.row)
                    || (message.range.start.column< cursor.column)
                    ||(message.range.end.column< cursor.column)){

                    editor.getSession().getDocument().applyDeltas([message]);
                }else{
                    fromCursor=true;
                    editor.getSession().getDocument().applyDeltas([message]);
                    editor.getSelection()
                        .moveCursorTo(cursor.row, cursor.column,true);
                    fromCursor=false;
                }

                //enable the message info send to server
                fromMessage = false;

            }
        };

        //when close set the connection to null
        conn.onclose = function() {
            conn = null;
        };
    }

    //disconnect function
    function disconnect() {
        if (conn != null) {
            conn.close();
            conn = null;
        }
    }

    //auto connect when the page refresh
    $(function() {
        if (conn == null) {
            connect();
        }
        return false;
    });


    //check if the username tag is dropped when there is a repaint of
    // the board if it is then readded it
    $( "#editor" ).click(function() {
        ensureNameTagIsPresent(users,cursorTag);
        setTimeout(function(){
            bindMouseOver();
        },50);
    });

    //send the info to the server when there is a new text change detected
    editor.getSession().getDocument().on('change', function(e){
        if(!fromMessage&&!applyChange&&! fromCursor){
            conn.send(JSON.stringify(e.data )+ '\r\n');
        }
    });


    //send info to the server when there is a cursor change.time out function
    // to help to send the right cursor position and send the range object if
    // the cursor forms a selection. send a cursor position if the user just
    //moves cursor
    editor.getSelection().on('changeCursor', function() {
        if(! fromCursor&&!applyChange){
            setTimeout(function() {
            var oldrange=editor.getSelection().getRange();
            if((oldrange.start.row==oldrange.end.row)
                && (oldrange.start.column==oldrange.end.column)){

                conn.send(JSON.stringify(editor.getSelection().getCursor())+ '\r\n');
            }else{
                conn.send(JSON.stringify(editor.getSelection().getRange())+ '\r\n');
            }
        },1);

        setTimeout(function() {
            ensureNameTagIsPresent(users,cursorTag);
        },300);

        setTimeout(function(){
            bindMouseOver();
        },450);
        }
    });

});