#!/usr/local/bin/perl -w


use CGI ':standard', '-debug';

# print "Content-type: text/vbscript\n\n";
print header();

my $logfile = "E:/customer/wangjianshuo/scripts/Webcam/WebCamURL.txt";
my $uplog = "E:/customer/wangjianshuo/scripts/Webcam/Uplog.txt";

if (param('ResetIP')) 
{
   open(URLFILE, ">$logfile") or die "Cannot open the file $logfile. Reason: $!";
   my $ipaddr = $ENV{'REMOTE_ADDR'};
   my $webu = "http://$ipaddr:8080";
   print URLFILE $webu;
   close(URLFILE);
   print "<h2>Webcam IP reset to $webu</h2>";

   open(LOG, ">>$uplog") or die "Cannot open update log file: $!";
   print LOG 
}


open(URLFILE, $logfile) or die "Cannot open the file $logfile. Reason: $!";
$WebCamURL = <URLFILE>;
close(URLFILE);


#------------------------------------------------------------------
print <<"EOF";

On Error Resume Next

strURL = "$WebCamURL"

lngMP70 = IsObject(CreateObject("WMPlayer.OCX"))

' Windows Media Player 7 Code
If (lngMP70) Then
	document.write "<OBJECT ID=MediaPlayer "
	document.write " CLASSID=CLSID:6BF52A52-394A-11D3-B153-00C04F79FAA6"
	document.write " standby=""Loading Microsoft Windows Media Player components..."" "
	document.write " TYPE=""application/x-oleobject"" >"
	document.write "<PARAM NAME=""url"" VALUE='"
	document.write strURL
	document.write "'>"
	document.write "<PARAM NAME=""AutoStart"" VALUE=""true"">"
	document.write "<PARAM NAME=""ShowControls"" VALUE=""1"">"
	document.write "<PARAM NAME=""uiMode"" VALUE=""mini"">"
	document.write "</OBJECT>"

' Windows Media Player 6.4 Code
Else
	document.write "<OBJECT ID=MediaPlayer "
	document.write " CLASSID=CLSID:22d6f312-b0f6-11d0-94ab-0080c74c7e95"
	document.write "CODEBASE=http://activex.microsoft.com/activex/controls/mplayer/en/nsmp2inf.cab#Version=6,4,5,715"
	document.write " standby=""Loading Microsoft Windows Media Player components..."" "
	document.write " TYPE=""application/x-oleobject"" >"
	document.write "<PARAM NAME=""FileName"" VALUE='"
	document.write strURL
	document.write "'>"
	document.write "<PARAM NAME=""AutoStart"" VALUE=""true"">"
	document.write "<PARAM NAME=""ShowControls"" VALUE=""1"">"
	document.write "</OBJECT>"
End If

document.write "<br>Broadcasting from Everbright Exhibition Center, Shanghai, China (" + strURL + ")" 

EOF
