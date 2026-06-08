// filelocation: http://home.wangjianshuo.com/archives/2006/07/13/public_javascript.js
// Update via: http://home.wangjianshuo.com/cgi-bin/mt/mt.cgi?__mode=view&saved_rebuild=1&_type=template&blog_id=1&id=78

// This is the public Javascript.
// This page is included in all individual pages.

// This is remove link back to the same page
e = document.getElementsByTagName("A");
for(i=0; i < e.length; i++) {
	if(e[i].href == location.href) {
		e[i].removeAttribute("href");
		e[i].style.textDecoration = "none";
	}
}


document.write('<img src="http://home.wangjianshuo.com/cgi-bin/axs/ax.pl?mode=img&ref=');
document.write( escape( document.referrer ) );
document.write('" height="1" width="1" style="display:none" alt="" />');

//var s = document.createElement("script");
//s.setAttribute("src", "http://feedjit.com/serve/?bc=FFFFFF&amp;tc=494949&amp;brd1=336699&amp;lnk=494949&amp;hc=336699&amp;ww=640");
//document.getElementsByTagName("head")[0].appendChild(s);