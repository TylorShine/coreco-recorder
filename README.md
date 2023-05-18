# CoReco
A general-purpose Corpus Recorder

`TODO: スクリーンショット画像`

## これは？
CoRecoは言語コーパスやシナリオなどのテキストと音声がペアになっている音声の収録を手助けするソフトウェアです。  
比較的大きなテキストセットの収録、内容の確認、ファイルの書き出しを主な用途として作成していますが、テキストと音声がセットになるような収録に使用できます。  


## 主な機能
`TODO: 各種機能のスクショ画像`  

- テキストを表示しながら音声を連続録音  
  一文づつ区切っての収録や、セリフ集の制作、シナリオの読み上げなどに使えます。  
  ITAコーパス形式やjsut-label text_kana形式の場合、よみがなも同時に表示されます。  
  音声入出力は、
  - Windows: MME, DirectSound, WDM/KS, ASIO, WASAPI
  - Mac OS X: Core Audio, JACK
  - Linux: ALSA, JACK, OSS

  に対応しています。(PortAudio依存、Windowsのみ動作確認)  
  また、録音中に
  - テキストを切り替えることで、次のテキストを連続して録音
  - すぐにリテイク

  が可能です。


- マルチチャンネル収録  
  オーディオI/Fに複数チャネル入力がある場合、同時に複数のチャンネルを別々のファイルとして収録できます。  
  現状、ch1からの連続した入力を全てモノラル、もしくはステレオペア(1-2, 3-4...)として収録可能です。


- 簡易的なテイク管理  
  同じテキストを録音した場合、新しいテイクとして録音されます。  
  採用するテイク(使用するテイク)をテキストごとに設定することで、書き出す際にそのテイクのみが書き出されます。  


- 簡易なメタ情報を付与  
  現状、テキストごとに
  - 確認済み、要リテイク チェックボックス
  - メモテキスト
  を設定できます。また、要リテイク チェックボックスをONにしておくことで、あとで次のリテイクが必要なテキストにジャンプできます。


- 音声の前後ブランク時間を設定  
  書き出し時に前後を切り取る時間の設定ができます。  
  録音、テキスト送り時の打鍵音のカットに有用です。
  録音時にはブランク時間としてステータス表示され、再生時には書き出される予定の範囲のみが再生されます。


- 収録した音声の再生  
  収録した音声はテイク、チャンネルを切り替えながら再生することができます。  
  収録した音声が正しいか、ノイズが無いかなどの確認に有用です。  


- 音声セットの書き出し  
  形式の指定、ファイル名パターンの指定、チャンネル範囲の指定、テキスト範囲の指定をして音声を書き出せます。  
  先に32bit float 96kHz wav形式で収録、後で16bit 44.1kHz flac形式に書き出しなど、フォーマット変更、リサンプリングしての出力が可能です。  


