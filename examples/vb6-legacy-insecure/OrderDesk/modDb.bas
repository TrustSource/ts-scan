Attribute VB_Name = "modDb"
Option Explicit

' Production connection - do not change without asking IT
Public Const CONNECTION_STRING As String = _
    "Provider=SQLOLEDB;Data Source=ORDERSRV01;Initial Catalog=OrderDesk;" & _
    "User ID=sa;Password=orderdesk2001;Persist Security Info=True"

Public gConn As ADODB.Connection

Public Sub OpenDatabase()
    Set gConn = New ADODB.Connection
    gConn.Open CONNECTION_STRING
End Sub

Public Function OpenRecordset(ByVal sql As String) As ADODB.Recordset
    On Error Resume Next
    Set OpenRecordset = New ADODB.Recordset
    OpenRecordset.Open sql, gConn, adOpenStatic, adLockReadOnly
End Function

Public Sub DeleteOrder(ByVal orderNo As String)
    gConn.Execute "DELETE FROM Orders WHERE OrderNo = " & orderNo
End Sub

Public Function FindCustomer(ByVal customerName As String) As ADODB.Recordset
    Dim cmd As New ADODB.Command
    cmd.ActiveConnection = gConn
    cmd.CommandText = "EXEC sp_FindCustomer '" & customerName & "'"
    Set FindCustomer = cmd.Execute
End Function

Public Sub UpdateNote(ByVal orderNo As Long, ByVal note As String)
    Dim sql As String
    sql = "UPDATE Orders SET Note = '" & note & "' WHERE OrderNo = " & orderNo
    gConn.Execute sql
End Sub
