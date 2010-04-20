// ****************************************************
// Insert GPL header here.
// ****************************************************

// ****************************************************
// Compatability matrix (as far as I can guess)
// 
// IE5+, Mozilla 1.0+, and Netscape 6+
//

function requestsong(no) {
	$.get(ajaxurl+'song/'+no+'/queue/?'+ajaxeventid);
}

// added support for multiple counter spans with arbitrary direction
function counter() {
	var spans=document.getElementsByName('counter');
	for (var i=0;i<spans.length;i++){
		var counter=1*spans[i].getAttribute("sec");
		var inc=1*spans[i].getAttribute("inc");

		if ((inc<0 && counter>0) || inc>0) {
			counter=counter+inc;

			spans[i].setAttribute("sec",counter);
			var s=counter;
			var h=Math.round(Math.floor(s/(60.0*60.0)));
			s%=(60*60);
			var m=Math.round(Math.floor(s/60.0));
			s%=(60);
			if (s<10) {
				s="0"+s;
			}
			if (h>0 && m<10) {
           		m="0"+m;
			}
			try {
				if (h>0) {
					spans[i].innerHTML=h+":"+m+":"+s;
				}else{
					spans[i].innerHTML=m+":"+s;
				}
			}catch(err){} // ignore error
		}
	}
}

// Added try/catch to prevent errors, if updates occur while this runs.
function countdown() {
	var txt='0:00';
	if (counter>=0) {
		counter=counter-1;
	}
	if (counter>=0) {
		var s=counter;
		var h=Math.round(Math.floor(s/(60.0*60.0)));
		s%=(60*60);
		var m=Math.round(Math.floor(s/60.0));
		s%=(60);
		if (s<10) {
		s="0"+s;
		}
		if (h>0) {
			txt=h+":"+m+":"+s;
		}else{
			txt=m+":"+s;
		}
	} else {
		iscounting=0;
		clearInterval(Timer);
	}
	var divs=ajaxfindobjs('counter');
	for (var i=0;i<divs.length;i++) {
  		var obj=divs[i];
  		try {
  			obj.innerHTML=txt;
  		} catch(err) {} // ignore errors 
  	}
}

// Added try/catch to prevent errors, if updates occur while this runs.
function voteshow(id,value)
{
    for (i=1;i<=5;i++)
    {
        var objs=$("#"+id+'-'+i);
        for (var j=0;j<objs.length;j++)
        {
            var obj=objs[j];
            if (obj)
            {
                if (i>value)
                {
                    diff=(i-value);
                    if (diff>=1)
                    {
                        try
                        {
                            // Spaces AFTER the selected star (if on 3, 4 and 5 use this)
                            obj.src='/static/star-white.png';
                            obj.style.width='100%';
                        } catch(err) {} // ignore errors
                    } else
                    {
                        try
                        {
                            // This only gets called if value has decimals!
                            obj.src='/static/star-gold.png';
                            obj.style.width=100-(diff*100)+'%';
                        } catch(err) {} // ignore errors
                    }
                } else
                {
                    try
                    {
                        // Voting up to and under mouse pointer, or default value if not on img
                        obj.src='/static/star-red.png';
                        obj.style.width='100%';
                    } catch(err) {} // ignore errors
                }
            }
        }
    }
}