- テキストの取り込み  
  現状、
  - [ITAコーパス](https://github.com/mmorise/ita-corpus)形式
    ```
    <TYPE>_<TEXTNUMBER>:<TEXT>,<KANA>
    ...
    ```
  - [jsut-label](https://github.com/sarulab-speech/jsut-label)の[text_kana](https://github.com/sarulab-speech/jsut-label/tree/master/text_kana)/basic5000.yaml 形式
    ```
    <TYPE>_<TEXTNUMBER>:
        text_level0: <TEXT>
        kana_level0: <KANA>
    ...
    ```
  - [OREMO](http://nwp8861.web.fc2.com/soft/oremo/index.html) reclist.txt 形式
    ```
    <TEXT1> <TEXT2>...
    ...
    ```
  に対応しています。


## 操作方法、収録手順
1. CoRecoをダウンロードして好きなフォルダに配置
    - パッケージ版(通常はこちら)  
      `TODO: DLページへのリンク`
        - プロジェクト作成時、同一フォルダにプロジェクトフォルダ`projects`が作られるので、新しくフォルダを作ることをおすすめします。
1. 起動する
1. プロジェクトをつくる
    - `プロジェクト名を入力`欄に任意のプロジェクト名を入力して[Enter]もしくは[プロジェクトを作成/読み込み]ボタンをクリックします。
      - プロジェクト名 = `projects`フォルダ以下のフォルダ名にもなるので、`<>:"/\|?*`などフォルダ名に使えない文字は使用しないでください。
1. テキストを読み込む
    - [テキストの読み込み]ボタンをクリックすると、ファイル選択ポップアップが出るので、対応したテキストファイルを選択してください。
1. 各種設定を確認する
    - [録音フォーマット設定]ボタン  
        クリックして出てきたウィンドウで任意のフォーマットを設定します。(初期設定で`wav float モノラル収録`になっています。)
    - [出力デバイス]、[入力デバイス]欄  
        使用したいデバイスを選択します。
    - [入力チャンネル数]  
        同時収録するチャンネル数です。
        設定可能な最大チャンネルは入力デバイスによって異なります。通常、モノラルなら`1`、ステレオなら`2`に設定します。  
        (現状、ch1からの連続したチャンネル範囲のみに対応しています。)
    - [サンプルレート]  
        入力デバイスのサンプリングレートが表示されていて、これからこのサンプリングレートで収録されることになります。  
        収録サンプリングレートの要求がある場合などは、ここが一致することを確認し、違う場合は各OSのサウンドデバイスの設定やドライバの設定を見直すなどしたあと、再度CoRecoを起動してください。  
        (note: 書き出し時に必要だったら自動的にリサンプリングがされますが、アップサンプリングはおすすめしません。)
    - [ブランク時間]  
        開始:には録音開始操作からの"間"、終了:には録音終了した時間から遡る時間をそれぞれ秒単位で指定します。  
        ここで設定した時間がテキストごとのブランク時間にも予め設定されます。  
        (note: 録音自体は録音開始操作から終了操作の間行っていますので、あとで前後のブランク時間をなかったことにもできます。あくまで書き出し、再生時に効く設定です。)
    - [System]欄  
        このソフトの見た目を`Light`と`Dark`から選べます。`System`はお使いのシステム設定に合わせます。  
    - [100%]欄  
        ソフト全体の表示を拡大、縮小できます。
1. 音声の収録、再生、確認  
下記の[キーボード操作表](#キーボード操作表)などを参考に収録をしていきます。
    - 使用するテイク:は、録音後に自動的に最新のテイクになります。ここで選択したテイクが書き出しの際に使用されます。  
1. 音声の書き出し  
[音声の書き出し]ボタンで書き出し用ウィンドウが開きます。  
    - フォーマット、サンプルレート、詳細(ビット深度など)  
      書き出したいフォーマットを設定します。
    - 音量をノーマライズ  
      チェックを入れると、書き出し時にファイルごとに波形ピークがチェックされ、右欄に設定したdB値をピーク音量に音量がノーマライズされます。  
      (参考: 数値的には-6(dB)設定で約半分0.5です)
    - テキスト番号範囲、チャンネル範囲
      それぞれどの範囲のテキスト番号とチャンネルを書き出すかを設定します。  
      `1-4`の様な連続範囲、`1,3,7`などの個別指定、その組み合わせが指定可能です。  
      存在しない範囲は無視され、空欄の場合は全てを書き出します。
    - ファイル名パターン
      書き出す際のファイル/フォルダ名のパターンを指定します。  
      通常のファイル名として使用できる文字と、下記の[書き出し時のファイル名テンプレート表](#書き出し時のファイル名テンプレート表)にあるテンプレートのキーが使用できます。  
      例1: `${PROJECT_NAME}/ch${CHANNEL_NUMBER}/${TEXT_TYPE}/${TEXT_TYPE}_${TEXT_NUMBER4}.${OUTPUT_EXT}` (初期設定)  
      の場合、  
      `ITAコーパス収録_2023_05_19/ch1/EMOTION100/EMOTION100_0001.wav`  
      例2: `${PROJECT_NAME}/ch${CHANNEL_NUMBER2}/${TEXT_TYPE}/${TEXT}.${OUTPUT_EXT}`  
      の場合、  
      `ITAコーパス収録_2023_05_19/ch01/EMOTION100/えっ嘘でしょ。.wav`  
      など。
    - 出力先フォルダ  
      ここに指定したフォルダ以下にファイル名パターンで指定したフォルダ/ファイルが書き出されていきます。  
      (初期設定では`out`フォルダ以下に書き出されます。)

設定を確認後、[書き出し]ボタンをクリックで書き出されます。
      


## キーボード操作表
音声収録、再生中はできるだけキーボード操作のみで完結できるようにしています。  

- 通常(録音、再生していないとき)
  |  キー  |  操作  |
  | ------ | ------ |
  |  →、D  |  次のテキストへ  |
  |  ←、A  |  前のテキストへ  |
  |  ↑、W  |  次のテイクへ  |
  |  ↓、S  |  前のテイクへ  |
  |  Shift+→、Shift+D  |  次の`要リテイク`なテキストへ  |
  |  Shift+←、Shift+A  |  前の`要リテイク`なテキストへ  |
  |  Shift+↑、Shift+W  |  次のチャンネルへ  |
  |  Shift+↓、Shift+S  |  前のチャンネルへ  |
  |  Ctrl+R  |  現在のテキストを録音開始  |
  |  Space  |  現在のテキストの選択されたテイク、チャンネルを再生  |

- 録音中
  |  キー  |  操作  |
  | ------ | ------ |
  |  →、D  |  録音を停止し次のテキストを録音開始  |
  |  ←、A  |  録音を停止し前のテキストを録音開始  |
  |  Shift+→、Shift+D  |  録音を停止し次の`要リテイク`なテキストを録音開始  |
  |  Shift+←、Shift+A  |  録音を停止し前の`要リテイク`なテキストを録音開始  |
  |  R  |  録音を停止し再度録音開始(リテイク)  |
  |  Ctrl+R、Space  |  録音を停止  |

- 再生中
  |  キー  |  操作  |
  | ------ | ------ |
  |  Space  |  停止  |


## 書き出し時のファイル名テンプレート表
  |  キー  |  値  |
  | ------ | ------ |
  |  ${PROJECT_NAME}  |  プロジェクト名  |
  |  ${TEXT}  |  テキスト内容  |
  |  ${TEXT_TYPE}  |  テキストの種類(`EMOTION100`など)  |
  |  ${TEXT_NUMBER}  |  テキスト番号  |
  |  ${CHANNEL_NUMBER}  |  音声のチャンネル数  |
  |  ${TAKE_NUMBER}  |  テイク番号  |
  |  ${OUTPUT_EXT}  |  出力形式の拡張子(`wav`など)  |
  
また、NUMBER系は2-8文字のゼロ埋めに対応しています。
(例: ${TEXT_NUMBER4}=4文字幅でゼロ埋め、`0001`など)
  |  キー  |  値  |
  | ------ | ------ |
  |  ${TEXT_NUMBER[n]}  |  テキスト番号 n文字ゼロ埋め  |
  |  ${CHANNEL_NUMBER[n]}  |  音声のチャンネル数 n文字ゼロ埋め  |
  |  ${TAKE_NUMBER[n]}  |  テイク番号 n文字ゼロ埋め  |


## ライセンス情報
[MIT License](LICENSE) です。

