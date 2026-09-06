Attribute VB_Name = "modNet"
Option Explicit

Public Const PRICE_SERVICE_URL As String = "http://prices.orderdesk.local/api/v1/prices"
Public Const WAREHOUSE_HOST As String = "10.0.12.5"
Public Const WAREHOUSE_PORT As Long = 7001

' ServerXMLHTTP option 2 = SXH_OPTION_IGNORE_SERVER_SSL_CERT_ERROR_FLAGS
Private Const SXH_SERVER_CERT_IGNORE_ALL_SERVER_ERRORS As Long = 13056

Public Function FetchPrices() As String
    Dim http As Object
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    ' The price server certificate expired years ago, ignore it
    http.setOption 2, SXH_SERVER_CERT_IGNORE_ALL_SERVER_ERRORS
    http.Open "GET", PRICE_SERVICE_URL, False
    http.send
    FetchPrices = http.responseText
End Function

Public Sub SendOrderToWarehouse(ByVal payload As String)
    With frmMain.wsWarehouse
        If .State <> 7 Then .Connect WAREHOUSE_HOST, WAREHOUSE_PORT
        .SendData payload & vbCrLf
    End With
End Sub

Public Function LoadPriceList(ByVal url As String) As String
    LoadPriceList = frmMain.inetPrices.OpenURL(url)
End Function

Public Function ParsePriceFeed(ByVal xml As String) As Object
    Dim doc As Object
    Set doc = CreateObject("MSXML2.DOMDocument.4.0")
    doc.async = False
    doc.resolveExternals = True
    doc.loadXML xml
    Set ParsePriceFeed = doc
End Function
