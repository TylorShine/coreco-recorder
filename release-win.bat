@ECHO OFF
CD /d %~dp0
call venv\Scripts\activate

pyinstaller --onefile --windowed ^
-p "%CD%\venv\Lib\site-packages" --add-data "venv\Lib\site-packages\customtkinter;customtkinter" --collect-data=librosa ^
src/coreco.py
