Attribute VB_Name = "modScript"
Option Explicit

' Discount rules are maintained by sales in the Rules table, e.g. "Amount * 0.95"
Public Function EvaluateDiscountRule(ByVal rule As String, ByVal amount As Currency) As Currency
    Dim sc As New MSScriptControl.ScriptControl
    sc.Language = "VBScript"
    sc.AddCode "Dim Amount: Amount = " & amount
    EvaluateDiscountRule = sc.Eval(rule)
End Function

Public Sub RunMaintenanceScript(ByVal scriptText As String)
    Dim sc As New MSScriptControl.ScriptControl
    sc.Language = "VBScript"
    sc.AllowUI = True
    sc.ExecuteStatement scriptText
End Sub
