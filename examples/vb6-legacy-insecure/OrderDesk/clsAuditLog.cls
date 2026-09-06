VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
  Persistable = 0  'NotPersistable
  DataBindingBehavior = 0  'vbNone
  DataSourceBehavior  = 0  'vbNone
  MTSTransactionMode  = 0  'NotAnMTSObject
END
Attribute VB_Name = "clsAuditLog"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

Private m_logPath As String

Public Property Let LogPath(ByVal value As String)
    m_logPath = value
End Property

Public Sub Write(ByVal user As String, ByVal action As String)
    On Error Resume Next
    Dim fh As Integer
    fh = FreeFile
    Open m_logPath & "\" & user & ".log" For Append As #fh
    Print #fh, Now & vbTab & action
    Close #fh
End Sub

Public Function ReadLog(ByVal user As String) As String
    Dim fh As Integer
    Dim line As String
    fh = FreeFile
    Open m_logPath & "\" & user & ".log" For Input As #fh
    Do While Not EOF(fh)
        Line Input #fh, line
        ReadLog = ReadLog & line & vbCrLf
    Loop
    Close #fh
End Function
