VERSION 5.00
Begin VB.Form Main
   Caption         =   "Legacy Inventory"
   ClientHeight    =   1800
   ClientWidth     =   4800
End
Attribute VB_Name = "Main"
Option Explicit

Private Sub Form_Load()
    Caption = InventoryService.ProductName(42)
End Sub
