## 開発者向け
### 依存環境
- Python 3.10+

### 環境構築
1. リポジトリをクローン
    ```sh
    $ git clone https://github.com/TylorShine/coreco-recorder.git
    $ cd coreco
    ```
1. venv環境を作成、activate
    ```sh
    $ python -m venv venv
    ```
    - Windows
       ```bat
       > venv\Scripts\activate
       ```
    - Mac, Linux
       ```sh
       $ . venv/bin/activate
       ```
1. 環境構築
    ```sh
    $ pip install -r requirements-dev.txt
    $ flit install
    ```
    または
    ```sh
    $ pip install -r requirements/dev.txt
    ```
1. 実行
    ```sh
    $ python src/coreco.py
    ```
1. パッケージング (PyInstaller)
    ```sh
    $ flit install --deps production
    ```
    または
    ```sh
    $ pip install -r requirements/prod.txt
    ```
    のあと
    - Windows
        ```bat
        > pyinstaller --onefile --windowed \
        -p "%cd%/venv/lib/site-packages" \
        --add-data "venv/lib/site-packages/customtkinter;customtkinter" \
        --collect-data=librosa \
        src/coreco.py
        ```
    - Mac, Linux
        ```sh
        > pyinstaller --onefile --windowed \
        -p "`pwd`/venv/lib/site-packages" \
        --add-data "venv/lib/site-packages/customtkinter:customtkinter" \
        --collect-data=librosa \
        src/coreco.py
        ```
    