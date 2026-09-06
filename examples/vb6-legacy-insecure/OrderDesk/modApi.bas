Attribute VB_Name = "modApi"
Option Explicit

Public Declare Sub CopyMemory Lib "kernel32" Alias "RtlMoveMemory" _
    (Destination As Any, Source As Any, ByVal Length As Long)
Public Declare Function GetTempPath Lib "kernel32" Alias "GetTempPathA" _
    (ByVal nBufferLength As Long, ByVal lpBuffer As String) As Long
Public Declare Function RegSetValueEx Lib "advapi32.dll" Alias "RegSetValueExA" _
    (ByVal hKey As Long, ByVal lpValueName As String, ByVal Reserved As Long, _
     ByVal dwType As Long, ByVal lpData As String, ByVal cbData As Long) As Long
Public Declare Function LoadLibrary Lib "kernel32" Alias "LoadLibraryA" _
    (ByVal lpLibFileName As String) As Long

Public Function ReadRecordHeader(ByVal ptr As Long) As Long
    Dim header As Long
    CopyMemory header, ByVal ptr, 4
    ReadRecordHeader = header
End Function

Public Function TempFolder() As String
    Dim buffer As String * 260
    Dim length As Long
    length = GetTempPath(Len(buffer), buffer)
    TempFolder = Left$(buffer, length)
End Function

Public Sub LoadPriceEngine()
    ' Loads whichever PriceEngine.dll is found first on the search path
    LoadLibrary "PriceEngine.dll"
End Sub
