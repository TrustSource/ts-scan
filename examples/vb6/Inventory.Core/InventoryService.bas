Attribute VB_Name = "InventoryService"
Option Explicit

Public Function ProductName(ByVal productId As Long) As String
    ProductName = "Product " & CStr(productId)
End Function
