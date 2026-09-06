Attribute VB_Name = "modShell"
Option Explicit

Public Declare Function ShellExecute Lib "shell32.dll" Alias "ShellExecuteA" _
    (ByVal hwnd As Long, ByVal lpOperation As String, ByVal lpFile As String, _
     ByVal lpParameters As String, ByVal lpDirectory As String, ByVal nShowCmd As Long) As Long

Public Sub PrintReport(ByVal reportFile As String)
    Shell "cmd.exe /c print " & reportFile, vbHide
End Sub

Public Sub OpenAttachment(ByVal attachmentPath As String)
    Dim wsh As Object
    Set wsh = CreateObject("WScript.Shell")
    wsh.Run attachmentPath, 1, True
End Sub

Public Sub ExportAndCleanup(ByVal exportDir As String)
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    If fso.FolderExists(exportDir) Then
        Kill exportDir & "\*.tmp"
    End If
    ShellExecute 0, "open", exportDir, vbNullString, vbNullString, 1
End Sub

Public Sub AutoFillLegacyTerminal()
    ' The old warehouse terminal has no API, so we type the login for the user
    AppActivate "Legacy Terminal"
    SendKeys "sa{TAB}orderdesk2001{ENTER}", True
End Sub

Public Function CommandLineOrder() As String
    CommandLineOrder = Command$
    If Len(CommandLineOrder) = 0 Then
        CommandLineOrder = Environ$("ORDERDESK_ORDER")
    End If
End Function

Public Sub ShowHelp()
    ' Static command, no user input involved
    Shell "hh.exe OrderDesk.chm", vbNormalFocus
End Sub
