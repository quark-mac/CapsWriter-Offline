' 无感启动 CapsWriter（wscript 运行本脚本无窗口）
' 以「隐藏窗口」方式启动 start_server.exe / start_client.exe。
' 参数：无 = 启动服务端+客户端；server = 仅服务端；client = 仅客户端
Option Explicit
Dim fso, baseDir, sh, target
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")

If WScript.Arguments.Count > 0 Then
    target = LCase(WScript.Arguments(0))
Else
    target = "both"
End If

If target = "server" Or target = "both" Then
    sh.CurrentDirectory = baseDir
    sh.Run """" & baseDir & "\start_server.exe""", 0, False
End If

If target = "both" Then
    WScript.Sleep 1000
End If

If target = "client" Or target = "both" Then
    sh.CurrentDirectory = baseDir
    sh.Run """" & baseDir & "\start_client.exe""", 0, False
End If
