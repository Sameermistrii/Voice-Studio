Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = root & "\.venv\Scripts\pythonw.exe"
py = root & "\.venv\Scripts\python.exe"
app = root & "\app.py"

If Not fso.FileExists(py) Then
  MsgBox "Missing app Python." & vbCrLf & vbCrLf & "Run setup.bat first.", 16, "Voice Studio"
  WScript.Quit 1
End If

exe = py
If fso.FileExists(pyw) Then exe = pyw

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = root
sh.Environment("Process")("HF_HUB_DISABLE_XET") = "1"
If fso.FolderExists("D:\HuggingFace") Then
  sh.Environment("Process")("HF_HOME") = "D:\HuggingFace"
End If

' 0 = hide the console. python.exe otherwise opens a transparent Windows Terminal.
sh.Run """" & exe & """ """ & app & """", 0, False
