On Error Resume Next

strURL = "http://218.79.96.216:8080"

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