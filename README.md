# AImc 最小実装

本プロジェクトは、Minecraft(Java版) を映像入力のみで自律プレイする AI の最小構成を構築する取り組みです。Windows 10/11 と GPU (GTX 1070 Ti ×4) を想定し、Python 3.12/Conda 環境 `AImc` を前提としています。

## セットアップ
1. `environmentINFO.yml.sample` を `environmentINFO.yml` にコピーし、モニタ番号や ROI を編集してください。ファイルは YAML 互換 JSON 形式です。
2. 依存ライブラリは `pip install -r requirements.txt` ではなく、付属の Conda 環境で提供されます。必要に応じて `pip install pydantic==2.12.3 PySide6==6.10.0` を実行してください。

## 実行方法
- ROI セットアップ: `python main.py --setup`
- ライブ起動: `python main.py --live`

ライブ起動時に設定ファイルが存在しない、またはバリデーションに失敗した場合はエラーメッセージと修正手順を日本語で表示します。

## 既知の制約
- OpenGL (`libGL.so`) が無い環境では ROI オーバーレイを表示できません。その場合は Windows 実機で実行してください。
- OCR や dxcam は GPU/DirectX 環境が必須です。CI ではモック挙動のみ確認しています。
- 行動決定は単純なビヘイビアツリーであり、前進/右旋回/停止の3動作に限定されています。

## 今後の課題
- HUD 解析を実際のテンプレートマッチングで実装する。
- OCR から位置情報を抽出し、ブラックボードに反映する。
- 音声入出力との統合およびタスク管理の高度化。
