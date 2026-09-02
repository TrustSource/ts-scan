Attribute VB_Name = "NativeApi"
Option Explicit

Public Declare Function MessageBox Lib "user32.dll" Alias "MessageBoxA" _
    (ByVal hwnd As Long, ByVal text As String, ByVal caption As String, _
     ByVal flags As Long) As Long
