Attribute VB_Name = "modCrypto"
Option Explicit

Private Declare Function CryptAcquireContext Lib "advapi32.dll" Alias "CryptAcquireContextA" _
    (ByRef phProv As Long, ByVal pszContainer As String, ByVal pszProvider As String, _
     ByVal dwProvType As Long, ByVal dwFlags As Long) As Long
Private Declare Function CryptCreateHash Lib "advapi32.dll" _
    (ByVal hProv As Long, ByVal Algid As Long, ByVal hKey As Long, ByVal dwFlags As Long, _
     ByRef phHash As Long) As Long
Private Declare Function CryptHashData Lib "advapi32.dll" _
    (ByVal hHash As Long, ByVal pbData As String, ByVal dwDataLen As Long, ByVal dwFlags As Long) As Long
Private Declare Function CryptDeriveKey Lib "advapi32.dll" _
    (ByVal hProv As Long, ByVal Algid As Long, ByVal hBaseData As Long, ByVal dwFlags As Long, _
     ByRef phKey As Long) As Long
Private Declare Function CryptEncrypt Lib "advapi32.dll" _
    (ByVal hKey As Long, ByVal hHash As Long, ByVal Final As Long, ByVal dwFlags As Long, _
     ByVal pbData As String, ByRef pdwDataLen As Long, ByVal dwBufLen As Long) As Long

Private Const PROV_RSA_FULL As Long = 1
Private Const CRYPT_VERIFYCONTEXT As Long = &HF0000000
Private Const CALG_MD5 As Long = &H8003&
Private Const CALG_RC4 As Long = &H6801&
Private Const CALG_DES As Long = &H6601&

Private Const LICENSE_KEY As String = "0D-4F-1A-77-C3-9B-22-E1"

Public Function XorEncrypt(ByVal plainText As String, ByVal key As String) As String
    Dim i As Long
    Dim result As String
    For i = 1 To Len(plainText)
        result = result & Chr$(Asc(Mid$(plainText, i, 1)) Xor Asc(Mid$(key, (i Mod Len(key)) + 1, 1)))
    Next i
    XorEncrypt = result
End Function

Public Function NewSessionToken() As String
    Randomize
    NewSessionToken = Hex$(CLng(Rnd * 2147483647))
End Function

Public Function HashPassword(ByVal password As String) As String
    Dim hProv As Long
    Dim hHash As Long
    If CryptAcquireContext(hProv, vbNullString, vbNullString, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT) = 0 Then Exit Function
    If CryptCreateHash(hProv, CALG_MD5, 0, 0, hHash) = 0 Then Exit Function
    CryptHashData hHash, password, Len(password), 0
    HashPassword = Hex$(hHash)
End Function

Public Function EncryptForTransfer(ByVal payload As String, ByVal password As String) As String
    Dim hProv As Long, hHash As Long, hKey As Long
    Dim dataLen As Long
    CryptAcquireContext hProv, vbNullString, vbNullString, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT
    CryptCreateHash hProv, CALG_MD5, 0, 0, hHash
    CryptHashData hHash, password, Len(password), 0
    CryptDeriveKey hProv, CALG_RC4, hHash, 0, hKey
    dataLen = Len(payload)
    CryptEncrypt hKey, 0, 1, 0, payload, dataLen, Len(payload)
    EncryptForTransfer = payload
End Function
