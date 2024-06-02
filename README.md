# tktftp_server  
python3 tkinter tftp server  

![](./windows.png)  

**pyinstaller**  
```
pyinstaller -F tktftp.py --add-data 'icon.png:.' --hidden-import=PIL._tkinter_finder
```