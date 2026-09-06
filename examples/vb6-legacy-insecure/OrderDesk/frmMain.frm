VERSION 5.00
Object = "{831FDD16-0C5C-11D2-A9FC-0000F8754DA1}#2.0#0"; "MSCOMCTL.OCX"
Object = "{248DD890-BB45-11CF-9ABC-0080C7E7B78D}#1.0#0"; "MSWINSCK.OCX"
Object = "{48E59290-9880-11CF-9754-00AA00C00908}#1.0#0"; "MSINET.OCX"
Object = "{F9043C88-F6F2-101A-A3C9-08002B2F49FB}#1.2#0"; "COMDLG32.OCX"
Begin VB.Form frmMain
   Caption         =   "OrderDesk 2.4"
   ClientHeight    =   6030
   ClientLeft      =   165
   ClientTop       =   735
   ClientWidth     =   9525
   StartUpPosition =   3  'Windows Default
   Begin MSComctlLib.ListView lvwOrders
      Height          =   4215
      Left            =   120
      TabIndex        =   0
      Top             =   600
      Width           =   9255
      View            =   3
      LabelEdit       =   1
      FullRowSelect   =   -1  'True
   End
   Begin VB.TextBox txtOrderNo
      Height          =   285
      Left            =   1320
      TabIndex        =   1
      Top             =   120
      Width           =   1815
   End
   Begin VB.TextBox txtPriceListUrl
      Height          =   285
      Left            =   4560
      TabIndex        =   2
      Text            =   "http://prices.orderdesk.local/pricelist.csv"
      Top             =   120
      Width           =   4815
   End
   Begin VB.CommandButton cmdDelete
      Caption         =   "Delete order"
      Height          =   375
      Left            =   120
      TabIndex        =   3
      Top             =   5040
      Width           =   1575
   End
   Begin VB.CommandButton cmdPrint
      Caption         =   "Print report"
      Height          =   375
      Left            =   1800
      TabIndex        =   4
      Top             =   5040
      Width           =   1575
   End
   Begin VB.CommandButton cmdImport
      Caption         =   "Import price list"
      Height          =   375
      Left            =   3480
      TabIndex        =   5
      Top             =   5040
      Width           =   1815
   End
   Begin MSWinsockLib.Winsock wsWarehouse
      Left            =   8280
      Top             =   5040
      _ExtentX        =   741
      _ExtentY        =   741
      _Version        =   393216
   End
   Begin InetCtlsObjects.Inet inetPrices
      Left            =   8760
      Top             =   5040
      _ExtentX        =   1005
      _ExtentY        =   1005
      _Version        =   393216
   End
   Begin MSComDlg.CommonDialog dlgFile
      Left            =   7800
      Top             =   5040
      _ExtentX        =   847
      _ExtentY        =   847
      _Version        =   393216
   End
   Begin VB.Label lblOrderNo
      Caption         =   "Order no.:"
      Height          =   255
      Left            =   120
      Top             =   120
      Width           =   1095
   End
   Begin VB.Label lblUrl
      Caption         =   "Price list URL:"
      Height          =   255
      Left            =   3360
      Top             =   120
      Width           =   1215
   End
End
Attribute VB_Name = "frmMain"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Explicit

Private m_audit As New clsAuditLog

Private Sub Form_Load()
    On Error Resume Next
    modDb.OpenDatabase
    m_audit.LogPath = App.Path & "\logs"
    RefreshOrders
End Sub

Private Sub RefreshOrders()
    Dim rs As ADODB.Recordset
    Dim item As MSComctlLib.ListItem

    lvwOrders.ListItems.Clear
    Set rs = modDb.OpenRecordset("SELECT OrderNo, Customer, Total FROM Orders ORDER BY OrderNo DESC")
    Do While Not rs.EOF
        Set item = lvwOrders.ListItems.Add(, , CStr(rs!OrderNo))
        item.SubItems(1) = rs!Customer & ""
        item.SubItems(2) = Format$(rs!Total, "#,##0.00")
        rs.MoveNext
    Loop
End Sub

Private Sub cmdDelete_Click()
    If MsgBox("Delete order " & txtOrderNo.Text & "?", vbYesNo + vbQuestion) = vbYes Then
        modDb.DeleteOrder txtOrderNo.Text
        m_audit.Write Environ$("USERNAME"), "DELETE " & txtOrderNo.Text
        RefreshOrders
    End If
End Sub

Private Sub cmdPrint_Click()
    dlgFile.Filter = "Report files (*.rpt)|*.rpt"
    dlgFile.ShowOpen
    If Len(dlgFile.FileName) > 0 Then
        modShell.PrintReport dlgFile.FileName
    End If
End Sub

Private Sub cmdImport_Click()
    Dim csv As String
    csv = modNet.LoadPriceList(txtPriceListUrl.Text)
    modNet.SendOrderToWarehouse "PRICELIST " & Len(csv)
    MsgBox "Imported " & Len(csv) & " bytes.", vbInformation
End Sub
